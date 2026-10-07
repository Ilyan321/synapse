import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from config.groq_client import groq_engine
from config.settings import settings
from core.models import AgentProfile, ChatMessage

logger = logging.getLogger("synapse.moderator")

class ModeratorDecision(BaseModel):
    """Structured decision made by the Smart Moderator after each turn."""
    action: str = Field(
        description="Action to take: 'speak' (delegate to an agent), 'conclude' (wrap up and summarize), 'wait_for_user' (pause for user input)"
    )
    next_speaker: Optional[str] = Field(
        default=None,
        description="Name of the agent selected to speak next (MUST match an active agent name)"
    )
    reasoning: str = Field(
        description="1-sentence explanation for this routing decision"
    )
    is_wrap_up_requested: bool = Field(
        default=False,
        description="True if the user explicitly asked to wrap up/conclude the meeting"
    )

class SmartModerator:
    """
    Intelligent conversation router that manages turn-taking, handles @mentions,
    enforces debate convergence, and prevents infinite loops.
    """

    def __init__(self):
        self.engine = groq_engine

    def check_direct_mention(
        self,
        last_message_content: str,
        active_agents: List[AgentProfile]
    ) -> Optional[AgentProfile]:
        """
        Checks if the user or an agent explicitly tagged an active agent (e.g. '@Elena' or 'Elena:').
        """
        content_lower = last_message_content.lower()
        for agent in active_agents:
            agent_name_lower = agent.name.lower()
            # Check @name or direct name address at start/mention
            pattern = rf'(@|\b){re.escape(agent_name_lower)}(\b|:|\?)'
            if re.search(pattern, content_lower):
                return agent
        return None

    def check_wrap_up_intent(self, text: str) -> bool:
        """Detects if user asked to end, conclude, or summarize the meeting."""
        triggers = [
            "wrap up", "wrap-up", "dismiss", "conclude", "summary",
            "executive brief", "end meeting", "finish meeting", "done for now"
        ]
        text_lower = text.lower()
        return any(t in text_lower for t in triggers)

    def evaluate_next_turn(
        self,
        topic: str,
        active_agents: List[AgentProfile],
        chat_history: List[ChatMessage],
        current_turn_count: int,
        max_turn_budget: int = 6
    ) -> ModeratorDecision:
        """
        Evaluates the conversation state and decides who speaks next or if it should conclude.
        """
        if not active_agents:
            return ModeratorDecision(
                action="wait_for_user",
                reasoning="No active agents available in roster."
            )

        if not chat_history:
            # First turn: Pick the primary technical domain lead
            return ModeratorDecision(
                action="speak",
                next_speaker=active_agents[0].name,
                reasoning="Opening discussion with primary domain specialist."
            )

        last_msg = chat_history[-1]

        # 1. User message handling
        if last_msg.sender_type == "user":
            if self.check_wrap_up_intent(last_msg.content):
                return ModeratorDecision(
                    action="conclude",
                    reasoning="User explicitly requested meeting conclusion.",
                    is_wrap_up_requested=True
                )
            else:
                # User provided a new question or directive: ALWAYS delegate to an agent to respond
                # Check for direct @mention first
                mentioned_agent = self.check_direct_mention(last_msg.content, active_agents)
                if mentioned_agent:
                    return ModeratorDecision(
                        action="speak",
                        next_speaker=mentioned_agent.name,
                        reasoning=f"Directly addressed by founder in '{last_msg.content[:40]}'."
                    )
                # Pick the most relevant agent for this new user prompt
                speaker = active_agents[0].name
                return ModeratorDecision(
                    action="speak",
                    next_speaker=speaker,
                    reasoning=f"Answering founder prompt: '{last_msg.content[:50]}'."
                )

        # 2. Check for direct @mention between agents
        mentioned_agent = self.check_direct_mention(last_msg.content, active_agents)
        if mentioned_agent and last_msg.sender_name != mentioned_agent.name:
            return ModeratorDecision(
                action="speak",
                next_speaker=mentioned_agent.name,
                reasoning=f"Directly addressed by {last_msg.sender_name}."
            )

        # 3. Interactive Pausing: If we hit turn budget without wrap-up, ask founder to steer
        if current_turn_count >= max_turn_budget:
            return ModeratorDecision(
                action="wait_for_user",
                reasoning=f"Both specialists have staked out their positions on {topic[:40]}."
            )

        # 4. LLM-based intelligent speaker selection
        agent_roster_str = "\n".join([f"- {a.name}: {a.role}" for a in active_agents])
        recent_msgs_str = "\n".join([
            f"[{m.sender_name} ({m.sender_type})]: {m.content[:200]}"
            for m in chat_history[-4:]
        ])

        system_instruction = (
            "You are the SYNAPSE War Room Moderator.\n"
            "Your job is to read the conversation and select the next speaker or ask the founder a question.\n\n"
            "RULES:\n"
            "1. Only choose a name from the ACTIVE AGENTS list.\n"
            "2. Avoid having the same agent speak twice in a row.\n"
            "3. If both agents have given their initial positions, return action='wait_for_user' with reasoning stating a 1-sentence dilemma for the founder.\n"
            "4. If the user explicitly requested wrap up, return action='conclude'."
        )

        user_prompt = (
            f"MISSION: \"{topic}\"\n\n"
            f"ACTIVE AGENTS:\n{agent_roster_str}\n\n"
            f"RECENT MESSAGES:\n{recent_msgs_str}\n\n"
            f"Turn {current_turn_count}/{max_turn_budget}. Decide next action."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]

        try:
            decision: ModeratorDecision = self.engine.generate_structured(
                messages=messages,
                response_model=ModeratorDecision,
                model=settings.groq_router_model
            )
            # Validate selected speaker exists in active roster
            if decision.action == "speak":
                valid_names = [a.name for a in active_agents]
                if decision.next_speaker not in valid_names:
                    # Fallback to alternate agent
                    for a in active_agents:
                        if a.name != last_msg.sender_name:
                            decision.next_speaker = a.name
                            break
                    else:
                        decision.next_speaker = active_agents[0].name
            return decision
        except Exception as e:
            logger.error(f"Moderator LLM error: {e}. Falling back to round-robin.")
            # Fallback to next agent in rotation
            for a in active_agents:
                if a.name != last_msg.sender_name:
                    return ModeratorDecision(action="speak", next_speaker=a.name, reasoning="Fallback turn rotation.")
            return ModeratorDecision(action="speak", next_speaker=active_agents[0].name, reasoning="Default speaker.")

# Singleton instance
moderator = SmartModerator()
