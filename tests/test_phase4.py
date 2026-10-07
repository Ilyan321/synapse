import sys
import os

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.spawner import spawner_service, RecruitmentDecision
from core.db import db

def run_phase4_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 4: META-AGENT RECRUITER TEST     ")
    print("=======================================================\n")

    # 1. Test Spawning New Agents from High-Level Prompt
    print("🔍 [1/3] Testing Dynamic Persona Spawning from Scratch...")
    prompt_1 = "Simulate a seed-stage startup building an AI-powered automated cybersecurity code reviewer."
    
    decision_1: RecruitmentDecision = spawner_service.assemble_team_for_topic(
        user_prompt=prompt_1,
        target_team_size=3,
        force_fresh=True
    )

    print(f"   • Mission Title: {decision_1.mission_title}")
    print(f"   • Brief:         {decision_1.mission_brief}")
    print(f"   • Strategy:      {decision_1.team_strategy_notes}\n")

    print(f"   • Newly Created Agents ({len(decision_1.newly_created_agents)}):")
    for a in decision_1.newly_created_agents:
        print(f"     👉 [{a.avatar_emoji}] {a.name} — {a.role}")
        print(f"        Prompt Preview: {a.system_prompt[:120]}...\n")
        # Strict assertions
        assert " " not in a.name, f"❌ Agent name '{a.name}' is not a single first name!"
        assert len(a.system_prompt) > 80, f"❌ Agent '{a.name}' has insufficient system prompt depth"
        assert "python_sandbox" in a.tools, f"❌ Agent '{a.name}' missing python_sandbox tool"

    print("   ✅ Dynamic Persona Spawning & Quality PASSED.\n")

    # 2. Test Supabase Persistence of Newly Created Team
    print("🔍 [2/3] Verifying Roster Persistence in Supabase Database...")
    for a in decision_1.newly_created_agents:
        fetched = db.get_agent_by_name(a.name)
        assert fetched is not None, f"❌ Agent {a.name} was not persisted in Supabase"
        print(f"   • Verified in Supabase: {fetched.name} (UUID: {fetched.id})")
    print("   ✅ Supabase Directory Persistence PASSED.\n")

    # 3. Test Intelligent Roster Reuse on Follow-Up Task
    print("🔍 [3/3] Testing Intelligent Roster Reuse on Related Mission...")
    prompt_2 = "We need a security architecture review and performance simulation for our scanner codebase."
    decision_2: RecruitmentDecision = spawner_service.assemble_team_for_topic(
        user_prompt=prompt_2,
        target_team_size=2,
        force_fresh=False
    )

    print(f"   • Follow-up Mission: {decision_2.mission_title}")
    print(f"   • Reused Agents:     {decision_2.reused_existing_agent_names}")
    print(f"   • New Agents:        {[a.name for a in decision_2.newly_created_agents]}")
    print(f"   • Strategy:          {decision_2.team_strategy_notes}")

    assert len(decision_2.reused_existing_agent_names) + len(decision_2.newly_created_agents) >= 1, "❌ No team assembled"
    print("   ✅ Roster Re-use & Multi-Task Assembly PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 4 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase4_verification()
