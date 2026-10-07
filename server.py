import os
import threading
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.settings import settings
from slack_bot.listener import SynapseSlackListener
from slack_bot.client import slack_service
from core.db import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("synapse.server")

listener = SynapseSlackListener()

def run_listener_daemon():
    """Runs the continuous Slack polling loop in a background thread."""
    logger.info("⚡ Starting Synapse Slack Polling Daemon Thread on Render...")
    try:
        listener.start_polling()
    except Exception as e:
        logger.error(f"Slack listener daemon error: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Slack Listener in background daemon thread
    t = threading.Thread(target=run_listener_daemon, daemon=True, name="SynapseListenerDaemon")
    t.start()
    logger.info("🚀 Background listener thread launched.")
    yield
    logger.info("🛑 Shutting down Synapse server.")

app = FastAPI(
    title="Synapse Autonomous War Room",
    version="1.0.0",
    description="Multi-agent orchestration daemon and API for Slack",
    lifespan=lifespan
)

@app.get("/")
@app.head("/")
def index():
    return {
        "status": "online",
        "service": "Synapse Multi-Agent Orchestrator",
        "channel": settings.slack_default_channel,
        "groq_keys_count": len(settings.groq_api_keys),
        "docs": "/docs"
    }

@app.get("/health")
@app.head("/health")
def health():
    slack_health = slack_service.health_check()
    agents = db.get_all_agents()
    return {
        "status": "healthy",
        "slack": slack_health,
        "supabase_roster_count": len(agents),
        "groq_model": settings.groq_agent_model
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
