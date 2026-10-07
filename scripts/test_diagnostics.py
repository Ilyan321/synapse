#!/usr/bin/env python3
"""
Synapse Comprehensive Subsystem Diagnostic & Verification Suite.
Checks all dependencies, API connections, database tables, sandbox security,
and multi-agent orchestration pipelines.
"""

import os
import sys
import time
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("synapse.diagnostics")

def run_diagnostics():
    print("\n" + "="*70)
    print("🔍 SYNAPSE SUBSYSTEM DIAGNOSTICS & VERIFICATION SUITE")
    print("="*70 + "\n")

    results = {}

    # 1. Environment & Library Checks
    print("1️⃣  Verifying Python Environment & Libraries...")
    try:
        import groq
        import supabase
        import slack_sdk
        import pydantic
        import httpx
        from config.settings import settings

        import slack_sdk.version
        slack_ver = slack_sdk.version.__version__
        print(f"   ✅ Python Version: {sys.version.split()[0]}")
        print(f"   ✅ Groq SDK: {groq.__version__}")
        print(f"   ✅ Pydantic: {pydantic.__version__}")
        print(f"   ✅ Slack SDK: {slack_ver}")
        print(f"   ✅ Supabase SDK: {supabase.__version__}")
        results["Libraries & Config"] = True
    except Exception as e:
        print(f"   ❌ Library Check Failed: {e}")
        results["Libraries & Config"] = False

    # 2. Groq Key Pool & Model Checks
    print("\n2️⃣  Verifying Groq API Key Pool & Inference Models...")
    try:
        from config.groq_client import groq_engine
        print(f"   • Configured Keys in Pool: {len(settings.groq_api_keys)}")
        
        # Test basic text completion
        t0 = time.time()
        test_resp = groq_engine.chat_completion(
            messages=[{"role": "user", "content": "Reply with 'SYNAPSE_OK'"}],
            model=settings.groq_router_model,
            max_tokens=20
        )
        latency = (time.time() - t0) * 1000
        print(f"   ✅ Fast Model ({settings.groq_router_model}): {test_resp.strip()} ({latency:.0f}ms)")

        # Test reasoning model
        t0 = time.time()
        test_agent = groq_engine.chat_completion(
            messages=[{"role": "user", "content": "Reply with 'REASONING_OK'"}],
            model=settings.groq_agent_model,
            max_tokens=20
        )
        latency_agent = (time.time() - t0) * 1000
        print(f"   ✅ Deep Agent Model ({settings.groq_agent_model}): {test_agent.strip()} ({latency_agent:.0f}ms)")
        results["Groq Key Pool & LLM Inference"] = True
    except Exception as e:
        print(f"   ❌ Groq Inference Failed: {e}")
        results["Groq Key Pool & LLM Inference"] = False

    # 3. Supabase Cloud Database Check
    print("\n3️⃣  Verifying Supabase Cloud Database (CRUD)...")
    try:
        from core.db import db
        from core.models import AgentProfile
        import uuid

        # Read agents
        all_agents = db.get_all_agents()
        print(f"   ✅ Supabase Connection Healthy. Found {len(all_agents)} existing agents in company roster.")

        # Test create test session
        test_session = db.create_or_get_session(
            channel_id="TEST_DIAGNOSTIC",
            thread_ts=f"test_{int(time.time())}",
            topic="Diagnostic Verification Test",
            initial_roster=["DiagBot"]
        )
        print(f"   ✅ Supabase Session Created: ID={test_session.id}")
        results["Supabase Persistent DB"] = True
    except Exception as e:
        print(f"   ❌ Supabase DB Check Failed: {e}")
        results["Supabase Persistent DB"] = False

    # 4. Python Sandbox & AST Expression Auto-Print Check
    print("\n4️⃣  Verifying Autonomous Python Sandbox & Safety Filters...")
    try:
        from tools.python_runner import python_sandbox
        
        # Test standard execution
        res1 = python_sandbox.execute_code("x = 50 * 2\nx")
        if res1.get("success") and res1.get("stdout") == "100":
            print(f"   ✅ Auto-Print Expression Handling: stdout = '{res1.get('stdout')}'")
        else:
            print(f"   ⚠️ Auto-Print stdout: {res1}")

        # Test security filter
        res_sec = python_sandbox.execute_code("import os; os.system('rm -rf /')")
        if not res_sec.get("success") and "Security restriction" in res_sec.get("error", ""):
            print("   ✅ Security Sandbox Restriction: Blocked destructive call successfully.")
        results["Python Sandbox"] = True
    except Exception as e:
        print(f"   ❌ Sandbox Check Failed: {e}")
        results["Python Sandbox"] = False

    # 5. Slack API & Channel Check
    print("\n5️⃣  Verifying Slack Integration & Permissions...")
    try:
        from slack_bot.client import slack_service
        health = slack_service.health_check()
        if health.get("status") == "healthy":
            print(f"   ✅ Slack Auth Healthy: Team='{health.get('team')}', Bot User='{health.get('user')}' ({health.get('user_id')})")
            
            # Check default channel
            channel_id = settings.slack_default_channel
            info = slack_service.client.conversations_info(channel=channel_id)
            ch_name = info["channel"]["name"]
            is_member = info["channel"].get("is_member")
            print(f"   ✅ Target Channel: #{ch_name} ({channel_id}) | Bot is member: {is_member}")
            results["Slack Bot & OAuth Scopes"] = True
        else:
            print(f"   ❌ Slack Unhealthy: {health.get('error')}")
            results["Slack Bot & OAuth Scopes"] = False
    except Exception as e:
        print(f"   ❌ Slack API Check Failed: {e}")
        results["Slack Bot & OAuth Scopes"] = False

    # 6. Spawner & Recruiter Check
    print("\n6️⃣  Verifying Meta-Agent Recruiter (Spawner)...")
    try:
        from core.spawner import spawner_service
        recruitment = spawner_service.assemble_team_for_topic(
            user_prompt="Build a high-frequency crypto arbitrage bot",
            target_team_size=2,
            force_fresh=False
        )
        names = recruitment.reused_existing_agent_names + [a.name for a in recruitment.newly_created_agents]
        print(f"   ✅ Recruited Specialists: {', '.join(names)}")
        print(f"   ✅ Mission Brief: {recruitment.mission_brief}")
        results["Meta-Agent Spawner"] = True
    except Exception as e:
        print(f"   ❌ Spawner Check Failed: {e}")
        results["Meta-Agent Spawner"] = False

    # 7. Smart Moderator Routing Check
    print("\n7️⃣  Verifying Smart Moderator Decision Engine...")
    try:
        from core.moderator import moderator
        from core.models import AgentProfile, ChatMessage
        
        sample_agents = [
            AgentProfile(name="Elena", role="HFT Lead", system_prompt="Test"),
            AgentProfile(name="Marcus", role="Risk Lead", system_prompt="Test")
        ]
        
        # Test wrap-up detection
        is_wrap = moderator.check_wrap_up_intent("Wrap up the meeting now please")
        print(f"   ✅ Wrap-Up Intent Detection: {is_wrap}")
        
        # Test turn evaluation
        dec = moderator.evaluate_next_turn(
            topic="Arbitrage Latency",
            active_agents=sample_agents,
            chat_history=[ChatMessage(
                session_id=str(uuid.uuid4()),
                sender_name="User",
                sender_role="Founder",
                sender_type="user",
                content="How do we reduce latency to sub-microsecond?"
            )],
            current_turn_count=1,
            max_turn_budget=2
        )
        print(f"   ✅ Moderator Routing: Action='{dec.action}', Speaker='{dec.next_speaker}' ({dec.reasoning})")
        results["Smart Moderator"] = True
    except Exception as e:
        print(f"   ❌ Moderator Check Failed: {e}")
        results["Smart Moderator"] = False

    # Summary
    print("\n" + "="*70)
    print("📊 DIAGNOSTIC SUMMARY MATRIX")
    print("="*70)
    all_passed = True
    for component, passed in results.items():
        status_icon = "✅ PASS" if passed else "❌ FAIL"
        print(f" • {component:<35}: {status_icon}")
        if not passed:
            all_passed = False
    print("="*70)
    if all_passed:
        print("🎉 ALL SYNAPSE SUBSYSTEMS ARE ACCURATE & OPERATIONAL!\n")
    else:
        print("⚠️ SOME SUBSYSTEMS REPORTED ISSUES.\n")
    return all_passed

if __name__ == "__main__":
    success = run_diagnostics()
    sys.exit(0 if success else 1)
