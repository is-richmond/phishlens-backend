"""
Generation Service

Orchestrates the full generation pipeline:
  1. Construct prompt (PromptService)
  2. Generate message (LLMService)
  3. Parse and extract subject/body
  4. Evaluate realism (LLMService — secondary call)
  5. Store results
"""

import re
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.models.template import Template
from app.models.generation import Generation
from app.services.llm_service import llm_service
from app.services.prompt_service import prompt_service
from app.core.logging import get_logger

logger = get_logger("generation_service")

WATERMARK = "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]"


class GenerationService:
    """Orchestrates phishing message generation and evaluation."""

    def generate(
        self,
        db: Session,
        scenario: Scenario,
        template: Optional[Template],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_variant: str = "gemini-2.0-flash",
    ) -> Generation:
        """Run the full generation + evaluation pipeline.

        Args:
            db: Database session.
            scenario: The scenario to generate for.
            template: Optional template to use.
            temperature: LLM creativity parameter.
            max_tokens: Maximum output length.
            model_variant: Gemini model variant.

        Returns:
            The created Generation record with scores.
        """
        # Step 1: Construct prompts
        system_prompt, user_prompt = prompt_service.construct_prompt(
            scenario, template
        )

        # Step 2: Generate the phishing message
        gen_result = llm_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_variant=model_variant,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        generated_text = gen_result["text"]

        # Step 3: Parse subject and body
        subject, body = self._extract_subject_body(
            generated_text, scenario.communication_channel
        )

        # Ensure watermark is present
        if WATERMARK not in body:
            body = f"{body}\n\n{WATERMARK}"

        # Step 4: Enforce placeholder data (safety check)
        body = self._enforce_placeholders(body)

        # Step 5: Evaluate realism (secondary LLM call)
        scenario_context = prompt_service.build_scenario_context_summary(scenario)
        try:
            eval_result = llm_service.evaluate(
                generated_message=f"Subject: {subject}\n\n{body}" if subject else body,
                scenario_context=scenario_context,
                model_variant=model_variant,
            )
        except Exception as e:
            logger.warning("Evaluation failed, using defaults", error=str(e))
            eval_result = {
                "overall_score": None,
                "dimensional_scores": None,
                "analysis": "Evaluation could not be completed.",
                "generation_time_ms": 0,
            }

        total_time_ms = gen_result["generation_time_ms"] + eval_result.get(
            "generation_time_ms", 0
        )

        # Step 6: Create and store Generation record
        generation = Generation(
            scenario_id=scenario.id,
            template_id=template.id if template else None,
            input_parameters={
                "temperature": temperature,
                "max_tokens": max_tokens,
                "model_variant": model_variant,
                "system_prompt_preview": system_prompt[:200] + "...",
                "user_prompt_preview": user_prompt[:200] + "...",
            },
            generated_subject=subject,
            generated_text=body,
            model_used=gen_result["model_used"],
            overall_score=eval_result.get("overall_score"),
            dimensional_scores=eval_result.get("dimensional_scores"),
            evaluation_analysis=eval_result.get("analysis"),
            watermark=WATERMARK,
            generation_time_ms=round(total_time_ms, 2),
        )

        db.add(generation)
        db.commit()
        db.refresh(generation)

        logger.info(
            "Generation complete",
            generation_id=str(generation.id),
            score=eval_result.get("overall_score"),
            time_ms=total_time_ms,
        )

        return generation

    def _extract_subject_body(
        self, text: str, channel: str
    ) -> tuple[Optional[str], str]:
        """Extract subject line and body from the generated text.

        For email channel, look for a Subject: line.
        For other channels, there's no subject line.
        """
        if channel != "email":
            return None, text.strip()

        # Try to extract "Subject: ..." from the generated text
        subject_match = re.search(
            r"(?:^|\n)\s*(?:Subject|SUBJECT|subject)\s*:\s*(.+?)(?:\n|$)",
            text,
        )
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove the subject line from body
            body = text[: subject_match.start()] + text[subject_match.end() :]
            body = body.strip()
            return subject, body

        return None, text.strip()

    def _enforce_placeholders(self, text: str) -> str:
        """Ensure no functional URLs exist — replace with safe placeholders.

        Block any real-looking URLs that aren't using the safe domain.
        """
        # Replace any URLs that aren't our safe domain
        url_pattern = re.compile(
            r"https?://(?!example-phishing-domain\.test)[^\s\]\)>\"']+",
            re.IGNORECASE,
        )
        text = url_pattern.sub(
            "https://example-phishing-domain.test/[LINK]", text
        )

        return text


# Singleton instance
generation_service = GenerationService()
