"""
Predefined Template Seeder

Seeds the database with predefined phishing templates across all attack categories.
Run via: python -m app.services.seed_templates
"""

from sqlalchemy.orm import Session

from app.models.template import Template
from app.core.logging import get_logger

logger = get_logger("seed_templates")


PREDEFINED_TEMPLATES = [
    # ===== CREDENTIAL PHISHING =====
    {
        "name": "Password Expiration Warning",
        "description": "Simulates an IT notification about an expiring password, urging the target to update credentials via a fake portal.",
        "category": "credential_phishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic credential phishing 
simulation message for the PhishLens security research platform. 

## Role
Generate a convincing password expiration / credential update notification that appears 
to come from the organization's IT department or identity provider.

## Constraints
- Use ONLY placeholder data: [TARGET_NAME], [SENDER_NAME], [COMPANY_NAME], 
  [COMPANY_EMAIL], [TARGET_EMAIL], [DEPARTMENT], [DATE], [PHONE_NUMBER]
- For URLs use ONLY: https://example-phishing-domain.test/[PATH]
- Include watermark "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]" at the end
- Generate ONLY the message content, no explanations or meta-commentary
- Make it indistinguishable from legitimate IT communications""",
        "user_prompt_skeleton": """Generate a credential phishing email with these parameters:

## Target
- Role: {{TARGET_ROLE}}
- Department: {{TARGET_DEPARTMENT}}

## Attack Parameters
- Urgency Level: {{URGENCY_LEVEL}}/5 ({{URGENCY_DESCRIPTION}})
- Tactic: Password expiration / account security notification
- Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

## Requirements
- Subject line referencing password/security update
- Impersonate IT Help Desk or Identity Provider
- Create urgency about account lockout or access loss
- Include a fake credential update link: https://example-phishing-domain.test/reset-password
- Professional IT communication formatting
- Reference specific systems (SSO, Active Directory, Microsoft 365) for realism

Generate the complete {{CHANNEL}} message now.""",
    },
    {
        "name": "MFA Verification Required",
        "description": "Impersonates an MFA/2FA service asking the target to re-verify their multi-factor authentication setup.",
        "category": "credential_phishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic MFA/2FA 
re-verification phishing simulation for the PhishLens platform.

## Role
Generate a convincing multi-factor authentication reset or verification message 
that appears to come from the organization's security team or identity provider.

## Constraints
- Use ONLY placeholder data: [TARGET_NAME], [SENDER_NAME], [COMPANY_NAME], etc.
- For URLs use ONLY: https://example-phishing-domain.test/[PATH]
- Include watermark "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]" at the end
- Generate ONLY the message content
- Reference real MFA technologies (Microsoft Authenticator, Google Authenticator, etc.)""",
        "user_prompt_skeleton": """Generate an MFA re-verification phishing message:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message that:
- Claims the target's MFA enrollment needs to be re-verified
- References a recent "security incident" or "system migration" as the reason
- Provides a link to re-enroll: https://example-phishing-domain.test/mfa-setup
- Warns of account suspension if not completed by [DATE]
- Appears to come from [COMPANY_NAME] Security Team

Generate the message now.""",
    },

    # ===== BUSINESS EMAIL COMPROMISE =====
    {
        "name": "CEO Wire Transfer Request",
        "description": "Classic BEC attack where an executive urgently requests a wire transfer for a confidential business deal.",
        "category": "business_email_compromise",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic Business 
Email Compromise (BEC) wire transfer request simulation for the PhishLens platform.

## Role
Generate a convincing email that appears to come from a C-level executive 
requesting an urgent financial transaction.

## Constraints
- Use ONLY placeholder data for all names, amounts, and account details
- Do NOT include real bank account numbers — use [ACCOUNT_NUMBER], [ROUTING_NUMBER]
- Include watermark "[SIMULATION - AUTHORIZED SECURITY RESEARCH ONLY]" at the end
- The email should appear brief and informal, as if sent from a mobile device
- Emphasize confidentiality and urgency""",
        "user_prompt_skeleton": """Generate a BEC wire transfer request:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message that:
- Impersonates [CEO_NAME] or another C-level executive
- Requests an urgent wire transfer for a "confidential acquisition" or "vendor payment"
- Emphasizes secrecy ("keep this between us", "don't discuss with others yet")
- Sent from what appears to be a mobile device (short, informal)
- References a realistic business context
- Asks the target to respond with confirmation
- Amount: [DOLLAR_AMOUNT]

{{PRETEXT_DESCRIPTION}}

Generate the message now.""",
    },
    {
        "name": "Vendor Invoice Payment Update",
        "description": "BEC attack impersonating a vendor requesting a change to payment details for an outstanding invoice.",
        "category": "business_email_compromise",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic vendor 
invoice fraud simulation for the PhishLens platform.

## Role
Generate a convincing email that appears to come from a legitimate vendor/supplier 
requesting a change to their payment details.

## Constraints
- Use ONLY placeholder data: [VENDOR_NAME], [INVOICE_NUMBER], [AMOUNT], etc.
- Do NOT include real bank details — use [NEW_ACCOUNT], [NEW_ROUTING]
- Include watermark at the end
- Professional business correspondence formatting
- Reference realistic invoice/PO numbers using placeholders""",
        "user_prompt_skeleton": """Generate a vendor invoice fraud email:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}

{{ORG_CONTEXT}}

Create a message from [VENDOR_NAME] that:
- References an outstanding invoice [INVOICE_NUMBER] for [AMOUNT]
- Requests updating banking details to a new account
- Provides a "reason" (bank migration, new subsidiary, restructuring)
- Includes professional vendor email formatting
- Attaches urgency about upcoming payment deadline

Generate the complete email now.""",
    },

    # ===== SPEAR PHISHING =====
    {
        "name": "Colleague Document Share",
        "description": "Targeted spear phishing impersonating a colleague sharing an important document or file.",
        "category": "spear_phishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic spear 
phishing simulation for the PhishLens platform.

## Role
Generate a convincing message that appears to come from a colleague sharing 
a document or file that requires the target's attention.

## Constraints
- Use ONLY placeholder data: [COLLEAGUE_NAME], [PROJECT_NAME], [DOCUMENT_NAME]
- For URLs use ONLY: https://example-phishing-domain.test/[PATH]
- Include watermark at the end
- Make it highly personalized to the target's role and department
- Reference realistic workplace scenarios""",
        "user_prompt_skeleton": """Generate a spear phishing document-sharing message:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message from [COLLEAGUE_NAME] that:
- References a specific project or initiative ([PROJECT_NAME])
- Shares a document link: https://example-phishing-domain.test/shared/[DOCUMENT_ID]
- Uses a casual, collegial tone appropriate for internal communication
- Includes a compelling reason to open the document
- May reference a recent meeting, deadline, or decision

{{PRETEXT_DESCRIPTION}}

Generate the message now.""",
    },
    {
        "name": "Conference Follow-Up",
        "description": "Spear phishing that leverages a recent industry event or conference to establish rapport.",
        "category": "spear_phishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic conference 
follow-up spear phishing simulation for the PhishLens platform.

## Role
Generate a convincing message that appears to be from someone the target met 
at a recent industry conference or event.

## Constraints
- Use ONLY placeholder data
- For URLs use ONLY: https://example-phishing-domain.test/[PATH]
- Include watermark at the end
- Reference realistic industry events and topics
- Professional networking tone""",
        "user_prompt_skeleton": """Generate a conference follow-up spear phishing message:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message from [EXTERNAL_CONTACT] that:
- References meeting at [CONFERENCE_NAME] recently
- Shares "presentation slides" or "research paper" discussed
- Includes link: https://example-phishing-domain.test/resources/[FILE_ID]
- Professional, friendly networking tone
- References industry-relevant topics

Generate the message now.""",
    },

    # ===== WHALING =====
    {
        "name": "Legal Subpoena Notification",
        "description": "Whaling attack targeting executives with a fake legal subpoena or regulatory notice.",
        "category": "whaling",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic whaling 
(executive-targeted phishing) simulation for the PhishLens platform.

## Role
Generate a convincing legal/regulatory notification that would alarm a senior 
executive into taking immediate action.

## Constraints
- Use ONLY placeholder data: [EXECUTIVE_NAME], [COMPANY_NAME], [CASE_NUMBER]
- For URLs use ONLY: https://example-phishing-domain.test/[PATH]
- Include watermark at the end
- Use formal legal language
- Reference realistic legal/regulatory frameworks""",
        "user_prompt_skeleton": """Generate a whaling legal notification:

## Target: {{TARGET_ROLE}} (Executive)
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message that:
- Appears to come from [LAW_FIRM_NAME] or [REGULATORY_BODY]
- References a pending legal matter, subpoena, or investigation
- Case/Reference: [CASE_NUMBER]
- Requires immediate review of documents
- Link to "secure document portal": https://example-phishing-domain.test/legal/[CASE_ID]
- Formal legal tone with appropriate disclaimers
- Implies serious consequences for non-response

Generate the message now.""",
    },

    # ===== QUISHING =====
    {
        "name": "MFA QR Code Setup",
        "description": "QR code phishing that tricks the target into scanning a malicious QR code disguised as an MFA enrollment.",
        "category": "quishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic QR code 
phishing (quishing) simulation for the PhishLens platform.

## Role
Generate a convincing message that includes instructions to scan a QR code, 
which would normally lead to a credential-harvesting page.

## Constraints
- Use ONLY placeholder data
- For any URLs referenced by the QR code: https://example-phishing-domain.test/[PATH]
- Include watermark at the end
- Note: The actual QR code image is not generated, just the message context
- Describe where the QR code would appear: [QR_CODE_PLACEHOLDER]""",
        "user_prompt_skeleton": """Generate a quishing message:

## Target: {{TARGET_ROLE}} in {{TARGET_DEPARTMENT}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}
## Channel: {{CHANNEL}}

{{ORG_CONTEXT}}

Create a message that:
- Instructs the target to scan a QR code for MFA enrollment/verification
- Claims to be from IT Security or Identity team
- References a recent "security policy update" requiring re-enrollment
- Include [QR_CODE_PLACEHOLDER] where the QR code image would be
- The QR code supposedly links to: https://example-phishing-domain.test/mfa-enroll
- Warns of access loss if not completed by deadline

Generate the message now.""",
    },

    # ===== SMISHING =====
    {
        "name": "Urgent Account Alert (SMS)",
        "description": "SMS phishing that impersonates a bank or service provider with an urgent account security alert.",
        "category": "smishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic SMS 
phishing (smishing) simulation for the PhishLens platform.

## Role
Generate a convincing SMS message that impersonates a legitimate service 
with an urgent account alert.

## Constraints
- Keep the message under 320 characters (SMS format)
- Use ONLY: https://example-phishing-domain.test/[PATH] for links
- Include watermark at the end (can be abbreviated)
- Use SMS-appropriate language (abbreviations OK)
- Urgent, action-oriented tone""",
        "user_prompt_skeleton": """Generate a smishing message:

## Target: {{TARGET_ROLE}}
## Urgency: {{URGENCY_LEVEL}}/5 — {{URGENCY_DESCRIPTION}}

Create a SHORT SMS message (under 320 chars) that:
- Impersonates [SERVICE_NAME] (bank, cloud service, or corporate IT)
- Alerts about suspicious activity or account issue
- Includes: https://example-phishing-domain.test/verify
- Creates urgency to act immediately
- Looks like an automated security notification

{{PRETEXT_DESCRIPTION}}

Generate the SMS message now.""",
    },
    {
        "name": "Package Delivery Notification (SMS)",
        "description": "SMS phishing impersonating a delivery service with a failed package delivery notification.",
        "category": "smishing",
        "system_prompt": """You are a cybersecurity research assistant generating a realistic package 
delivery smishing simulation for the PhishLens platform.

## Role
Generate a convincing SMS about a failed/pending package delivery.

## Constraints
- Keep under 320 characters
- Use ONLY: https://example-phishing-domain.test/[PATH]
- Include abbreviated watermark
- Impersonate [DELIVERY_SERVICE] (FedEx, UPS, DHL style)""",
        "user_prompt_skeleton": """Generate a delivery notification smishing message:

## Target: {{TARGET_ROLE}}
## Urgency: {{URGENCY_LEVEL}}/5

Create a SHORT SMS (under 320 chars) that:
- Impersonates [DELIVERY_SERVICE]
- References tracking: [TRACKING_NUMBER]
- Claims delivery issue requiring address confirmation
- Link: https://example-phishing-domain.test/track/[ID]
- Mentions redelivery fee or package return deadline

Generate the SMS now.""",
    },
]


def seed_templates(db: Session) -> int:
    """Seed the database with predefined templates.

    Returns:
        Number of templates created (skips existing ones).
    """
    created = 0
    for tmpl_data in PREDEFINED_TEMPLATES:
        # Check if template already exists by name
        existing = db.query(Template).filter(
            Template.name == tmpl_data["name"],
            Template.is_predefined == True,  # noqa: E712
        ).first()

        if existing:
            logger.info(f"Template '{tmpl_data['name']}' already exists, skipping")
            continue

        template = Template(
            name=tmpl_data["name"],
            description=tmpl_data["description"],
            category=tmpl_data["category"],
            system_prompt=tmpl_data["system_prompt"],
            user_prompt_skeleton=tmpl_data["user_prompt_skeleton"],
            is_predefined=True,
            is_public=True,
            user_id=None,  # System template
        )
        db.add(template)
        created += 1

    db.commit()
    logger.info(f"Seeded {created} predefined templates")
    return created


if __name__ == "__main__":
    """Run directly to seed templates: python -m app.services.seed_templates"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        count = seed_templates(db)
        print(f"✅ Seeded {count} predefined templates")
    finally:
        db.close()
