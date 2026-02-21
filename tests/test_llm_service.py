"""
Sprint 5.1.4 — LLM Service Tests (Mocked)

Covers: generate(), evaluate(), response parsing, score clamping,
        default evaluation fallback, model variant validation.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.llm_service import LLMService, SUPPORTED_MODELS


def _mock_genai_response(text: str, finish_reason="STOP"):
    """Build a mock Gemini response object."""
    response = MagicMock()
    response.text = text
    response.parts = [MagicMock()]
    candidate = MagicMock()
    candidate.finish_reason = finish_reason
    response.candidates = [candidate]
    return response


# ── Model catalogue ──────────────────────────────────────────────────

class TestSupportedModels:

    def test_has_flash_lite(self):
        assert "gemini-2.5-flash-lite" in SUPPORTED_MODELS

    def test_has_flash(self):
        assert "gemini-2.5-flash" in SUPPORTED_MODELS

    def test_has_pro(self):
        assert "gemini-2.5-pro" in SUPPORTED_MODELS


# ── generate() ───────────────────────────────────────────────────────

class TestLLMGenerate:

    @patch("app.services.llm_service.genai")
    def test_generate_returns_dict(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_genai_response(
            "Subject: Test\n\nDear [TARGET_NAME], reset your password."
        )
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig.return_value = MagicMock()

        svc = LLMService()
        result = svc.generate(
            system_prompt="You are an assistant.",
            user_prompt="Generate a phishing email.",
            model_variant="gemini-2.5-flash-lite",
        )

        assert "text" in result
        assert "model_used" in result
        assert "generation_time_ms" in result
        assert isinstance(result["generation_time_ms"], float)

    @patch("app.services.llm_service.genai")
    def test_generate_blocked_response(self, mock_genai):
        response = MagicMock()
        response.parts = []
        response.prompt_feedback.block_reason = "SAFETY"
        response.candidates = []
        mock_model = MagicMock()
        mock_model.generate_content.return_value = response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig.return_value = MagicMock()

        svc = LLMService()
        result = svc.generate("sys", "user")
        assert "[BLOCKED]" in result["text"]

    @patch("app.services.llm_service.genai")
    def test_generate_raises_on_api_error(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error 500")
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig.return_value = MagicMock()

        svc = LLMService()
        with pytest.raises(RuntimeError, match="LLM generation failed"):
            svc.generate("sys", "user")

    def test_generate_no_api_key(self):
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.gemini_api_key = None
            svc = LLMService()
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                svc.generate("sys", "user")


# ── evaluate() ───────────────────────────────────────────────────────

class TestLLMEvaluate:

    VALID_EVAL_JSON = json.dumps({
        "overall_score": 8.2,
        "linguistic_naturalness": 8.5,
        "psychological_triggers": 7.8,
        "technical_plausibility": 8.0,
        "contextual_relevance": 8.5,
        "strengths": ["Good urgency", "Natural tone"],
        "weaknesses": ["Slightly long"],
        "analysis": "Well-crafted message with realistic tone.",
    })

    @patch("app.services.llm_service.genai")
    def test_evaluate_parses_json(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_genai_response(
            f"```json\n{self.VALID_EVAL_JSON}\n```"
        )
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig.return_value = MagicMock()

        svc = LLMService()
        result = svc.evaluate("Test message", "Context")

        assert result["overall_score"] == 8.2
        assert "linguistic_naturalness" in result["dimensional_scores"]
        assert isinstance(result["analysis"], str)

    @patch("app.services.llm_service.genai")
    def test_evaluate_raw_json_no_code_block(self, mock_genai):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_genai_response(
            self.VALID_EVAL_JSON
        )
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig.return_value = MagicMock()

        svc = LLMService()
        result = svc.evaluate("Msg", "Ctx")
        assert result["overall_score"] == 8.2


# ── _parse_evaluation_response() ─────────────────────────────────────

class TestEvaluationParsing:

    def test_score_clamping_high(self):
        svc = LLMService()
        data = json.dumps({
            "overall_score": 15.0,
            "linguistic_naturalness": 12.0,
            "psychological_triggers": 5.0,
            "technical_plausibility": 5.0,
            "contextual_relevance": 5.0,
            "analysis": "Test",
        })
        result = svc._parse_evaluation_response(f"```json\n{data}\n```", 100.0)
        assert result["overall_score"] == 10.0
        assert result["dimensional_scores"]["linguistic_naturalness"] == 10.0

    def test_score_clamping_low(self):
        svc = LLMService()
        data = json.dumps({
            "overall_score": -2.0,
            "linguistic_naturalness": 0.0,
            "psychological_triggers": 5.0,
            "technical_plausibility": 5.0,
            "contextual_relevance": 5.0,
            "analysis": "Test",
        })
        result = svc._parse_evaluation_response(f"```json\n{data}\n```", 100.0)
        assert result["overall_score"] == 1.0
        assert result["dimensional_scores"]["linguistic_naturalness"] == 1.0

    def test_default_evaluation_on_invalid_json(self):
        svc = LLMService()
        result = svc._parse_evaluation_response("This is not JSON at all.", 200.0)
        assert result["overall_score"] == 5.0
        assert result["generation_time_ms"] == 200.0

    def test_default_evaluation_direct(self):
        svc = LLMService()
        result = svc._default_evaluation(300.0)
        assert result["overall_score"] == 5.0
        assert all(
            v == 5.0 for v in result["dimensional_scores"].values()
        )

    def test_strengths_and_weaknesses_in_analysis(self):
        svc = LLMService()
        data = json.dumps({
            "overall_score": 7.0,
            "linguistic_naturalness": 7.0,
            "psychological_triggers": 7.0,
            "technical_plausibility": 7.0,
            "contextual_relevance": 7.0,
            "strengths": ["Good structure"],
            "weaknesses": ["Too verbose"],
            "analysis": "Decent quality.",
        })
        result = svc._parse_evaluation_response(data, 100.0)
        assert "Good structure" in result["analysis"]
        assert "Too verbose" in result["analysis"]
