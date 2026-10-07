# ⚡ SYNAPSE: Dynamic On-Demand Multi-Agent Engine

**Synapse** is an on-demand, meta-agent orchestration system powered by **Groq** ultra-fast inference, **Supabase** persistent memory, and **Slack** as a real-time collaborative war room.

Instead of fixed, hardcoded agents, Synapse dynamically recruits, designs, and instantiates senior AI personas with specific industry backgrounds (e.g. 20-year researchers, startup CTOs, GTM leads, security auditors) on the fly in response to your prompts.

---

## 🏗️ Architecture

- **The Recruiter (Meta-Agent):** Generates structured Pydantic schemas for domain expert agents using `llama-3.1-8b-instant` (~800 tok/s).
- **The War Room (GroupChat):** Coordinates multi-agent debates in dedicated Slack threads.
- **Smart Moderator:** Reads conversation flow and dynamically delegates speaking turns to agents or wraps up when consensus is reached.
- **Deep Domain Reasoning:** `llama-3.3-70b-versatile` powers deep technical arguments and Python code generation.
- **Autonomous Python Sandbox:** Executes generated code in a secure subprocess/E2B micro-VM sandbox and returns stdout/plots to Slack.
- **Supabase Memory & Persistent Roster:** Saves agent personas and past session memories for long-term re-summoning via `@mentions`.
- **Groq Multi-Key Rotation Pool:** Prevents 429 rate limit errors by rotating across multiple API keys.

---

## 📁 Project Structure

```
synapse/
├── .env.example             # Configuration template
├── .gitignore
├── README.md
├── requirements.txt         # Dependencies (groq, slack-bolt, supabase, etc.)
├── config/                  # Settings and Groq multi-key manager
├── core/                    # Spawner, Moderator, GroupChat, and Roster
├── tools/                   # Python sandbox and search tools
└── slack/                   # Slack Bolt app and thread manager
```

---

## 🚀 Quickstart Guide

1. Clone or navigate to the repository:
   ```bash
   cd synapse
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Populate `.env` with your Supabase and Slack tokens.

4. Start the Synapse engine:
   ```bash
   python main.py
   ```
