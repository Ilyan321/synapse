import sys
import os
import time
import argparse
import logging

from config.settings import settings
from config.groq_client import groq_engine
from core.db import db
from core.models import AgentProfile, ThreadSession, ChatMessage
from core.spawner import spawner_service
from core.groupchat import war_room_engine
from slack_bot.client import slack_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("synapse.main")

def run_interactive_war_room(topic: str, channel: str = None, team_size: int = 3, turns: int = 4):
    """
    Executes a complete on-demand multi-agent simulation for a given topic.
    """
    target_channel = channel or settings.slack_default_channel
    print("\n" + "="*60)
    print(f"⚡ SYNAPSE WAR ROOM ENGINE INITIATING")
    print(f"Topic: \"{topic}\"")
    print(f"Channel: {target_channel}")
    print("="*60 + "\n")

    # 1. Spawner Meta-Agent Recruits Team
    print("🔍 [1/4] Spawner Meta-Agent analyzing topic & recruiting specialists...")
    recruitment = spawner_service.assemble_team_for_topic(
        user_prompt=topic,
        target_team_size=team_size,
        force_fresh=False
    )

    # Collect active agent instances
    active_agents = []
    for name in recruitment.reused_existing_agent_names:
        a = db.get_agent_by_name(name)
        if a:
            active_agents.append(a)
    for a in recruitment.newly_created_agents:
        active_agents.append(a)

    print(f"\n👥 Assembled Elite Taskforce ({len(active_agents)} members):")
    team_roster_slack_str = []
    for a in active_agents:
        print(f"   👉 [{a.avatar_emoji}] {a.name} — {a.role}")
        team_roster_slack_str.append(f"{a.avatar_emoji} *{a.name}* ({a.role.split('(')[0].strip()})")
    print(f"   💡 Strategy: {recruitment.team_strategy_notes}\n")

    # 2. Initialize Parent Thread in Slack
    print("🚀 [2/4] Initializing War Room Parent Thread in Slack...")
    kickoff_text = (
        f"🚀 *SYNAPSE WAR ROOM ACTIVATED*\n"
        f"🎯 *Mission:* {topic}\n\n"
        f"👥 *Assigned Domain Taskforce:*\n" +
        "\n".join([f"• {s}" for s in team_roster_slack_str]) +
        f"\n\n_Discussion starting below in thread..._"
    )

    kickoff_res = slack_service.post_message(
        text=kickoff_text,
        channel=target_channel,
        username="Synapse Recruiter",
        icon_emoji=":zap:"
    )

    if not kickoff_res or not kickoff_res.get("ts"):
        logger.error("Failed to establish Slack thread. Check channel permissions.")
        return

    thread_ts = kickoff_res["ts"]
    print(f"   • Live Slack Thread TS: {thread_ts}")

    # 3. Create Session in Supabase
    session = db.create_or_get_session(
        channel_id=target_channel,
        thread_ts=thread_ts,
        topic=topic,
        initial_roster=[a.name for a in active_agents]
    )

    # Save User Prompt into Message Ledger
    db.save_message(ChatMessage(
        session_id=session.id,
        sender_name="Founder",
        sender_role="User",
        sender_type="user",
        content=topic
    ))

    # 4. Run War Room Multi-Agent Debate Loop
    print(f"\n🧠 [3/4] Running Multi-Agent Debate on Groq ({settings.groq_agent_model})...")
    executed_turns = war_room_engine.run_discussion_loop(
        session=session,
        active_agents=active_agents,
        max_turns=turns
    )

    print(f"\n   ✅ Executed {len(executed_turns)} debate turns and tool actions.")

    # 5. Conclude & Executive Summary
    print("\n📋 [4/4] Generating Executive Summary & Archiving...")
    summary_md = war_room_engine.generate_executive_summary(session, active_agents)
    print("\n" + "="*60)
    print("📊 EXECUTIVE BRIEFING DELIVERED TO SLACK THREAD")
    print("="*60 + "\n")
    print(summary_md)

def main():
    parser = argparse.ArgumentParser(description="Synapse Dynamic Multi-Agent War Room Engine")
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="Simulate a startup building an AI-powered automated code reviewer detecting security vulnerabilities in real-time",
        help="The high-level mission or task to simulate"
    )
    parser.add_argument(
        "--channel", "-c",
        type=str,
        default=None,
        help="Slack channel ID to post to (defaults to SLACK_DEFAULT_CHANNEL in .env)"
    )
    parser.add_argument(
        "--team-size", "-s",
        type=int,
        default=2,
        help="Number of specialized expert agents to recruit"
    )
    parser.add_argument(
        "--turns", "-t",
        type=int,
        default=3,
        help="Max debate turns per cycle"
    )

    args = parser.parse_args()
    run_interactive_war_room(
        topic=args.prompt,
        channel=args.channel,
        team_size=args.team_size,
        turns=args.turns
    )

if __name__ == "__main__":
    main()
