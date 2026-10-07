import time
import logging
from typing import Dict, Any, Optional, Set
from config.settings import settings
from core.db import db
from core.models import ChatMessage
from core.spawner import spawner_service
from core.groupchat import war_room_engine
from core.moderator import moderator
from slack_bot.client import slack_service

logger = logging.getLogger("synapse.listener")

class SynapseSlackListener:
    """
    Continuous Polling / Event Listener for Slack channels and threads.
    Monitors for user prompts, dispatches the Spawner, and drives War Room threads.
    """

    def __init__(self, poll_interval: float = 3.0):
        self.slack = slack_service
        self.db = db
        self.spawner = spawner_service
        self.war_room = war_room_engine
        self.poll_interval = poll_interval
        self._processed_message_ts: Set[str] = set()
        self._bot_user_id: Optional[str] = None

    def get_bot_id(self) -> str:
        if not self._bot_user_id:
            health = self.slack.health_check()
            self._bot_user_id = health.get("user") or "U0BEWUH8XJM"
        return self._bot_user_id

    def fetch_channel_messages(self, channel_id: str, limit: int = 10) -> list:
        """Fetches the latest messages from a channel."""
        try:
            res = self.slack.client.conversations_history(channel=channel_id, limit=limit)
            if res.get("ok"):
                return res.get("messages", [])
        except Exception as e:
            logger.error(f"Error fetching channel history: {e}")
        return []

    def fetch_thread_replies(self, channel_id: str, thread_ts: str) -> list:
        """Fetches latest replies from a thread."""
        try:
            res = self.slack.client.conversations_replies(channel=channel_id, ts=thread_ts)
            if res.get("ok"):
                return res.get("messages", [])
        except Exception as e:
            logger.error(f"Error fetching thread replies: {e}")
        return []

    def handle_new_user_mission(self, channel_id: str, text: str, user_ts: str):
        """
        Handles a brand new top-level prompt posted by the user in the channel.
        """
        logger.info(f"🚀 New user mission detected: '{text[:60]}...' (TS: {user_ts})")

        # 1. Spawner Meta-Agent Recruits Team
        recruitment = self.spawner.assemble_team_for_topic(
            user_prompt=text,
            target_team_size=2,
            force_fresh=False
        )

        active_agents = []
        for name in recruitment.reused_existing_agent_names:
            a = self.db.get_agent_by_name(name)
            if a:
                active_agents.append(a)
        for a in recruitment.newly_created_agents:
            active_agents.append(a)

        # 2. Post Recruited Team Intro to thread
        team_intro_lines = [
            f"• {a.avatar_emoji} *{a.name}* — {a.role.split('(')[0].strip()}"
            for a in active_agents
        ]
        intro_text = (
            f"🚀 *SYNAPSE WAR ROOM ACTIVATED*\n"
            f"🎯 *Mission:* {recruitment.mission_brief or text}\n\n"
            f"👥 *Recruited Domain Specialists:*\n" +
            "\n".join(team_intro_lines) +
            f"\n\n_Starting debate in thread..._"
        )

        self.slack.post_message(
            text=intro_text,
            channel=channel_id,
            thread_ts=user_ts,
            username="Synapse Recruiter",
            icon_emoji=":zap:"
        )

        # 3. Create Session in Supabase
        session = self.db.create_or_get_session(
            channel_id=channel_id,
            thread_ts=user_ts,
            topic=text,
            initial_roster=[a.name for a in active_agents]
        )

        # Record User Prompt in DB
        self.db.save_message(ChatMessage(
            session_id=session.id,
            sender_name="User",
            sender_role="Founder",
            sender_type="user",
            content=text
        ))

        # 4. Run Discussion Loop (2-3 initial turns)
        self.war_room.run_discussion_loop(
            session=session,
            active_agents=active_agents,
            max_turns=3
        )

    def handle_thread_followup(self, channel_id: str, thread_ts: str, text: str, user_ts: str):
        """
        Handles a user replying inside an existing War Room thread.
        """
        logger.info(f"💬 User follow-up in thread {thread_ts}: '{text[:60]}...'")

        # Get existing session from Supabase
        session = self.db.create_or_get_session(channel_id, thread_ts, topic="")
        
        # Load active agents from session roster
        active_agents = []
        for name in session.active_roster:
            a = self.db.get_agent_by_name(name)
            if a:
                active_agents.append(a)

        if not active_agents:
            logger.warning("No active agents found for session.")
            return

        # Save user message to Supabase
        self.db.save_message(ChatMessage(
            session_id=session.id,
            sender_name="User",
            sender_role="Founder",
            sender_type="user",
            content=text
        ))

        # Check if user asked to wrap up
        if moderator.check_wrap_up_intent(text):
            self.war_room.generate_executive_summary(session, active_agents)
            return

        # Continue War Room Debate Loop with follow-up
        self.war_room.run_discussion_loop(
            session=session,
            active_agents=active_agents,
            max_turns=2
        )

    def start_polling(self, channel_id: Optional[str] = None):
        """
        Runs the continuous polling loop for the designated channel.
        """
        target_channel = channel_id or settings.slack_default_channel
        bot_id = self.get_bot_id()

        print("\n" + "="*60)
        print("⚡ SYNAPSE SLACK LISTENER ONLINE")
        print(f"📡 Monitoring Channel: {target_channel}")
        print(f"🤖 Bot User: {bot_id}")
        print("💬 Post any prompt or question in Slack to begin!")
        print("="*60 + "\n")

        # Initial seed of existing message timestamps to avoid reprocessing old messages
        initial_msgs = self.fetch_channel_messages(target_channel, limit=20)
        for m in initial_msgs:
            self._processed_message_ts.add(m.get("ts"))

        while True:
            try:
                recent_messages = self.fetch_channel_messages(target_channel, limit=10)
                for msg in reversed(recent_messages):
                    ts = msg.get("ts")
                    user = msg.get("user")
                    text = msg.get("text", "").strip()
                    thread_ts = msg.get("thread_ts")
                    subtype = msg.get("subtype")

                    # Skip already processed, bots, or empty messages
                    if not ts or ts in self._processed_message_ts:
                        continue
                    if user == bot_id or subtype == "bot_message":
                        self._processed_message_ts.add(ts)
                        continue

                    # Mark as processed
                    self._processed_message_ts.add(ts)

                    if not text:
                        continue

                    # Case A: Follow-up reply inside an existing thread
                    if thread_ts and thread_ts != ts:
                        self.handle_thread_followup(target_channel, thread_ts, text, ts)
                    # Case B: Brand new top-level prompt in channel
                    else:
                        self.handle_new_user_mission(target_channel, text, ts)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    listener = SynapseSlackListener()
    listener.start_polling()
