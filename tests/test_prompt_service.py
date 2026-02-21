"""
Sprint 5.1.3 — Prompt Service Tests

Covers: three-tier pipeline construction, template skeleton filling,
        language overrides (Russian, Kazakh), channel formatting,
        persona mapping, scenario context summary.
"""

import uuid
from unittest.mock import MagicMock

import pytest

from app.services.prompt_service import (
    PromptService,
    prompt_service,
    TARGET_PERSONAS,
    PRETEXT_DESCRIPTIONS,
    URGENCY_LABELS,
    CHANNEL_FORMATS,
)
from app.models.scenario import Scenario
from app.models.template import Template


def _make_scenario(**overrides) -> Scenario:
    """Factory to build a Scenario-like object for testing."""
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Test Scenario",
        description="Scenario for testing prompt construction",
        target_role="HR Manager",
        target_department="Human Resources",
        organization_context="A large fintech company in Almaty",
        pretext_category="credential_phishing",
        pretext_description="Password expiration warning",
        urgency_level=3,
        communication_channel="email",
        language="english",
    )
    defaults.update(overrides)
    s = MagicMock(spec=Scenario)
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _make_template(**overrides) -> Template:
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Custom Template",
        category="credential_phishing",
        system_prompt="You are a security research assistant for PhishLens.",
        user_prompt_skeleton=(
            "Generate a {{ATTACK_CATEGORY}} message targeting "
            "{{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}. "
            "Urgency: {{URGENCY_LEVEL}}. Channel: {{CHANNEL}}."
        ),
        is_predefined=False,
        is_public=False,
    )
    defaults.update(overrides)
    t = MagicMock(spec=Template)
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


# ── Data constants ───────────────────────────────────────────────────

class TestDataConstants:

    def test_all_categories_have_descriptions(self):
        expected = {
            "credential_phishing", "business_email_compromise",
            "quishing", "spear_phishing", "whaling", "smishing",
        }
        assert expected.issubset(PRETEXT_DESCRIPTIONS.keys())

    def test_urgency_labels_cover_1_to_5(self):
        for level in range(1, 6):
            assert level in URGENCY_LABELS

    def test_channel_formats_exist(self):
        for ch in ("email", "sms", "internal_chat"):
            assert ch in CHANNEL_FORMATS

    def test_target_personas_have_context(self):
        for key, info in TARGET_PERSONAS.items():
            assert "label" in info
            assert "context" in info


# ── Prompt construction (no template) ────────────────────────────────

class TestPromptConstructionDefault:

    def test_returns_tuple_of_two_strings(self):
        scenario = _make_scenario()
        sys_prompt, user_prompt = prompt_service.construct_prompt(scenario)
        assert isinstance(sys_prompt, str)
        assert isinstance(user_prompt, str)
        assert len(sys_prompt) > 50
        assert len(user_prompt) > 50

    def test_system_prompt_mentions_channel(self):
        scenario = _make_scenario(communication_channel="sms")
        sys_prompt, _ = prompt_service.construct_prompt(scenario)
        assert "sms" in sys_prompt.lower()

    def test_user_prompt_contains_target_role(self):
        scenario = _make_scenario(target_role="Finance Manager")
        _, user_prompt = prompt_service.construct_prompt(scenario)
        assert "Finance Manager" in user_prompt

    def test_user_prompt_contains_category(self):
        scenario = _make_scenario(pretext_category="business_email_compromise")
        _, user_prompt = prompt_service.construct_prompt(scenario)
        assert "Business Email Compromise" in user_prompt

    def test_user_prompt_contains_org_context(self):
        scenario = _make_scenario(organization_context="A bank in Kazakhstan")
        _, user_prompt = prompt_service.construct_prompt(scenario)
        assert "bank in Kazakhstan" in user_prompt

    def test_no_org_context_still_works(self):
        scenario = _make_scenario(organization_context=None)
        sys_p, user_p = prompt_service.construct_prompt(scenario)
        assert len(sys_p) > 0 and len(user_p) > 0


# ── Language overrides ───────────────────────────────────────────────

class TestLanguageOverride:

    def test_english_no_override(self):
        scenario = _make_scenario(language="english")
        sys_p, user_p = prompt_service.construct_prompt(scenario)
        assert "Русский" not in sys_p
        assert "Қазақ" not in sys_p

    def test_russian_override(self):
        scenario = _make_scenario(language="russian")
        sys_p, user_p = prompt_service.construct_prompt(scenario)
        assert "Русский" in sys_p or "Russian" in sys_p
        assert "Русский" in user_p or "Russian" in user_p

    def test_kazakh_override(self):
        scenario = _make_scenario(language="kazakh")
        sys_p, user_p = prompt_service.construct_prompt(scenario)
        assert "Қазақ" in sys_p or "Kazakh" in sys_p


# ── Template-based prompt construction ───────────────────────────────

class TestTemplatePromptConstruction:

    def test_template_system_prompt_used(self):
        scenario = _make_scenario()
        template = _make_template(system_prompt="Custom system: you are a red-team assistant.")
        sys_p, _ = prompt_service.construct_prompt(scenario, template)
        assert "Custom system" in sys_p

    def test_template_skeleton_filled(self):
        scenario = _make_scenario(target_role="CTO", target_department="Tech")
        template = _make_template(
            user_prompt_skeleton="Attack {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}} using {{ATTACK_CATEGORY}}."
        )
        _, user_p = prompt_service.construct_prompt(scenario, template)
        assert "CTO" in user_p
        assert "Tech" in user_p
        assert "Credential Phishing" in user_p

    def test_template_skeleton_all_placeholders_replaced(self):
        scenario = _make_scenario()
        template = _make_template(
            user_prompt_skeleton=(
                "Role: {{TARGET_ROLE}}, Dept: {{TARGET_DEPARTMENT}}, "
                "Cat: {{ATTACK_CATEGORY}}, Urgency: {{URGENCY_LEVEL}}, "
                "Channel: {{CHANNEL}}, Lang: {{LANGUAGE}}"
            )
        )
        _, user_p = prompt_service.construct_prompt(scenario, template)
        assert "{{" not in user_p, f"Unfilled placeholders remain: {user_p}"


# ── Scenario context summary ────────────────────────────────────────

class TestScenarioContextSummary:

    def test_summary_contains_attack_type(self):
        scenario = _make_scenario(pretext_category="spear_phishing")
        summary = prompt_service.build_scenario_context_summary(scenario)
        assert "Spear Phishing" in summary

    def test_summary_contains_target(self):
        scenario = _make_scenario(target_role="IT Administrator")
        summary = prompt_service.build_scenario_context_summary(scenario)
        assert "IT Administrator" in summary

    def test_summary_contains_channel(self):
        scenario = _make_scenario(communication_channel="sms")
        summary = prompt_service.build_scenario_context_summary(scenario)
        assert "sms" in summary

    def test_summary_contains_urgency(self):
        scenario = _make_scenario(urgency_level=5)
        summary = prompt_service.build_scenario_context_summary(scenario)
        assert "5/5" in summary
