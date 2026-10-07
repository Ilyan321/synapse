import json
import logging
import re
import threading
import time
from typing import List, Dict, Any, Optional, Type, TypeVar
from groq import Groq, RateLimitError, APIError
from pydantic import BaseModel
from config.settings import settings

logger = logging.getLogger("synapse.groq")
T = TypeVar("T", bound=BaseModel)

class GroqKeyPool:
    """
    Thread-safe Groq API Key Rotator with exponential backoff and rate-limit mitigation.
    Rotates through multiple API keys to distribute RPM/TPM load.
    """

    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("No Groq API keys provided in configuration.")
        self.api_keys = api_keys
        self._current_index = 0
        self._lock = threading.Lock()
        # Initialize Groq client instances for each key
        self._clients: List[Groq] = [Groq(api_key=k) for k in self.api_keys]
        logger.info(f"Initialized GroqKeyPool with {len(self.api_keys)} active API keys.")

    def get_client(self) -> Groq:
        """Returns the next client in round-robin sequence."""
        with self._lock:
            client = self._clients[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._clients)
            return client

    def execute_with_retry(
        self,
        func,
        max_attempts: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Executes a Groq call. If a RateLimitError (429) occurs, automatically
        rotates to the next key in the pool and retries with backoff.
        """
        attempts = max_attempts or (len(self.api_keys) * 2)
        last_exception = None

        for attempt in range(1, attempts + 1):
            client = self.get_client()
            try:
                return func(client, *args, **kwargs)
            except RateLimitError as rle:
                last_exception = rle
                backoff = min(0.5 * (2 ** (attempt - 1)), 4.0)
                logger.warning(
                    f"Groq Rate Limit (429) on attempt {attempt}/{attempts}. "
                    f"Rotating to next key and waiting {backoff:.1f}s..."
                )
                time.sleep(backoff)
            except APIError as api_err:
                last_exception = api_err
                if api_err.status_code == 429:
                    backoff = min(0.5 * (2 ** (attempt - 1)), 4.0)
                    time.sleep(backoff)
                else:
                    logger.error(f"Groq API Error: {api_err}")
                    raise api_err
            except Exception as e:
                logger.error(f"Unexpected error during Groq execution: {e}")
                raise e

        raise RuntimeError(
            f"Failed Groq request after {attempts} attempts across all keys in pool: {last_exception}"
        )

class GroqEngine:
    """High-level LLM interface for fast routing, structured JSON generation, and agent reasoning."""

    def __init__(self):
        self.pool = GroqKeyPool(settings.groq_api_keys)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Performs a chat completion using the Groq multi-key pool.
        """
        target_model = model or settings.groq_agent_model

        def _call(client: Groq):
            kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if response_format:
                kwargs["response_format"] = response_format

            chat_completion = client.chat.completions.create(**kwargs)
            return chat_completion.choices[0].message.content or ""

        return self.pool.execute_with_retry(_call)

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> T:
        """
        Enforces structured JSON output matching a Pydantic model with schema injection
        and fallback regex parsing.
        """
        target_model = model or settings.groq_router_model
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)

        schema_instruction = (
            f"\n\nCRITICAL: Respond ONLY with a valid JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"You MUST output valid JSON format."
        )

        augmented_messages = list(messages)
        augmented_messages[-1] = {
            "role": augmented_messages[-1]["role"],
            "content": augmented_messages[-1]["content"] + schema_instruction
        }

        # Try with strict response_format first, fallback to text mode if 400
        raw_json_str = ""
        try:
            raw_json_str = self.chat_completion(
                messages=augmented_messages,
                model=target_model,
                temperature=temperature,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
        except Exception as err:
            logger.warning(f"Strict json_object mode failed ({err}). Retrying in standard completion mode with regex extraction...")
            raw_json_str = self.chat_completion(
                messages=augmented_messages,
                model=target_model,
                temperature=temperature,
                max_tokens=4000
            )

        # Robust parsing of JSON from model output
        raw_text = raw_json_str.strip()
        
        # 1. Direct JSON parse
        try:
            data = json.loads(raw_text)
            return response_model.model_validate(data)
        except Exception:
            pass

        # 2. Extract from markdown code blocks (```json ... ```)
        md_matches = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
        for block in reversed(md_matches):
            try:
                data = json.loads(block.strip())
                return response_model.model_validate(data)
            except Exception:
                pass

        # 3. Extract balanced JSON objects (handles schemas/thoughts concatenated with output)
        candidates = []
        stack = []
        start_idx = None
        for idx, char in enumerate(raw_text):
            if char == '{':
                if not stack:
                    start_idx = idx
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        candidates.append(raw_text[start_idx:idx+1])
                        start_idx = None

        for cand in reversed(candidates):
            try:
                data = json.loads(cand)
                return response_model.model_validate(data)
            except Exception:
                pass

        # 4. Fallback regex
        try:
            json_match = re.search(r'(\{[\s\S]*\})', raw_text)
            if json_match:
                data = json.loads(json_match.group(1))
                return response_model.model_validate(data)
        except Exception:
            pass

        logger.error(f"Failed to parse structured response into {response_model.__name__}:\nRaw: {raw_json_str}")
        raise ValueError(f"Could not extract valid {response_model.__name__} from LLM response")

# Singleton instance
groq_engine = GroqEngine()
