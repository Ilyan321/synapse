import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from config.groq_client import groq_engine
from config.settings import settings

logger = logging.getLogger("synapse.qa")

class QAClarification(BaseModel):
    """Structured evaluation of whether user requirements need clarifying questions before generation."""
    needs_clarification: bool = Field(
        description="True if the prompt is missing critical technical parameters that could cause hallucinations."
    )
    clarifying_questions: List[str] = Field(
        default_factory=list,
        description="2-3 targeted multiple-choice or short questions for the user to confirm exact tech requirements."
    )
    recommended_defaults: List[str] = Field(
        default_factory=list,
        description="Sensible defaults the agent will use if the user decides to skip."
    )

class QAAgent:
    """
    Quality Assurance & Requirement Clarification Specialist.
    Analyzes high-stakes coding/architecture missions to prevent hallucinations and misaligned code generation.
    """

    def __init__(self):
        self.engine = groq_engine

    def assess_prompt(self, user_prompt: str) -> QAClarification:
        """
        Assesses if a prompt requires clarification on hardware, dataset, model choice, or architecture.
        """
        system_prompt = (
            "You are the SYNAPSE QA & Scope Validation Lead.\n"
            "Your job is to inspect user engineering requests (e.g. machine learning pipelines, cloud architectures, "
            "database schemas, security scanners) and determine if critical parameters are missing.\n\n"
            "CRITERIA FOR CLARIFICATION:\n"
            "- If the prompt is broad or high-stakes (e.g. 'fine tune text to image', 'build database pipeline') without specifying exact dataset paths, target hardware/GPU, or model variants, set needs_clarification=True.\n"
            "- Provide 2 to 3 concise, high-signal questions with recommended defaults (e.g. 1. Model: SD 1.5 vs SDXL vs FLUX? 2. Training method: LoRA vs Full Fine-Tuning? 3. Dataset source?).\n"
            "- If the prompt is already detailed or self-contained, set needs_clarification=False."
        )

        user_message = f"USER REQUEST: \"{user_prompt}\"\n\nEvaluate and generate clarifying questions if needed."

        try:
            decision: QAClarification = self.engine.generate_structured(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_model=QAClarification,
                model=settings.groq_router_model
            )
            return decision
        except Exception as e:
            logger.error(f"QA Agent assessment error: {e}")
            return QAClarification(needs_clarification=False)

qa_agent = QAAgent()
