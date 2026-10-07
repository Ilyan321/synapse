import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Centralized configuration manager for Synapse."""
    
    def __init__(self):
        # 1. Groq Multi-Key Rotation Pool
        raw_groq_keys = os.getenv("GROQ_API_KEYS", "")
        self.groq_api_keys: List[str] = [
            k.strip() for k in raw_groq_keys.split(",") if k.strip()
        ]
        if not self.groq_api_keys:
            # Fallback to single GROQ_API_KEY if present
            single_key = os.getenv("GROQ_API_KEY", "")
            if single_key.strip():
                self.groq_api_keys.append(single_key.strip())
                
        self.groq_router_model: str = os.getenv("GROQ_ROUTER_MODEL", "openai/gpt-oss-20b")
        self.groq_agent_model: str = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b")
        
        # 2. Supabase Settings
        self.supabase_url: str = os.getenv("SUPABASE_URL", "")
        self.supabase_key: str = os.getenv("SUPABASE_KEY", "")
        self.supabase_db_password: str = os.getenv("SUPABASE_DB_PASSWORD", "")
        
        # 3. Slack Settings
        self.slack_bot_token: str = os.getenv("SLACK_BOT_TOKEN", "")
        self.slack_user_token: str = os.getenv("SLACK_USER_TOKEN", "")
        self.slack_default_channel: str = os.getenv("SLACK_DEFAULT_CHANNEL", "C0BERK7RJFP")
        self.slack_team_id: str = os.getenv("SLACK_TEAM_ID", "T0BEYKV1TQU")
        
        # 4. Sandbox & Model Hub Settings
        self.python_execution_mode: str = os.getenv("PYTHON_EXECUTION_MODE", "subprocess")
        self.e2b_api_key: str = os.getenv("E2B_API_KEY", "")
        self.execution_timeout: int = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "15"))
        self.hf_token: str = os.getenv("HF_TOKEN", "")

    def validate_foundation(self) -> dict:
        """Validates that all essential Phase 1 foundation keys exist."""
        status = {
            "groq_keys_count": len(self.groq_api_keys),
            "supabase_configured": bool(self.supabase_url and self.supabase_key),
            "slack_configured": bool(self.slack_bot_token),
            "e2b_configured": bool(self.e2b_api_key)
        }
        return status

# Singleton settings instance
settings = Settings()
