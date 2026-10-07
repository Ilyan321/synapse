import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from config.groq_client import groq_engine
from config.settings import settings
from core.db import db
from core.models import AgentProfile

logger = logging.getLogger("synapse.spawner")

class RecruitmentDecision(BaseModel):
    """Structured LLM decision for team recruitment."""
    mission_title: str = Field(description="Crisp 3-6 word mission title")
    mission_brief: str = Field(description="1-2 sentence executive summary of the objective")
    reused_existing_agent_names: List[str] = Field(
        default_factory=list,
        description="Names of existing agents selected from the roster"
    )
    newly_created_agents: List[AgentProfile] = Field(
        default_factory=list,
        description="Newly designed senior expert agents needed for this mission (MUST have single first names only)"
    )
    team_strategy_notes: str = Field(
        default="",
        description="Why this specific combination of roles was chosen"
    )

class SpawnerService:
    """
    The Meta-Agent / Recruiter that analyzes user prompts, reviews the existing company roster,
    and dynamically spawns high-caliber AI agents on the fly.
    """

    def __init__(self):
        self.db = db
        self.engine = groq_engine

    def sanitize_agent_name(self, name: str) -> str:
        """Ensures the agent name is strictly a single, clean first name."""
        # Strip prefixes like Dr., Mr., Ms., Prof., etc.
        cleaned = re.sub(r'^(dr|mr|ms|mrs|prof|chief|senior)\.?\s*', '', name, flags=re.IGNORECASE)
        # Take only the first word
        first_word = cleaned.strip().split()[0]
        # Keep alphanumeric
        first_word = re.sub(r'[^a-zA-Z0-9]', '', first_word)
        # Capitalize nicely
        return first_word.capitalize() or "Agent"

    def assemble_team_for_topic(
        self,
        user_prompt: str,
        target_team_size: int = 3,
        force_fresh: bool = False
    ) -> RecruitmentDecision:
        """
        Analyzes the user's topic, consults the Supabase roster, and generates/assigns
        the optimal team of specialized dynamic agents.
        """
        existing_agents: List[AgentProfile] = [] if force_fresh else self.db.get_all_agents()
        
        # Build roster summary for prompt context
        roster_context = ""
        if existing_agents:
            roster_context = "EXISTING COMPANY DIRECTORY (ROSTER):\n"
            for a in existing_agents:
                roster_context += f"- Name: {a.name} | Role: {a.role}\n"
        else:
            roster_context = "EXISTING COMPANY DIRECTORY: (Empty - no agents currently exist)\n"

        system_instruction = (
            "You are the SYNAPSE Meta-Agent & Chief Recruiter.\n"
            "Your job is to analyze any mission or problem statement and assemble an elite, "
            "deeply specialized founding team / taskforce of top-tier AI domain experts.\n\n"
            "CRITICAL RULES FOR AGENT GENERATION:\n"
            "1. AGENT NAMES MUST BE SINGLE FIRST NAMES ONLY (e.g. 'Elena', 'Marcus', 'Sarah', 'Leo', 'Aria', 'David').\n"
            "   NEVER use titles (Dr., Mr.), last names, or multi-word names.\n"
            "2. DEEP SINGLE-DOMAIN SPECIALIZATION (NO GENERIC PROMPTS):\n"
            "   Each agent must NOT be a generic 'expert in cybersecurity' or 'generic coder'.\n"
            "   They must be a hyper-specialized authority in a single niche domain (e.g., 'Static AST Taint Analysis & Abstract Syntax Trees', "
            "   'Low-Latency eBPF Linux Kernel Tracing', 'SaaS Self-Serve Product-Led Growth & Viral Loops').\n"
            "3. RICH MULTI-PARAGRAPH SYSTEM PROMPTS WITH HIGH-SIGNAL SLACK DISCIPLINE:\n"
            "   The 'system_prompt' for each agent MUST define their 20-year pedigree and methodologies, but CRITICALLY ENFORCE:\n"
            "   - [Concise Communication Rule]: The agent MUST write in ultra-punchy, high-signal Slack style (2 to 4 sentences max per turn, strictly under 100 words).\n"
            "   - [No Markdown Tables]: NEVER output markdown tables (| col |). Use bullet points with bold keywords (• *Starter*: $49/mo).\n"
            "   - [Colleague Tagging]: Address colleagues directly by name (@Name) with sharp, opinionated trade-offs.\n"
            "   - [Code Sandbox]: If calculating numbers/economics, write a 3-line Python snippet that prints the key metric.\n"
            "4. REAL-WORLD COGNITIVE FRICTION: Design complementary agents who will rigorously challenge each other "
            "   (e.g., an ambitious Growth Lead vs. a cost-obsessed Pragmatic CTO vs. a rigorous Principal Researcher).\n"
            "5. ROSTER REUSE: If an existing agent in the directory is a great fit, list their name in 'reused_existing_agent_names'. "
            "   Otherwise, create new specialized agents in 'newly_created_agents'.\n"
            f"6. TARGET TEAM SIZE: Assemble a total of {target_team_size} agents.\n"
        )

        user_message = (
            f"{roster_context}\n"
            f"USER MISSION / PROMPT:\n"
            f"\"{user_prompt}\"\n\n"
            f"Please recruit the optimal team."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message}
        ]

        logger.info(f"Recruiter analyzing prompt: '{user_prompt[:60]}...'")
        decision: RecruitmentDecision = self.engine.generate_structured(
            messages=messages,
            response_model=RecruitmentDecision,
            model=settings.groq_router_model
        )

        # Sanitize names and persist any newly created agents to Supabase
        persisted_new_agents: List[AgentProfile] = []
        for agent in decision.newly_created_agents:
            agent.name = self.sanitize_agent_name(agent.name)
            # Ensure python_sandbox tool is enabled
            if "python_sandbox" not in agent.tools:
                agent.tools.append("python_sandbox")
            # Save to persistent Supabase roster
            saved = self.db.save_agent(agent)
            persisted_new_agents.append(saved)

        decision.newly_created_agents = persisted_new_agents
        return decision

# Singleton instance
spawner_service = SpawnerService()
