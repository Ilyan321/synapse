import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from config.groq_client import groq_engine
from config.settings import settings
from core.models import AgentProfile, ChatMessage

logger = logging.getLogger("synapse.moderator")

class ModeratorDecision(BaseModel):
    """Structured decision made by the Smart Moderator after each turn."""
    action: str = Field(
        description="Action to take: 'speak' (delegate to an agent), 'conclude' (wrap up and summarize), 'wait_for_user' (pause for user input)"
    )
    next_speaker: Optional[str] = Field(
        default=None,
        description="Name of the agent selected to speak next (MUST match an active agent name)"
    )
    reasoning: str = Field(
        description="1-sentence explanation for this routing decision"
    )
    is_wrap_up_requested: bool = Field(
        default=False,
        description="True if the user explicitly asked to wrap up/conclude the meeting"
    )

class SmartModerator:
    """
    Intelligent conversation router that manages turn-taking, handles @mentions,
    enforces debate convergence, and prevents infinite loops.
    """

    def __init__(self):
        self.engine = groq_engine

    def check_direct_mention(
        self,
        last_message_content: str,
        active_agents: List[AgentProfile]
    ) -> Optional[AgentProfile]:
        """
        Checks if the user or an agent explicitly tagged an active agent (e.g. '@Elena' or 'Elena:').
        """
        content_lower = last_message_content.lower()
        for agent in active_agents:
            agent_name_lower = agent.name.lower()
            # Check @name or direct name address at start/mention
            pattern = rf'(@|\b){re.escape(agent_name_lower)}(\b|:|\?)'
            if re.search(pattern, content_lower):
                return agent
        return None

    def check_wrap_up_intent(self, text: str) -> bool:
        """Detects if user asked to end, conclude, or summarize the meeting."""
        triggers = [
            "wrap up", "wrap-up", "dismiss", "conclude", "summary",
            "executive brief", "end meeting", "finish meeting", "done for now"
        ]
        text_lower = text.lower()
        return any(t in text_lower for t in triggers)

    def evaluate_next_turn(
        self,
        topic: str,
        active_agents: List[AgentProfile],
        chat_history: List[ChatMessage],
        current_turn_count: int,
        max_turn_budget: int = 6
    ) -> ModeratorDecision:
        """
        Evaluates the conversation state and decides who speaks next or if it should conclude.
        """
        if not active_agents:
            return ModeratorDecision(
                action="wait_for_user",
                reasoning="No active agents available in roster."
            )

        if not chat_history:
            # First turn: Pick the primary technical domain lead
            return ModeratorDecision(
                action="speak",
                next_speaker=active_agents[0].name,
                reasoning="Opening discussion with primary domain specialist."
            )

        last_msg = chat_history[-1]

        # 1. Check for explicit wrap-up request from user
        if last_msg.sender_type == "user" and self.check_wrap_up_intent(last_msg.content):
            return ModeratorDecision(
                action="conclude",
                reasoning="User requested meeting conclusion.",
                is_wrap_up_requested=True
            )

        # 2. Check for direct @mention in the last message
        mentioned_agent = self.check_direct_mention(last_msg.content, active_agents)
        if mentioned_agent:
            # Prevent self-loop if agent mentioned their own name
            if last_msg.sender_name != mentioned_agent.name:
                return ModeratorDecision(
                    action="speak",
                    next_speaker=mentioned_agent.name,
                    reasoning=f"Directly addressed by {last_msg.sender_name}."
                )

        # 3. Circuit breaker: If we hit max turn budget without new user input, conclude
        if current_turn_count >= max_turn_budget:
            return ModeratorDecision(
                action="conclude",
                reasoning=f"Reached max turn budget ({max_turn_budget} turns). Synthesizing consensus."
            )

        # 4. LLM-based intelligent speaker selection
        agent_roster_str = "\n".join([f"- {a.name}: {a.role}" for a in active_agents])
        recent_msgs_str = "\n".join([
            f"[{m.sender_name} ({m.sender_type})]: {m.content[:300]}"
            for m in chat_history[-6:]
        ])

        system_instruction = (
            "You are the SYNAPSE War Room Moderator.\n"
            "Your job is to read the active conversation and select which dynamic expert agent "
            "should speak next to advance the discussion, challenge technical assumptions, or run benchmarks.\n\n"
            "RULES:\n"
            "1. Only choose a name from the ACTIVE AGENTS list.\n"
            "2. Avoid having the same agent speak twice in a row unless necessary.\n"
            "3. If consensus has been reached and the objective is met, return action='conclude'.\n"
            "4. If input is needed from the user, return action='wait_for_user'."
        )

        user_prompt = (
            f"WAR ROOM MISSION: \"{topic}\"\n\n"
            f"ACTIVE AGENTS:\n{agent_roster_str}\n\n"
            f"RECENT MESSAGES:\n{recent_msgs_str}\n\n"
            f"Current turn count in this debate: {current_turn_count}/{max_turn_budget}\n"
            f"Decide who speaks next."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]

        try:
            decision: ModeratorDecision = self.engine.generate_structured(
                messages=messages,
                response_model=ModeratorDecision,
                model=settings.groq_router_model
            )
            # Validate selected speaker exists in active roster
            if decision.action == "speak":
                valid_names = [a.name for a in active_agents]
                if decision.next_speaker not in valid_names:
                    # Fallback to alternate agent
                    for a in active_agents:
                        if a.name != last_msg.sender_name:
                            decision.next_speaker = a.name
                            break
                    else:
                        decision.next_speaker = active_agents[0].name
            return decision
        except Exception as e:
            logger.error(f"Moderator LLM error: {e}. Falling back to round-robin.")
            # Fallback to next agent in rotation
            for a in active_agents:
                if a.name != last_msg.sender_name:
                    return ModeratorDecision(action="speak", next_speaker=a.name, reasoning="Fallback turn rotation.")
            return ModeratorDecision(action="speak", next_speaker=active_agents[0].name, reasoning="Default speaker.")

# Singleton instance
moderator = SmartModerator()
