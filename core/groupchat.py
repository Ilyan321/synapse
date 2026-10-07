import logging
from typing import List, Dict, Any, Optional
from config.groq_client import groq_engine
from config.settings import settings
from core.db import db
from core.models import AgentProfile, ThreadSession, ChatMessage
from core.moderator import moderator, ModeratorDecision
from slack_bot.client import slack_service

logger = logging.getLogger("synapse.groupchat")

class WarRoomEngine:
    """
    Coordinates multi-agent debate sessions in a Slack thread,
    dispatches turns to deep-reasoning agents, and generates executive summaries.
    """

    def __init__(self):
        self.db = db
        self.engine = groq_engine
        self.moderator = moderator
        self.slack = slack_service

    def build_agent_turn_prompt(
        self,
        agent: AgentProfile,
        topic: str,
        active_agents: List[AgentProfile],
        chat_history: List[ChatMessage]
    ) -> List[Dict[str, str]]:
        """
        Constructs a high-context prompt for an agent staying strictly in their hyper-specialized character.
        """
        other_agents_str = ", ".join([f"{a.name} ({a.role})" for a in active_agents if a.name != agent.name])

        system_prompt = (
            f"YOU ARE {agent.name.upper()}.\n"
            f"YOUR ROLE & MASTERY: {agent.role}\n\n"
            f"=== YOUR DEEP PERSONA & SYSTEM INSTRUCTIONS ===\n"
            f"{agent.system_prompt}\n\n"
            f"=== WAR ROOM CONTEXT ===\n"
            f"TOPIC / MISSION: {topic}\n"
            f"YOUR COLLEAGUES IN THIS ROOM: {other_agents_str}\n\n"
            f"OPERATIONAL GUIDELINES:\n"
            f"1. Stay 100% in character with your deep 20-year domain mastery and technical philosophy.\n"
            f"2. BE CONCISE & PUNCHY: Keep your visible response to 1-2 short, high-impact paragraphs. "
            f"   Handle the deep complexity internally and present the bottom-line technical conclusion, concrete metrics, and direct decisions cleanly.\n"
            f"3. Directly address colleague statements by name (e.g. '@Mara', '@Jax') with constructive technical critique or agreement.\n"
            f"4. If you propose an algorithm or test calculation, include a clean, minimal runnable Python block ```python ... ```.\n"
            f"5. Do NOT prefix your response with '{agent.name}:'—just speak directly."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Append last 10 messages as dialogue history
        for msg in chat_history[-10:]:
            if msg.sender_name == agent.name:
                messages.append({"role": "assistant", "content": msg.content})
            else:
                formatted_speaker = f"[{msg.sender_name} ({msg.sender_role or msg.sender_type})]: {msg.content}"
                messages.append({"role": "user", "content": formatted_speaker})

        return messages

    def execute_turn(
        self,
        session: ThreadSession,
        active_agents: List[AgentProfile],
        agent_name: str
    ) -> ChatMessage:
        """
        Generates and logs a response from a specific dynamic agent,
        and automatically executes any embedded Python benchmarks in the sandbox.
        """
        agent = next((a for a in active_agents if a.name == agent_name), None)
        if not agent:
            raise ValueError(f"Agent {agent_name} not found in active roster.")

        history = self.db.get_session_messages(session.id, limit=20)
        messages = self.build_agent_turn_prompt(agent, session.topic, active_agents, history)

        logger.info(f"Agent {agent.name} thinking via {settings.groq_agent_model}...")
        response_text = self.engine.chat_completion(
            messages=messages,
            model=settings.groq_agent_model,
            temperature=0.6,
            max_tokens=1000
        )

        # 1. Save agent message to Supabase
        chat_msg = ChatMessage(
            session_id=session.id,
            sender_name=agent.name,
            sender_role=agent.role,
            sender_type="agent",
            content=response_text
        )
        saved_msg = self.db.save_message(chat_msg)

        # 2. Post to Slack Thread with dynamic persona avatar
        self.slack.post_message(
            text=response_text,
            channel=session.slack_channel_id,
            thread_ts=session.slack_thread_ts,
            username=f"{agent.name} ({agent.role.split('(')[0].strip()})",
            icon_emoji=agent.avatar_emoji
        )

        # 3. Autonomous Python Sandbox Execution
        from tools.python_runner import python_sandbox
        code_snippet = python_sandbox.extract_python_code(response_text)
        if code_snippet:
            logger.info(f"Detected Python code block from {agent.name}. Executing in sandbox...")
            exec_res = python_sandbox.execute_code(code_snippet)
            
            tool_output_content = ""
            if exec_res.get("success"):
                output_str = exec_res.get("stdout") or "[Code executed successfully with no stdout]"
                tool_output_content = f"⚙️ *Sandbox Result:*\n```\n{output_str}\n```"
            else:
                err_str = exec_res.get("error") or "Execution failed"
                tool_output_content = f"⚠️ *Execution Error:*\n```\n{err_str}\n```"

            # Save tool output to Supabase
            tool_msg = ChatMessage(
                session_id=session.id,
                sender_name=f"{agent.name} (Code Sandbox)",
                sender_role="Python Execution Sandbox",
                sender_type="tool",
                content=tool_output_content,
                tool_calls={"code": code_snippet, "result": exec_res}
            )
            self.db.save_message(tool_msg)

            # Post tool output to Slack thread
            self.slack.post_message(
                text=tool_output_content,
                channel=session.slack_channel_id,
                thread_ts=session.slack_thread_ts,
                username=f"{agent.name} (Code Runner)",
                icon_emoji=":gear:"
            )

        return saved_msg

    def generate_executive_summary(
        self,
        session: ThreadSession,
        active_agents: List[AgentProfile]
    ) -> str:
        """
        Synthesizes the entire multi-agent discussion into a structured executive summary artifact.
        """
        history = self.db.get_session_messages(session.id, limit=50)
        transcript = "\n\n".join([
            f"**{m.sender_name}** ({m.sender_role or m.sender_type}):\n{m.content}"
            for m in history
        ])

        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "You are an elite Executive Summarizer.\n"
                    "Synthesize the multi-agent war room debate into a structured, publication-grade "
                    "Executive Summary Markdown Artifact."
                )
            },
            {
                "role": "user",
                "content": (
                    f"WAR ROOM TOPIC: \"{session.topic}\"\n\n"
                    f"PARTICIPANTS: {', '.join([f'{a.name} ({a.role})' for a in active_agents])}\n\n"
                    f"FULL DEBATE TRANSCRIPT:\n{transcript}\n\n"
                    f"Please produce a comprehensive Executive Brief with:\n"
                    f"1. Executive Overview & Core Problem\n"
                    f"2. Key Architectural & Strategic Consensus\n"
                    f"3. Crucial Technical Trade-Offs & Debates\n"
                    f"4. Actionable Next Steps & Implementation Roadmap"
                )
            }
        ]

        summary_md = self.engine.chat_completion(
            messages=summary_prompt,
            model=settings.groq_agent_model,
            temperature=0.3
        )

        # Conclude in DB
        self.db.conclude_session(session.id, summary_md)

        # Post summary to Slack thread
        summary_post = (
            f"📋 *EXECUTIVE BRIEFING & WAR ROOM CONCLUDED*\n\n"
            f"{summary_md}"
        )
        self.slack.post_message(
            text=summary_post,
            channel=session.slack_channel_id,
            thread_ts=session.slack_thread_ts,
            username="Synapse Orchestrator",
            icon_emoji=":clipboard:"
        )

        return summary_md

    def run_discussion_loop(
        self,
        session: ThreadSession,
        active_agents: List[AgentProfile],
        max_turns: int = 4
    ) -> List[ChatMessage]:
        """
        Runs the automated conversation cycle until Moderator concludes or pauses.
        """
        executed_turns: List[ChatMessage] = []

        for turn_idx in range(1, max_turns + 1):
            history = self.db.get_session_messages(session.id, limit=20)
            decision: ModeratorDecision = self.moderator.evaluate_next_turn(
                topic=session.topic,
                active_agents=active_agents,
                chat_history=history,
                current_turn_count=turn_idx,
                max_turn_budget=max_turns
            )

            logger.info(f"Moderator Turn {turn_idx}: Action={decision.action}, NextSpeaker={decision.next_speaker} ({decision.reasoning})")

            if decision.action == "conclude":
                self.generate_executive_summary(session, active_agents)
                break
            elif decision.action == "wait_for_user":
                break
            elif decision.action == "speak" and decision.next_speaker:
                msg = self.execute_turn(session, active_agents, decision.next_speaker)
                executed_turns.append(msg)

        return executed_turns

# Singleton instance
war_room_engine = WarRoomEngine()
