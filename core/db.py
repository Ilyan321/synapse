import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from config.settings import settings
from core.models import AgentProfile, ThreadSession, ChatMessage

logger = logging.getLogger("synapse.db")

class DatabaseManager:
    """Manages persistent connections, queries, and data models in Supabase."""

    def __init__(self):
        self.url = settings.supabase_url
        self.key = settings.supabase_key
        self._client: Optional[Client] = None
        
        if self.url and self.key:
            try:
                self._client = create_client(self.url, self.key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")

    @property
    def client(self) -> Client:
        if not self._client:
            raise RuntimeError("Supabase client is not configured. Check SUPABASE_URL and SUPABASE_KEY.")
        return self._client

    def health_check(self) -> Dict[str, Any]:
        """Verifies database connectivity and table accessibility."""
        try:
            res = self.client.table("agents").select("id", count="exact").limit(1).execute()
            return {
                "status": "healthy",
                "connected": True,
                "agents_table_accessible": True,
                "current_agents_count": res.count or 0
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }

    # ==========================================
    # AGENT ROSTER OPERATIONS
    # ==========================================

    def save_agent(self, agent: AgentProfile) -> AgentProfile:
        """
        Saves or updates an agent profile in the persistent roster (Upsert by name).
        """
        payload = {
            "name": agent.name,
            "role": agent.role,
            "system_prompt": agent.system_prompt,
            "avatar_emoji": agent.avatar_emoji,
            "tools": agent.tools
        }
        res = self.client.table("agents").upsert(payload, on_conflict="name").execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            agent.id = row.get("id")
            return agent
        return agent

    def get_agent_by_name(self, name: str) -> Optional[AgentProfile]:
        """Fetches an existing agent by name from the roster."""
        res = self.client.table("agents").select("*").ilike("name", name).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            return AgentProfile(**row)
        return None

    def get_all_agents(self) -> List[AgentProfile]:
        """Fetches all agents in the company directory."""
        res = self.client.table("agents").select("*").order("created_at", desc=False).execute()
        return [AgentProfile(**row) for row in (res.data or [])]

    # ==========================================
    # SESSION (WAR ROOM) OPERATIONS
    # ==========================================

    def create_or_get_session(
        self,
        channel_id: str,
        thread_ts: str,
        topic: str,
        initial_roster: Optional[List[str]] = None
    ) -> ThreadSession:
        """
        Retrieves an active session for a Slack thread, or creates a new one.
        """
        # Check if session exists for this thread
        res = self.client.table("sessions").select("*").eq("slack_thread_ts", thread_ts).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            return ThreadSession(**row)

        # Create new session
        payload = {
            "slack_channel_id": channel_id,
            "slack_thread_ts": thread_ts,
            "topic": topic,
            "active_roster": initial_roster or [],
            "status": "active"
        }
        create_res = self.client.table("sessions").insert(payload).execute()
        if create_res.data and len(create_res.data) > 0:
            return ThreadSession(**create_res.data[0])
        raise RuntimeError("Failed to create session in Supabase")

    def update_session_roster(self, session_id: str, active_roster: List[str]) -> None:
        """Updates the list of active agents assigned to a session."""
        self.client.table("sessions").update({
            "active_roster": active_roster
        }).eq("id", session_id).execute()

    def conclude_session(self, session_id: str, summary: str) -> None:
        """Marks a session as concluded and records its final executive summary."""
        self.client.table("sessions").update({
            "status": "concluded",
            "summary": summary
        }).eq("id", session_id).execute()

    # ==========================================
    # CHAT MESSAGE LEDGER OPERATIONS
    # ==========================================

    def save_message(self, message: ChatMessage) -> ChatMessage:
        """Records a chat message or tool output into the persistent session ledger."""
        payload = {
            "session_id": message.session_id,
            "sender_name": message.sender_name,
            "sender_role": message.sender_role,
            "sender_type": message.sender_type,
            "content": message.content,
            "tool_calls": message.tool_calls
        }
        res = self.client.table("messages").insert(payload).execute()
        if res.data and len(res.data) > 0:
            message.id = res.data[0].get("id")
            return message
        return message

    def get_session_messages(self, session_id: str, limit: int = 30) -> List[ChatMessage]:
        """
        Retrieves the chronological message history for a session with a sliding-window limit.
        """
        res = self.client.table("messages")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .limit(limit)\
            .execute()
        return [ChatMessage(**row) for row in (res.data or [])]

# Singleton instance
db = DatabaseManager()
