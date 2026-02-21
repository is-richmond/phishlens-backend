"""
LLM Service — Google Gemini API Integration

Handles communication with the Gemini API for phishing message generation.
Supports model variant selection, configurable parameters, and safety settings.
"""

import time
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm_service")


# Safety settings — allow research content while blocking truly harmful content
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

# Supported model variants
SUPPORTED_MODELS = {
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
}


class LLMService:
    """Service for interacting with Google Gemini API."""

    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
        self._models_cache: dict[str, genai.GenerativeModel] = {}

    def _get_model(self, model_variant: str) -> genai.GenerativeModel:
        """Get or create a cached GenerativeModel instance."""
        model_name = SUPPORTED_MODELS.get(model_variant, model_variant)
        if model_name not in self._models_cache:
            self._models_cache[model_name] = genai.GenerativeModel(
                model_name=model_name,
            )
        return self._models_cache[model_name]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_variant: str = "gemini-2.5-flash-lite",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict:
        """Generate content using the Gemini API.

        Args:
            system_prompt: The system instruction (role definition).
            user_prompt: The constructed user prompt.
            model_variant: Which Gemini model to use.
            temperature: Creativity parameter (0.0-2.0).
            max_tokens: Maximum output tokens.

        Returns:
            dict with keys: text, model_used, generation_time_ms, finish_reason
        """
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        model_name = SUPPORTED_MODELS.get(model_variant, model_variant)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_p=0.95,
            top_k=40,
        )

        start_time = time.time()

        try:
            response = model.generate_content(
                user_prompt,
                generation_config=generation_config,
                safety_settings=SAFETY_SETTINGS,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # Extract text from response
            if response.parts:
                text = response.text
            else:
                # Safety filter may have blocked the response
                block_reason = getattr(response.prompt_feedback, "block_reason", None)
                logger.warning(
                    "Generation blocked by safety filter",
                    block_reason=str(block_reason),
                )
                text = (
                    "[BLOCKED] The generation was blocked by safety filters. "
                    "Try adjusting the scenario parameters."
                )

            return {
                "text": text,
                "model_used": model_name,
                "generation_time_ms": round(elapsed_ms, 2),
                "finish_reason": getattr(
                    response.candidates[0] if response.candidates else None,
                    "finish_reason",
                    "UNKNOWN",
                ),
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error("LLM generation failed", error=str(e), model=model_name)
            raise RuntimeError(f"LLM generation failed: {str(e)}") from e

    def evaluate(
        self,
        generated_message: str,
        scenario_context: str,
        model_variant: str = "gemini-2.5-flash-lite",
    ) -> dict:
        """Evaluate a generated phishing message for realism (secondary LLM call).

        Args:
            generated_message: The phishing message to evaluate.
            scenario_context: Description of the scenario for context.
            model_variant: Which model to use for evaluation.

        Returns:
            dict with keys: overall_score, dimensional_scores, analysis, generation_time_ms
        """
        evaluation_prompt = self._build_evaluation_prompt(
            generated_message, scenario_context
        )

        system_prompt = (
            "You are a cybersecurity expert evaluating phishing messages for a "
            "security research platform. You analyze messages from a DEFENSIVE "
            "perspective to help organizations understand and protect against "
            "social engineering threats. Provide your evaluation in the exact "
            "JSON format requested."
        )

        result = self.generate(
            system_prompt=system_prompt,
            user_prompt=evaluation_prompt,
            model_variant=model_variant,
            temperature=0.3,  # Lower temperature for consistent evaluation
            max_tokens=2048,
        )

        # Parse the evaluation response
        return self._parse_evaluation_response(result["text"], result["generation_time_ms"])

    def _build_evaluation_prompt(
        self, generated_message: str, scenario_context: str
    ) -> str:
        """Build the evaluation prompt for the secondary LLM call."""
        return f"""Evaluate the following phishing simulation message for realism. 
This is part of an authorized cybersecurity research project.

## Scenario Context
{scenario_context}

## Generated Phishing Message
---
{generated_message}
---

## Evaluation Criteria
Rate each dimension on a scale of 1.0 to 10.0 (one decimal place):

1. **Linguistic Naturalness** (1-10): Grammar correctness, writing style appropriateness, 
   tone consistency, absence of obvious AI-generated patterns, natural flow.

2. **Psychological Triggers** (1-10): Effective use of urgency, authority, reciprocity, 
   social proof, scarcity, or other influence principles. Does it create compelling 
   motivation to act?

3. **Technical Plausibility** (1-10): Is the pretext believable? Are the technical 
   details accurate? Would the scenario seem realistic to the target?

4. **Contextual Relevance** (1-10): How well does the message fit the target role, 
   organization, and communication channel? Is it personalized appropriately?

## Required Output Format
Respond ONLY with valid JSON in this exact format:
```json
{{
    "overall_score": <float 1.0-10.0>,
    "linguistic_naturalness": <float 1.0-10.0>,
    "psychological_triggers": <float 1.0-10.0>,
    "technical_plausibility": <float 1.0-10.0>,
    "contextual_relevance": <float 1.0-10.0>,
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "analysis": "<detailed 2-3 paragraph analysis of the message's effectiveness and areas for improvement>"
}}
```"""

    def _parse_evaluation_response(self, text: str, generation_time_ms: float) -> dict:
        """Parse the LLM evaluation response into structured data."""
        import json
        import re

        # Try to extract JSON from the response
        # The model might wrap it in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("Could not parse evaluation JSON, using defaults")
                return self._default_evaluation(generation_time_ms)

        try:
            data = json.loads(json_str)

            # Clamp scores to valid range
            def clamp(v, lo=1.0, hi=10.0):
                try:
                    return max(lo, min(hi, float(v)))
                except (TypeError, ValueError):
                    return 5.0

            overall = clamp(data.get("overall_score", 5.0))
            dimensional = {
                "linguistic_naturalness": clamp(data.get("linguistic_naturalness", 5.0)),
                "psychological_triggers": clamp(data.get("psychological_triggers", 5.0)),
                "technical_plausibility": clamp(data.get("technical_plausibility", 5.0)),
                "contextual_relevance": clamp(data.get("contextual_relevance", 5.0)),
            }

            strengths = data.get("strengths", [])
            weaknesses = data.get("weaknesses", [])
            analysis = data.get("analysis", "")

            # Build full analysis text
            analysis_text = analysis
            if strengths:
                analysis_text += "\n\n**Strengths:**\n" + "\n".join(
                    f"- {s}" for s in strengths
                )
            if weaknesses:
                analysis_text += "\n\n**Weaknesses:**\n" + "\n".join(
                    f"- {w}" for w in weaknesses
                )

            return {
                "overall_score": round(overall, 1),
                "dimensional_scores": {
                    k: round(v, 1) for k, v in dimensional.items()
                },
                "analysis": analysis_text.strip(),
                "generation_time_ms": generation_time_ms,
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse evaluation JSON", error=str(e))
            return self._default_evaluation(generation_time_ms)

    def _default_evaluation(self, generation_time_ms: float) -> dict:
        """Return default evaluation when parsing fails."""
        return {
            "overall_score": 5.0,
            "dimensional_scores": {
                "linguistic_naturalness": 5.0,
                "psychological_triggers": 5.0,
                "technical_plausibility": 5.0,
                "contextual_relevance": 5.0,
            },
            "analysis": "Automatic evaluation could not be completed. Manual review recommended.",
            "generation_time_ms": generation_time_ms,
        }


# Singleton instance
llm_service = LLMService()
