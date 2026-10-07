import sys
import os
import time
import uuid

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db
from core.models import AgentProfile, ThreadSession, ChatMessage
from core.moderator import moderator
from core.groupchat import war_room_engine
from core.spawner import spawner_service

def run_phase5_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 5: WAR ROOM & MODERATOR TEST    ")
    print("=======================================================\n")

    # 1. Recruit a Dynamic 2-Agent Expert Team
    print("🔍 [1/4] Recruiting Dynamic Expert Team for War Room...")
    prompt = "Design a high-throughput, low-false-positive real-time code vulnerability scanner"
    recruitment = spawner_service.assemble_team_for_topic(
        user_prompt=prompt,
        target_team_size=2,
        force_fresh=False
    )
    
    # Collect active agents from roster
    active_agents = []
    for name in recruitment.reused_existing_agent_names:
        a = db.get_agent_by_name(name)
        if a:
            active_agents.append(a)
    for a in recruitment.newly_created_agents:
        active_agents.append(a)

    print(f"   • Active War Room Roster ({len(active_agents)} agents):")
    for a in active_agents:
        print(f"     👉 [{a.avatar_emoji}] {a.name}: {a.role}")
    assert len(active_agents) >= 2, "❌ Expected at least 2 agents"
    print("   ✅ Team Assembly PASSED.\n")

    # 2. Initialize Session & User Kickoff Message
    print("🔍 [2/4] Initializing War Room Session & User Kickoff in Slack...")
    from slack_bot.client import slack_service

    # Post initial parent topic message to Slack to start the thread
    kickoff_res = slack_service.post_message(
        text=f"🚀 *WAR ROOM INITIATED:*\n\"{prompt}\"\n\n*Recruited Team:* {', '.join([f'{a.name} ({a.role})' for a in active_agents])}",
        username="Synapse Orchestrator",
        icon_emoji=":zap:"
    )
    assert kickoff_res is not None, "❌ Failed to post kickoff message to Slack"
    thread_ts = kickoff_res["ts"]
    print(f"   • Slack Parent Thread TS Created: {thread_ts}")

    session = db.create_or_get_session(
        channel_id="C0BERK7RJFP",
        thread_ts=thread_ts,
        topic=prompt,
        initial_roster=[a.name for a in active_agents]
    )

    # Post initial user prompt to ledger
    db.save_message(ChatMessage(
        session_id=session.id,
        sender_name="Founder",
        sender_role="User",
        sender_type="user",
        content="Team, should we build our real-time scanner using static AST graph analysis or LLM prompt evaluation? We need <100ms latency."
    ))
    print(f"   • Session Created in DB: {session.id}")
    print("   ✅ War Room Session Initialization PASSED.\n")

    # 3. Run Automated Multi-Agent Debate Loop (3 turns)
    print("🔍 [3/4] Running Multi-Agent Debate Loop on Groq 120B...")
    turns = war_room_engine.run_discussion_loop(
        session=session,
        active_agents=active_agents,
        max_turns=3
    )

    print(f"   • Successfully executed {len(turns)} turns:")
    for t in turns:
        print(f"     💬 [{t.sender_name}]: {t.content[:150]}...\n")
        assert len(t.content) > 50, "❌ Turn output too short"
        assert t.sender_name in [a.name for a in active_agents], "❌ Unknown speaker"

    # Verify messages in Supabase
    msgs = db.get_session_messages(session.id)
    assert len(msgs) >= 4, f"❌ Expected at least 4 messages in DB, got {len(msgs)}"
    print("   ✅ Dynamic Multi-Agent Debate & Slack Delivery PASSED.\n")

    # 4. Conclude Session & Generate Executive Summary
    print("🔍 [4/4] Testing Session Wrap-Up & Executive Brief Generation...")
    summary_md = war_room_engine.generate_executive_summary(session, active_agents)
    assert len(summary_md) > 100, "❌ Summary markdown too short"
    print("   • Executive Summary Preview:")
    for line in summary_md.split("\n")[:8]:
        print(f"     {line}")
    print("     ...")

    concluded_session = db.create_or_get_session("C0BERK7RJFP", thread_ts, prompt)
    assert concluded_session.status == "concluded", "❌ Session status not updated"
    assert concluded_session.summary is not None, "❌ Summary not saved in DB"
    print("   ✅ Executive Summary Artifact & Wrap-Up PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 5 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase5_verification()
