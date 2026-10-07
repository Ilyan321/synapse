import sys
import os

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import settings
from core.db import db
from slack_bot.client import slack_service

def run_phase1_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 1 INTEGRATION & HEALTH TEST     ")
    print("=======================================================\n")

    # 1. Config Validation
    print("🔍 [1/3] Validating Configuration & Secrets...")
    status = settings.validate_foundation()
    print(f"   • Groq API Keys in Pool: {status['groq_keys_count']} keys detected")
    print(f"   • Supabase Configured:   {status['supabase_configured']}")
    print(f"   • Slack Configured:      {status['slack_configured']}")
    print(f"   • E2B Sandbox Config:    {status['e2b_configured']}")
    
    assert status['groq_keys_count'] >= 1, "❌ Groq keys missing!"
    assert status['supabase_configured'], "❌ Supabase configuration missing!"
    assert status['slack_configured'], "❌ Slack token missing!"
    print("   ✅ Config validation PASSED.\n")

    # 2. Supabase Health Check
    print("🔍 [2/3] Testing Supabase Database Connectivity...")
    db_health = db.health_check()
    print(f"   • Status:                {db_health.get('status')}")
    print(f"   • Connected:             {db_health.get('connected')}")
    print(f"   • Agents Table Count:    {db_health.get('current_agents_count', 0)}")
    
    assert db_health.get("connected") is True, f"❌ Supabase failed: {db_health.get('error')}"
    print("   ✅ Supabase PostgreSQL connectivity PASSED.\n")

    # 3. Slack Health & Live Persona Test
    print("🔍 [3/3] Testing Slack API & Dynamic Persona Masking...")
    slack_health = slack_service.health_check()
    print(f"   • Workspace Team:        {slack_health.get('team')}")
    print(f"   • Bot User:              {slack_health.get('user')}")
    print(f"   • Bot ID:                {slack_health.get('bot_id')}")

    assert slack_health.get("status") == "healthy", f"❌ Slack auth failed: {slack_health.get('error')}"

    # Test sending a simulated dynamic agent message
    print("   • Testing live message post to Slack channel...")
    post_res = slack_service.post_message(
        text="🧪 *Phase 1 Foundation Test:* Supabase tables verified & Groq key rotation pool loaded.",
        username="Synapse Sentry",
        icon_emoji=":shield:"
    )
    assert post_res is not None, "❌ Failed to post message to Slack"
    print(f"   • Message Sent! TS: {post_res.get('ts')}")
    print("   ✅ Slack communication & Persona Masking PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 1 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase1_verification()
