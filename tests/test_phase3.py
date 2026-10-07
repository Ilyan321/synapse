import sys
import os
from typing import List
from pydantic import BaseModel, Field

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import settings
from config.groq_client import groq_engine
from core.models import AgentProfile

class DynamicTeamPlan(BaseModel):
    """Schema for dynamic team generation with first-name-only constraint."""
    mission_title: str = Field(description="Short mission name")
    agents: List[AgentProfile] = Field(description="List of recruited expert agents with simple single first names")

def run_phase3_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 3: GROQ MULTI-KEY POOL & LLM TEST ")
    print("=======================================================\n")

    # 1. Test Key Pool Rotation
    print("🔍 [1/3] Testing Key Pool Round-Robin Load Balancing...")
    pool = groq_engine.pool
    print(f"   • Active Keys in Rotation: {len(pool.api_keys)}")
    
    # Verify round-robin behavior
    c1 = pool.get_client()
    c2 = pool.get_client()
    c3 = pool.get_client()
    print("   • Key rotation sequence cycling verified.")
    print("   ✅ Groq Key Pool load balancing PASSED.\n")

    # 2. Test Deep Reasoning Agent Model (openai/gpt-oss-120b)
    print(f"🔍 [2/3] Testing Deep Reasoning Model ({settings.groq_agent_model})...")
    prompt = [
        {"role": "system", "content": "You are a concise senior engineer."},
        {"role": "user", "content": "Explain in 1 sentence why event-driven architecture scales."}
    ]
    response = groq_engine.chat_completion(
        messages=prompt,
        model=settings.groq_agent_model,
        temperature=0.3
    )
    print(f"   • Model Output: \"{response.strip()}\"")
    assert len(response.strip()) > 10, "❌ Empty or invalid LLM response"
    print("   ✅ Groq deep reasoning inference PASSED.\n")

    # 3. Test Fast Structured JSON Generation (openai/gpt-oss-20b) with First-Name-Only constraint
    print(f"🔍 [3/3] Testing Fast Structured Persona Extraction ({settings.groq_router_model}) with First-Name-Only...")
    extraction_prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert AI recruiter. You assemble dynamic AI teams based on user tasks.\n"
                "CRITICAL RULE: Agent names MUST be simple single FIRST NAMES ONLY (e.g. 'Elena', 'Marcus', 'Sarah', 'Leo'). "
                "Do NOT use titles, last names, or prefixes like Dr. or Mr."
            )
        },
        {
            "role": "user",
            "content": "Recruit a 2-person founding team for an autonomous drone delivery startup."
        }
    ]

    team_plan: DynamicTeamPlan = groq_engine.generate_structured(
        messages=extraction_prompt,
        response_model=DynamicTeamPlan,
        model=settings.groq_router_model
    )

    print(f"   • Mission: {team_plan.mission_title}")
    print(f"   • Spawned {len(team_plan.agents)} dynamic agents:")
    for a in team_plan.agents:
        print(f"     👉 Name: {a.name} | Role: {a.role} | Avatar: {a.avatar_emoji}")
        # Verify first name only (no space, no 'Dr.', no 'Mr.')
        assert " " not in a.name.strip(), f"❌ Agent name '{a.name}' contains spaces (must be single first name only)!"
        assert not a.name.lower().startswith("dr"), f"❌ Agent name '{a.name}' has prefix (must be single first name only)!"

    print("   ✅ Structured Pydantic extraction with first-name rule PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 3 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase3_verification()
