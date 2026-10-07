import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from config.settings import settings

logger = logging.getLogger("synapse.db")

class DatabaseManager:
    """Manages persistent connections and queries to Supabase."""

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
            # Query agents table count to verify access
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

# Singleton instance
db = DatabaseManager()
