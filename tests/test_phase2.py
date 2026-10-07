import sys
import os
import uuid
import time

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db
from core.models import AgentProfile, ThreadSession, ChatMessage

def run_phase2_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 2: DATABASE & DATA MODELS TEST  ")
    print("=======================================================\n")

    # 1. Test Agent Profile Creation & Persistence
    print("🔍 [1/4] Testing Dynamic Agent Persistence & Upsert...")
    test_agent = AgentProfile(
        name=f"Dr_Elena_Test_{uuid.uuid4().hex[:6]}",
        role="Principal AI Researcher (20+ yrs NLP & LLM Systems)",
        system_prompt="You are a senior AI researcher specializing in multi-agent orchestration and low-latency inference.",
        avatar_emoji=":female-scientist:",
        tools=["python_sandbox", "web_search"]
    )
    
    saved_agent = db.save_agent(test_agent)
    assert saved_agent.id is not None, "❌ Agent ID was not generated"
    print(f"   • Saved Agent: {saved_agent.name} (UUID: {saved_agent.id})")

    # Verify retrieval by name
    fetched_agent = db.get_agent_by_name(saved_agent.name)
    assert fetched_agent is not None, "❌ Failed to fetch agent by name"
    assert fetched_agent.role == test_agent.role, "❌ Fetched agent role mismatch"
    print("   • Retrieval by name: Verified successfully.")

    # Test Upsert without conflict
    saved_agent.role = "Senior AI Architect (Updated Role)"
    updated_agent = db.save_agent(saved_agent)
    assert updated_agent.role == "Senior AI Architect (Updated Role)", "❌ Upsert update failed"
    print("   • Upsert Behavior: Conflict-free update verified.")

    # List all roster agents
    all_agents = db.get_all_agents()
    print(f"   • Total Active Roster in Company Directory: {len(all_agents)} agents")
    print("   ✅ Agent Roster Operations PASSED.\n")

    # 2. Test War Room Session Lifecycle
    print("🔍 [2/4] Testing Session (War Room) Management...")
    fake_thread_ts = f"test_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    session = db.create_or_get_session(
        channel_id="C0BERK7RJFP",
        thread_ts=fake_thread_ts,
        topic="Simulate a high-frequency trading bot startup",
        initial_roster=[saved_agent.name]
    )
    assert session.id is not None, "❌ Session creation failed"
    print(f"   • Created Session ID: {session.id} for Thread TS: {session.slack_thread_ts}")

    # Test Idempotent Get
    session_dup = db.create_or_get_session(
        channel_id="C0BERK7RJFP",
        thread_ts=fake_thread_ts,
        topic="Duplicate call"
    )
    assert session_dup.id == session.id, "❌ Idempotent session retrieval failed"
    print("   • Idempotent retrieval for existing thread verified.")

    # Test Roster Update
    db.update_session_roster(session.id, [saved_agent.name, "Marcus_CTO"])
    print("   • Session active roster updated.")
    print("   ✅ Session Lifecycle Operations PASSED.\n")

    # 3. Test Chat Message Ledger
    print("🔍 [3/4] Testing Message Ledger & Tool Output Storage...")
    msg1 = db.save_message(ChatMessage(
        session_id=session.id,
        sender_name="User",
        sender_role="Founder",
        sender_type="user",
        content="What architecture should we use for real-time order routing?"
    ))
    assert msg1.id is not None, "❌ Failed to save user message"

    msg2 = db.save_message(ChatMessage(
        session_id=session.id,
        sender_name=saved_agent.name,
        sender_role=saved_agent.role,
        sender_type="agent",
        content="I recommend an event-driven architecture using Redis Streams with a Python benchmark simulation."
    ))
    assert msg2.id is not None, "❌ Failed to save agent message"

    msg3 = db.save_message(ChatMessage(
        session_id=session.id,
        sender_name=saved_agent.name,
        sender_role="Python Tool Sandbox",
        sender_type="tool",
        content="Benchmark executed: 50,000 events/sec processed in 0.21s.",
        tool_calls={"code": "import time; print('50k events')", "stdout": "50k events", "exit_code": 0}
    ))
    assert msg3.id is not None, "❌ Failed to save tool output message"
    assert msg3.tool_calls is not None, "❌ Tool calls JSON payload lost"

    history = db.get_session_messages(session.id, limit=10)
    assert len(history) == 3, f"❌ Expected 3 messages, got {len(history)}"
    print(f"   • Stored & Retrieved {len(history)} messages in chronological order.")
    print("   ✅ Chat Message Ledger Operations PASSED.\n")

    # 4. Test Conclude & Executive Summary
    print("🔍 [4/4] Testing Session Conclusion & Summary Artifact...")
    summary_text = "## Executive Summary: HFT Startup Architecture\n- Selected Redis Streams & C++ core\n- Benchmark verified: 50k ops/sec"
    db.conclude_session(session.id, summary_text)
    
    concluded_session = db.create_or_get_session(
        channel_id="C0BERK7RJFP",
        thread_ts=fake_thread_ts,
        topic=""
    )
    assert concluded_session.status == "concluded", "❌ Session status was not updated to concluded"
    assert concluded_session.summary == summary_text, "❌ Executive summary mismatch"
    print("   • Session concluded and executive summary archived successfully.")
    print("   ✅ Session Conclusion Operations PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 2 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase2_verification()
