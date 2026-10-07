#!/usr/bin/env python3
"""
Synapse Synthetic Fine-Tuning Dataset Generator.
Generates multi-agent reasoning, role-play dialogue, tool execution,
and executive synthesis data formatted for LLM fine-tuning (JSONL).
"""

import os
import sys
import json
import time
import argparse
import logging
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from config.groq_client import groq_engine
from core.spawner import spawner_service
from core.models import AgentProfile, ThreadSession, ChatMessage
from tools.python_runner import python_sandbox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("synapse.finetune_gen")

DEFAULT_SEED_TOPICS = [
    "Design an eBPF-based real-time container intrusion detection system for Kubernetes",
    "Architect an autonomous multi-currency FX settlement engine with sub-5ms finality",
    "Build a self-hosted vector database search engine with hybrid BM25 + dense retrieval",
    "Simulate a Series-A B2B DevOps startup pivoting to an open-core developer tool",
    "Design a zero-knowledge proof roll-up sequencer for decentralized orderbooks",
    "Architect a localized offline speech-to-text pipeline running on edge Apple Silicon"
]

def generate_finetuning_sample(mission_prompt: str) -> Dict[str, Any]:
    """
    Simulates a full Synapse session for a mission and converts it to a training conversation format.
    """
    logger.info(f"Generating synthetic session for topic: '{mission_prompt[:50]}...'")
    
    # 1. Recruit Specialists
    recruitment = spawner_service.assemble_team_for_topic(
        user_prompt=mission_prompt,
        target_team_size=2,
        force_fresh=True
    )
    agents = recruitment.newly_created_agents
    if len(agents) < 2:
        raise ValueError("Need at least 2 recruited agents.")

    agent_a, agent_b = agents[0], agents[1]
    
    # 2. Simulate Multi-Turn Conversation
    messages_transcript = []
    
    # User opening
    messages_transcript.append({
        "role": "user",
        "content": f"War Room Mission: {mission_prompt}"
    })

    # Agent A Turn
    prompt_a = (
        f"You are {agent_a.name} ({agent_a.role}).\n"
        f"Background: {agent_a.system_prompt}\n"
        f"Mission: {mission_prompt}\n"
        f"Rules: Write 2-3 punchy sentences with concrete architectural choices. If doing calculations, include a minimal Python snippet."
    )
    resp_a = groq_engine.chat_completion(
        messages=[{"role": "system", "content": prompt_a}, {"role": "user", "content": mission_prompt}],
        model=settings.groq_agent_model,
        temperature=0.7
    )
    messages_transcript.append({
        "role": "assistant",
        "name": agent_a.name,
        "content": resp_a
    })

    # Execute Python if any in Agent A
    code_a = python_sandbox.extract_python_code(resp_a)
    if code_a:
        exec_a = python_sandbox.execute_code(code_a)
        if exec_a.get("stdout"):
            messages_transcript.append({
                "role": "tool",
                "name": "python_sandbox",
                "content": f"Calculated: {exec_a.get('stdout')}"
            })

    # Agent B Turn
    prompt_b = (
        f"You are {agent_b.name} ({agent_b.role}).\n"
        f"Background: {agent_b.system_prompt}\n"
        f"Mission: {mission_prompt}\n"
        f"Colleague {agent_a.name} said: {resp_a}\n"
        f"Rules: Write 2-3 punchy sentences directly challenging or complementing {agent_a.name}'s numbers/stack."
    )
    resp_b = groq_engine.chat_completion(
        messages=[{"role": "system", "content": prompt_b}, {"role": "user", "content": f"{agent_a.name}: {resp_a}"}],
        model=settings.groq_agent_model,
        temperature=0.7
    )
    messages_transcript.append({
        "role": "assistant",
        "name": agent_b.name,
        "content": resp_b
    })

    # Execute Python if any in Agent B
    code_b = python_sandbox.extract_python_code(resp_b)
    if code_b:
        exec_b = python_sandbox.execute_code(code_b)
        if exec_b.get("stdout"):
            messages_transcript.append({
                "role": "tool",
                "name": "python_sandbox",
                "content": f"Calculated: {exec_b.get('stdout')}"
            })

    # Executive Briefing
    summary_prompt = [
        {"role": "system", "content": "You are the Synapse Chief of Staff. Generate a 15-line Executive Flash Brief with Core Solution, Key Decisions, and Action Items."},
        {"role": "user", "content": f"Mission: {mission_prompt}\nDebate:\n{agent_a.name}: {resp_a}\n{agent_b.name}: {resp_b}"}
    ]
    summary_brief = groq_engine.chat_completion(
        messages=summary_prompt,
        model=settings.groq_agent_model,
        temperature=0.3
    )

    messages_transcript.append({
        "role": "assistant",
        "name": "Synapse_Orchestrator",
        "content": summary_brief
    })

    return {
        "mission": mission_prompt,
        "specialists": [{"name": a.name, "role": a.role} for a in agents],
        "messages": messages_transcript
    }

def main():
    parser = argparse.ArgumentParser(description="Generate Synapse fine-tuning synthetic dataset.")
    parser.add_argument("--output", type=str, default="finetune_dataset.jsonl", help="Output JSONL file path")
    parser.add_argument("--count", type=int, default=3, help="Number of synthetic samples to generate")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("🚀 SYNAPSE FINE-TUNING DATASET GENERATOR")
    print(f"📁 Output Destination: {args.output}")
    print(f"🔢 Generating {args.count} high-signal multi-agent training sessions...")
    print("="*70 + "\n")

    topics = DEFAULT_SEED_TOPICS[:args.count]
    while len(topics) < args.count:
        topics.append(f"Simulate deep tech startup topic #{len(topics)+1}")

    samples = []
    with open(args.output, "w", encoding="utf-8") as f:
        for idx, topic in enumerate(topics, 1):
            print(f"[{idx}/{args.count}] Synthesizing mission: '{topic}'...")
            try:
                sample = generate_finetuning_sample(topic)
                f.write(json.dumps(sample) + "\n")
                f.flush()
                samples.append(sample)
                print(f"   ✅ Successfully exported sample with {len(sample['messages'])} turns.")
            except Exception as e:
                print(f"   ❌ Error synthesizing sample: {e}")

    print("\n" + "="*70)
    print(f"🎉 DATASET COMPLETE: {len(samples)} samples written to {args.output}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
