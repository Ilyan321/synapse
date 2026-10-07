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
            f"=== YOUR DEEP PERSONA ===\n"
            f"{agent.system_prompt}\n\n"
            f"=== WAR ROOM CONTEXT ===\n"
            f"TOPIC: {topic}\n"
            f"COLLEAGUES IN ROOM: {other_agents_str}\n\n"
            f"CRITICAL SLACK UX RULES (NON-NEGOTIABLE):\n"
            f"1. ULTRA-CONCISE: Write only 2 to 3 punchy, high-signal sentences (strictly under 80 words).\n"
            f"2. NO MARKDOWN TABLES: Never write | col | tables. Use bullet points (• *Key*: Value) if listing.\n"
            f"3. DIRECT & OPINIONATED: Directly debate colleagues (@Name) with bottom-line metrics and trade-offs.\n"
            f"4. PYTHON BENCHMARKS: If calculating metrics/economics, write a 2-line Python script that prints the final number.\n"
            f"5. Do NOT prefix your message with '{agent.name}:'—speak directly."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Append last 8 messages as dialogue history
        for msg in chat_history[-8:]:
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

        history = self.db.get_session_messages(session.id, limit=15)
        messages = self.build_agent_turn_prompt(agent, session.topic, active_agents, history)

        logger.info(f"Agent {agent.name} thinking via {settings.groq_agent_model}...")
        response_text = self.engine.chat_completion(
            messages=messages,
            model=settings.groq_agent_model,
            temperature=0.6,
            max_tokens=3500
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

        # 3. Autonomous Python Sandbox Execution (Silent unless stdout has value)
        from tools.python_runner import python_sandbox
        code_snippet = python_sandbox.extract_python_code(response_text)
        if code_snippet:
            logger.info(f"Detected Python code block from {agent.name}. Executing in sandbox...")
            exec_res = python_sandbox.execute_code(code_snippet)
            
            output_str = exec_res.get("stdout", "").strip()
            if exec_res.get("success") and output_str:
                tool_output_content = f"📊 *Calculated Metric:* `{output_str}`"
                
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

                # Post clean 1-line badge to Slack
                self.slack.post_message(
                    text=tool_output_content,
                    channel=session.slack_channel_id,
                    thread_ts=session.slack_thread_ts,
                    username=f"{agent.name} (Code Runner)",
                    icon_emoji=":gear:"
                )

            # 4. Autonomous Artifact & Document File Delivery
            topic_lower = session.topic.lower()
            if any(kw in topic_lower for kw in ["notebook", "ipynb", "script", "file", ".py", "pipeline", "model"]):
                from core.artifacts import artifact_generator
                safe_title = "".join(c if c.isalnum() else "_" for c in session.topic[:20]).strip("_")
                if "ipynb" in topic_lower or "notebook" in topic_lower:
                    nb_path = artifact_generator.create_jupyter_notebook(
                        filename=f"{safe_title}_{agent.name.lower()}.ipynb",
                        code_cells=[code_snippet],
                        markdown_cells=[f"# {session.topic}\n\nGenerated by **{agent.name}** ({agent.role})\n_Self-contained, Kaggle/Colab-ready training notebook with checkpointing._"]
                    )
                    artifact_generator.upload_to_slack(
                        filepath=nb_path,
                        channel_id=session.slack_channel_id,
                        thread_ts=session.slack_thread_ts,
                        title=f"{agent.name}'s Training Notebook",
                        initial_comment=f"📓 *Jupyter Notebook Artifact Created:* `{nb_path.name}`"
                    )
                else:
                    py_path = artifact_generator.create_python_script(
                        filename=f"{safe_title}_{agent.name.lower()}.py",
                        code=code_snippet,
                        header_doc=f"Mission: {session.topic}\nAuthor: {agent.name} ({agent.role})"
                    )
                    artifact_generator.upload_to_slack(
                        filepath=py_path,
                        channel_id=session.slack_channel_id,
                        thread_ts=session.slack_thread_ts,
                        title=f"{agent.name}'s Python Script",
                        initial_comment=f"🐍 *Python Pipeline Artifact Created:* `{py_path.name}`"
                    )

        return saved_msg

    def generate_executive_summary(
        self,
        session: ThreadSession,
        active_agents: List[AgentProfile]
    ) -> str:
        """
        Synthesizes the entire multi-agent discussion into a concise, 15-second read Executive Flash Brief.
        """
        history = self.db.get_session_messages(session.id, limit=30)
        transcript = "\n\n".join([
            f"**{m.sender_name}** ({m.sender_role or m.sender_type}):\n{m.content}"
            for m in history
        ])

        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "You are the SYNAPSE Chief of Staff.\n"
                    "Synthesize the war room debate into a punchy, 15-second read Executive Flash Brief for Slack.\n\n"
                    "FORMAT RULES:\n"
                    "- Maximum 15-20 lines total.\n"
                    "- NO markdown tables.\n"
                    "- Use clean bullet points and bold section headers:\n"
                    "  🎯 *Core Problem & Solution* (2 bullets)\n"
                    "  ⚖️ *Key Strategic Decisions* (2-3 bullets)\n"
                    "  🚀 *Immediate Next Steps* (2-3 bullets with owners)"
                )
            },
            {
                "role": "user",
                "content": (
                    f"MISSION: \"{session.topic}\"\n\n"
                    f"SPECIALISTS: {', '.join([f'{a.name} ({a.role})' for a in active_agents])}\n\n"
                    f"TRANSCRIPT:\n{transcript}\n\n"
                    f"Generate the Executive Flash Brief."
                )
            }
        ]

        summary_md = self.engine.chat_completion(
            messages=summary_prompt,
            model=settings.groq_agent_model,
            temperature=0.3,
            max_tokens=1500
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
        max_turns: int = 2
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
                # Prompt user for input
                self.slack.post_message(
                    text=f"💡 *Founder Decision:* {decision.reasoning}\n_Reply in thread to steer the team, or say \"Wrap up\" to conclude._",
                    channel=session.slack_channel_id,
                    thread_ts=session.slack_thread_ts,
                    username="Synapse Moderator",
                    icon_emoji=":speech_balloon:"
                )
                break
            elif decision.action == "speak" and decision.next_speaker:
                msg = self.execute_turn(session, active_agents, decision.next_speaker)
                executed_turns.append(msg)

        return executed_turns

# Singleton instance
war_room_engine = WarRoomEngine()
