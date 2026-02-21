"""
Prompt Construction Service — Three-Tier Pipeline

Implements the prompt construction pipeline per Section 1.4.3:
  Tier 1: Objective Definition — maps scenario to structured prompt
  Tier 2: Context Injection — incorporates organizational context
  Tier 3: Evasion/Polymorphism Optimization — reflection and variation
"""

from typing import Optional

from app.models.scenario import Scenario
from app.models.template import Template
from app.core.logging import get_logger

logger = get_logger("prompt_service")

# Urgency level labels
URGENCY_LABELS = {
    1: "Low — informational, no time pressure",
    2: "Moderate — some urgency, within a few days",
    3: "Medium — action needed within 24 hours",
    4: "High — immediate action required, consequences implied",
    5: "Critical — extreme urgency, dire consequences, panic-inducing",
}

# Channel-specific formatting instructions
CHANNEL_FORMATS = {
    "email": (
        "Format the output as a professional email with Subject line, "
        "greeting, body paragraphs, call-to-action, and signature block. "
        "Include realistic sender details using placeholders like [SENDER_NAME], "
        "[SENDER_TITLE], [COMPANY_NAME]."
    ),
    "sms": (
        "Format as a short SMS/text message (under 160 characters if possible, "
        "max 320 characters). Use informal, urgent language. Include a shortened "
        "URL placeholder: https://example-phishing-domain.test/[TRACKING_ID]"
    ),
    "internal_chat": (
        "Format as an internal messaging platform message (like Slack or Teams). "
        "Use casual professional tone, possibly with emoji. Keep it concise but "
        "natural. Reference internal team/channel names using placeholders."
    ),
}

# Target persona descriptions for common roles
TARGET_PERSONAS = {
    "hr_manager": {
        "label": "HR Manager",
        "context": (
            "Human Resources Manager responsible for employee onboarding, "
            "benefits administration, and compliance. Has access to employee "
            "personal data, payroll systems, and company policy documents."
        ),
    },
    "software_engineer": {
        "label": "Software Engineer",
        "context": (
            "Software developer with access to source code repositories, "
            "CI/CD pipelines, cloud infrastructure credentials, and "
            "internal development tools. Technically savvy but may be "
            "vulnerable to time-pressure tactics."
        ),
    },
    "c_level": {
        "label": "C-Level Executive",
        "context": (
            "Senior executive (CEO/CFO/CTO) with authority to approve "
            "financial transactions, access confidential business data, "
            "and make decisions on behalf of the organization. High-value "
            "target for whaling and BEC attacks."
        ),
    },
    "finance_manager": {
        "label": "Finance Manager",
        "context": (
            "Financial controller with access to banking details, wire "
            "transfer authorization, vendor payment systems, and financial "
            "reporting tools. Key target for BEC and invoice fraud."
        ),
    },
    "it_administrator": {
        "label": "IT Administrator",
        "context": (
            "System administrator with privileged access to network "
            "infrastructure, Active Directory, email servers, and "
            "security tools. Has elevated permissions across multiple systems."
        ),
    },
    "receptionist": {
        "label": "Receptionist / Front Desk",
        "context": (
            "Front-facing staff handling visitor management, mail, "
            "deliveries, and general inquiries. May have access to "
            "internal directories and physical access control systems."
        ),
    },
    "sales_representative": {
        "label": "Sales Representative",
        "context": (
            "Sales team member with access to CRM systems, customer "
            "databases, pricing information, and proposal templates. "
            "Regularly communicates with external parties."
        ),
    },
}

# Pretext category detailed descriptions
PRETEXT_DESCRIPTIONS = {
    "credential_phishing": {
        "label": "Credential Phishing",
        "description": (
            "Attempts to steal login credentials by impersonating legitimate "
            "services (email providers, SSO portals, cloud services, internal systems). "
            "Typically involves a fake login page or credential harvesting form."
        ),
        "tactics": [
            "Password expiration warnings",
            "Account verification requests",
            "Security alert notifications",
            "MFA reset requests",
            "SSO portal updates",
        ],
    },
    "business_email_compromise": {
        "label": "Business Email Compromise (BEC)",
        "description": (
            "Impersonates executives or trusted partners to manipulate employees "
            "into transferring funds, sharing sensitive data, or taking unauthorized actions. "
            "Relies on authority and urgency."
        ),
        "tactics": [
            "CEO wire transfer requests",
            "Vendor payment changes",
            "Confidential acquisition requests",
            "Urgent invoice payments",
            "Gift card purchase requests",
        ],
    },
    "quishing": {
        "label": "Quishing (QR Code Phishing)",
        "description": (
            "Uses QR codes to redirect victims to malicious websites. "
            "Exploits the opacity of QR codes — users can't see the URL before scanning. "
            "Often embedded in physical or digital documents."
        ),
        "tactics": [
            "MFA setup QR codes",
            "Document access QR codes",
            "Wi-Fi network QR codes",
            "Payment QR codes",
            "Event registration QR codes",
        ],
    },
    "spear_phishing": {
        "label": "Spear Phishing",
        "description": (
            "Highly targeted phishing directed at specific individuals using "
            "personalized information gathered from social media, company websites, "
            "or data breaches. More convincing than generic phishing."
        ),
        "tactics": [
            "Project-specific references",
            "Recent event exploitation",
            "Colleague impersonation",
            "Industry conference follow-ups",
            "LinkedIn connection requests",
        ],
    },
    "whaling": {
        "label": "Whaling",
        "description": (
            "Phishing attacks specifically targeting senior executives and "
            "high-profile individuals. Uses sophisticated pretexts involving "
            "legal, regulatory, or high-stakes business matters."
        ),
        "tactics": [
            "Legal subpoena notifications",
            "Board meeting documents",
            "Regulatory compliance alerts",
            "M&A confidential communications",
            "Executive performance reviews",
        ],
    },
    "smishing": {
        "label": "Smishing (SMS Phishing)",
        "description": (
            "Phishing conducted via SMS/text messages. Exploits the personal "
            "nature of text messages and mobile-first behavior. Often uses "
            "urgency and short URLs."
        ),
        "tactics": [
            "Package delivery notifications",
            "Bank fraud alerts",
            "Two-factor authentication codes",
            "Prize/reward notifications",
            "Account suspension warnings",
        ],
    },
}


class PromptService:
    """Three-tier prompt construction pipeline."""

    def construct_prompt(
        self,
        scenario: Scenario,
        template: Optional[Template] = None,
    ) -> tuple[str, str]:
        """Construct system prompt and user prompt from scenario + template.

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Tier 1: Objective Definition
        objective = self._define_objective(scenario)

        # Tier 2: Context Injection
        context = self._inject_context(scenario)

        # Tier 3: Evasion/Polymorphism Optimization
        system_prompt, user_prompt = self._build_final_prompts(
            objective, context, scenario, template
        )

        logger.info(
            "Prompt constructed",
            scenario_id=str(scenario.id),
            template_id=str(template.id) if template else None,
            category=scenario.pretext_category,
        )

        return system_prompt, user_prompt

    def _define_objective(self, scenario: Scenario) -> dict:
        """Tier 1: Map scenario parameters to a structured objective.

        Extracts the attack goal, target profile, and desired psychological
        approach from the scenario configuration.
        """
        pretext_info = PRETEXT_DESCRIPTIONS.get(
            scenario.pretext_category, {}
        )
        urgency_desc = URGENCY_LABELS.get(scenario.urgency_level, URGENCY_LABELS[3])

        # Determine target persona context
        target_persona_key = scenario.target_role.lower().replace(" ", "_")
        persona_info = TARGET_PERSONAS.get(target_persona_key, None)
        target_context = (
            persona_info["context"]
            if persona_info
            else f"Professional in the role of {scenario.target_role}"
        )

        return {
            "attack_category": pretext_info.get("label", scenario.pretext_category),
            "attack_description": pretext_info.get("description", ""),
            "tactics": pretext_info.get("tactics", []),
            "target_role": scenario.target_role,
            "target_context": target_context,
            "target_department": scenario.target_department or "General",
            "urgency_level": scenario.urgency_level,
            "urgency_description": urgency_desc,
            "channel": scenario.communication_channel,
            "language": scenario.language,
        }

    def _inject_context(self, scenario: Scenario) -> str:
        """Tier 2: Inject organizational context.

        Uses the organization_context field from the scenario to provide
        domain-specific details that make the phishing message more
        contextually relevant.
        """
        if not scenario.organization_context:
            return ""

        return (
            f"\n## Organizational Context (use to personalize the message)\n"
            f"{scenario.organization_context}\n"
            f"Use this context to make the message more targeted and believable. "
            f"Reference specific details where appropriate, but always use "
            f"placeholder names like [TARGET_NAME], [COMPANY_NAME], etc."
        )

    def _build_final_prompts(
        self,
        objective: dict,
        org_context: str,
        scenario: Scenario,
        template: Optional[Template],
    ) -> tuple[str, str]:
        """Tier 3: Build final system and user prompts with evasion optimization.

        If a template is provided, use it as the base. Otherwise, construct
        from scratch using the objective and context.
        """
        # --- System Prompt ---
        if template:
            system_prompt = template.system_prompt
        else:
            system_prompt = self._build_default_system_prompt(objective, scenario)

        # --- User Prompt ---
        if template:
            user_prompt = self._fill_template_skeleton(
                template.user_prompt_skeleton, objective, org_context, scenario
            )
        else:
            user_prompt = self._build_default_user_prompt(
                objective, org_context, scenario
            )

        # --- Language override (applied to ALL paths) ---
        lang_override = self._get_language_override(scenario)
        if lang_override:
            system_prompt += f"\n\n{lang_override}"
            user_prompt += f"\n\n{lang_override}"

        return system_prompt, user_prompt

    @staticmethod
    def _get_language_override(scenario: Scenario) -> str:
        """Return a strong language instruction if the scenario uses a non-English language."""
        lang = scenario.language
        if lang == "russian":
            return (
                "CRITICAL REQUIREMENT — LANGUAGE: You MUST write the ENTIRE message "
                "in Russian (Русский язык). Every single word of the output — subject "
                "line, greeting, body, call-to-action, signature — MUST be in Russian. "
                "The ONLY exceptions are placeholder tokens like [TARGET_NAME] and the "
                "watermark tag. Do NOT write in English."
            )
        if lang == "kazakh":
            return (
                "CRITICAL REQUIREMENT — LANGUAGE: You MUST write the ENTIRE message "
                "in Kazakh (Қазақ тілі). Every single word of the output — subject "
                "line, greeting, body, call-to-action, signature — MUST be in Kazakh. "
                "The ONLY exceptions are placeholder tokens like [TARGET_NAME] and the "
                "watermark tag. Do NOT write in English."
            )
        return ""

    def _build_default_system_prompt(self, objective: dict, scenario: Scenario) -> str:
        """Build a system prompt when no template is selected."""
        language_instruction = ""
        if scenario.language == "russian":
            language_instruction = "Write the entire message in Russian (Русский язык)."
        elif scenario.language == "kazakh":
            language_instruction = "Write the entire message in Kazakh (Қазақ тілі)."
        else:
            language_instruction = "Write the entire message in English."

        return f"""You are a cybersecurity research assistant helping generate realistic 
phishing simulation messages for an authorized security awareness training platform 
called PhishLens. Your output will NEVER be used for actual attacks — it is strictly 
for research and training purposes.

## Your Role
Generate a single, realistic {objective['attack_category']} message that would be 
sent via {objective['channel']} to a {objective['target_role']}.

## Important Constraints
- Use ONLY placeholder data: [TARGET_NAME], [SENDER_NAME], [COMPANY_NAME], 
  [COMPANY_EMAIL], [TARGET_EMAIL], [DEPARTMENT], [DATE], [PHONE_NUMBER]
- For any URLs, use ONLY: https://example-phishing-domain.test/[PATH]
- Do NOT include real personal information, real company names, or real URLs
- Include the watermark "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]" at the 
  very end of the message
- {language_instruction}
- Generate ONLY the message content — no meta-commentary or explanations

## Output Quality
- The message should be indistinguishable from a real {objective['attack_category']} 
  attempt when placeholder data is filled with real values
- Apply natural language patterns appropriate for the communication channel
- Avoid common phishing red flags like obvious grammatical errors (unless 
  specifically appropriate for the pretext)"""

    def _build_default_user_prompt(
        self, objective: dict, org_context: str, scenario: Scenario
    ) -> str:
        """Build a user prompt when no template is selected."""
        channel_format = CHANNEL_FORMATS.get(
            scenario.communication_channel, CHANNEL_FORMATS["email"]
        )
        tactics_str = "\n".join(f"  - {t}" for t in objective["tactics"][:3]) if objective["tactics"] else "  - Use contextually appropriate tactics"

        pretext_detail = ""
        if scenario.pretext_description:
            pretext_detail = f"\n## Custom Pretext Details\n{scenario.pretext_description}\n"

        return f"""Generate a {objective['attack_category']} simulation message with these parameters:

## Target Profile
- Role: {objective['target_role']}
- Department: {objective['target_department']}
- Target Context: {objective['target_context']}

## Attack Configuration
- Category: {objective['attack_category']}
- Description: {objective['attack_description']}
- Suggested Tactics (pick the most appropriate):
{tactics_str}
- Urgency Level: {objective['urgency_level']}/5 — {objective['urgency_description']}
- Communication Channel: {objective['channel']}
{pretext_detail}
{org_context}

## Formatting Requirements
{channel_format}

Generate the complete message now. Remember to use only placeholder data and include 
the research watermark at the end."""

    def _fill_template_skeleton(
        self,
        skeleton: str,
        objective: dict,
        org_context: str,
        scenario: Scenario,
    ) -> str:
        """Fill a template's user prompt skeleton with scenario data."""
        # Replace template placeholders with actual scenario data
        filled = skeleton
        replacements = {
            "{{TARGET_ROLE}}": objective["target_role"],
            "{{TARGET_DEPARTMENT}}": objective["target_department"],
            "{{TARGET_CONTEXT}}": objective["target_context"],
            "{{ATTACK_CATEGORY}}": objective["attack_category"],
            "{{ATTACK_DESCRIPTION}}": objective["attack_description"],
            "{{URGENCY_LEVEL}}": str(objective["urgency_level"]),
            "{{URGENCY_DESCRIPTION}}": objective["urgency_description"],
            "{{CHANNEL}}": objective["channel"],
            "{{LANGUAGE}}": objective["language"],
            "{{ORG_CONTEXT}}": org_context,
            "{{PRETEXT_DESCRIPTION}}": scenario.pretext_description or "",
            "{{TACTICS}}": ", ".join(objective["tactics"][:3]) if objective["tactics"] else "",
        }

        for placeholder, value in replacements.items():
            filled = filled.replace(placeholder, value)

        return filled

    def build_scenario_context_summary(self, scenario: Scenario) -> str:
        """Build a context summary string for evaluation purposes."""
        pretext_info = PRETEXT_DESCRIPTIONS.get(scenario.pretext_category, {})
        return (
            f"Attack Type: {pretext_info.get('label', scenario.pretext_category)}\n"
            f"Target: {scenario.target_role}"
            f"{' in ' + scenario.target_department if scenario.target_department else ''}\n"
            f"Channel: {scenario.communication_channel}\n"
            f"Urgency: {scenario.urgency_level}/5\n"
            f"Language: {scenario.language}"
        )


# Singleton instance
prompt_service = PromptService()
