from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class AgentProfile(BaseModel):
    """Schema representing an on-demand AI agent persona."""
    id: Optional[str] = Field(default=None, description="Unique UUID in Supabase")
    name: str = Field(description="Unique display name (e.g. 'Dr. Elena Chen' or 'Marcus_CTO')")
    role: str = Field(description="Job title & domain pedigree (e.g. 'Principal AI Researcher (20+ yrs NLP)')")
    system_prompt: str = Field(description="Deep persona instructions, style, domain knowledge, and biases")
    avatar_emoji: str = Field(default="🤖", description="Slack emoji icon for this persona (e.g. ':female-scientist:')")
    tools: List[str] = Field(default_factory=lambda: ["python_sandbox"], description="Enabled tools (e.g. 'python_sandbox', 'web_search')")
    created_at: Optional[datetime] = Field(default=None)

class ThreadSession(BaseModel):
    """Schema representing an active Slack thread war room."""
    id: Optional[str] = Field(default=None, description="UUID in Supabase")
    slack_channel_id: str = Field(description="Slack Channel ID (e.g. 'C0BERK7RJFP')")
    slack_thread_ts: str = Field(description="Slack Thread timestamp ID (e.g. '1791386888.355889')")
    topic: str = Field(description="The primary objective or prompt for this war room")
    active_roster: List[str] = Field(default_factory=list, description="List of agent names currently active in this thread")
    status: Literal["active", "concluded", "dismissed"] = Field(default="active", description="Session state")
    summary: Optional[str] = Field(default=None, description="Executive summary markdown artifact")
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)

class ChatMessage(BaseModel):
    """Schema representing a single message in the group chat ledger."""
    id: Optional[str] = Field(default=None, description="UUID in Supabase")
    session_id: str = Field(description="Associated session UUID")
    sender_name: str = Field(description="Sender display name (e.g. 'Dr. Elena Chen' or 'User')")
    sender_role: Optional[str] = Field(default=None, description="Sender role (e.g. 'Senior Researcher')")
    sender_type: Literal["user", "agent", "moderator", "tool", "system"] = Field(description="Category of sender")
    content: str = Field(description="Message body text")
    tool_calls: Optional[Dict[str, Any]] = Field(default=None, description="Tool execution payload and results if applicable")
    created_at: Optional[datetime] = Field(default=None)
