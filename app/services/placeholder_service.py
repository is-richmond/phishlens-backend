"""
Placeholder Service

Generates realistic values for common placeholders used in phishing simulations.
Supports: tracking numbers, dates, service names, URLs, etc.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.logging import get_logger

logger = get_logger("placeholder_service")


class PlaceholderService:
    """Service for generating placeholder values."""

    # Common delivery services
    DELIVERY_SERVICES = [
        "CDEK",
        "DPD",
        "FedEx",
        "UPS",
        "Яндекс.Доставка",
        "Boxberry",
        "PickPoint",
        "5Post",
        "Hermes",
        "Почта России",
    ]

    # Common company names (for generic uses)
    COMPANIES = [
        "Microsoft",
        "Apple",
        "Google",
        "Amazon",
        "PayPal",
        "Stripe",
        "Twilio",
        "SendGrid",
        "Slack",
        "Zoom",
    ]

    # Common bank names
    BANKS = [
        "Сбербанк",
        "ВТБ",
        "Альфа-Банк",
        "Райффайзен",
        "Тинькофф",
        "БПС-Сбербанк",
        "Промсвязьбанк",
        "МегаФон",
    ]

    @staticmethod
    def generate_tracking_number() -> str:
        """Generate a realistic tracking number.
        
        Format varies by service:
        - CDEK: 1000000000-1999999999 (10 digits)
        - UPS: 1000000000-9999999999 (10 digits)
        - FedEx: 794617899072-794617899999 (12 digits starting with specific prefix)
        """
        service = random.choice(["CDEK", "UPS", "FedEx", "DPD"])
        
        if service == "CDEK":
            return str(random.randint(1000000000, 1999999999))
        elif service == "FedEx":
            return str(random.randint(794617899072, 794617899999))
        elif service == "DPD":
            return f"{random.randint(100000000, 999999999)}"
        else:  # UPS
            return str(random.randint(1000000000, 9999999999))

    @staticmethod
    def generate_package_id() -> str:
        """Generate a realistic package/parcel ID.
        
        Format: RU + 9 digits
        """
        return f"RU{random.randint(100000000, 999999999)}"

    @staticmethod
    def generate_reference_number() -> str:
        """Generate a reference number for support tickets.
        
        Format: REF-XXXXXX-YYYYYY (random alphanumeric)
        """
        part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"REF-{part1}-{part2}"

    @staticmethod
    def generate_order_number() -> str:
        """Generate a realistic order number.
        
        Format: ORD-XXXXXXXXXX or just digits
        """
        if random.choice([True, False]):
            return f"ORD-{random.randint(100000000000, 999999999999)}"
        else:
            return str(random.randint(100000000000, 999999999999))

    @staticmethod
    def generate_invoice_number() -> str:
        """Generate a realistic invoice number.
        
        Format: INV-YYYYMMDD-XXXX or similar
        """
        date_part = datetime.now().strftime("%Y%m%d")
        seq_part = random.randint(1000, 9999)
        return f"INV-{date_part}-{seq_part}"

    @staticmethod
    def generate_confirmation_code() -> str:
        """Generate a confirmation code.
        
        Format: 6-digit code or alphanumeric code
        """
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    @staticmethod
    def generate_date(days_offset: int = 0, future_days: int = 3) -> str:
        """Generate a realistic date (usually in the future).
        
        Args:
            days_offset: Start offset (0 = today)
            future_days: Days in the future to generate
        
        Returns:
            Date string in format DD.MM.YYYY (Russian) or MM/DD/YYYY
        """
        base_date = datetime.now() + timedelta(days=days_offset)
        random_date = base_date + timedelta(days=random.randint(1, future_days))
        
        # Random format
        if random.choice([True, False]):
            return random_date.strftime("%d.%m.%Y")  # Russian format
        else:
            return random_date.strftime("%m/%d/%Y")  # US format

    @staticmethod
    def generate_time() -> str:
        """Generate a random time in HH:MM format."""
        hour = random.randint(9, 18)  # Business hours
        minute = random.randint(0, 59)
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def generate_delivery_service() -> str:
        """Generate a delivery service name."""
        return random.choice(PlaceholderService.DELIVERY_SERVICES)

    @staticmethod
    def generate_company_name() -> str:
        """Generate a company name."""
        return random.choice(PlaceholderService.COMPANIES)

    @staticmethod
    def generate_bank_name() -> str:
        """Generate a bank name."""
        return random.choice(PlaceholderService.BANKS)

    @staticmethod
    def generate_account_number() -> str:
        """Generate a realistic account number (masked).
        
        Format: ****-****-****-1234 (last 4 digits visible)
        """
        last_four = random.randint(1000, 9999)
        return f"****-****-****-{last_four}"

    @staticmethod
    def generate_verification_link() -> str:
        """Generate a verification/action link placeholder.
        
        This will be filled in later with actual domain.
        """
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        return f"https://example-phishing-domain.test/verify/{code}"

    @staticmethod
    def generate_all_placeholders() -> Dict[str, str]:
        """Generate values for all common placeholders.
        
        Returns:
            Dictionary mapping placeholder names to generated values
        """
        return {
            "[TRACKING_NUMBER]": PlaceholderService.generate_tracking_number(),
            "[PACKAGE_ID]": PlaceholderService.generate_package_id(),
            "[ORDER_NUMBER]": PlaceholderService.generate_order_number(),
            "[INVOICE_NUMBER]": PlaceholderService.generate_invoice_number(),
            "[REFERENCE_NUMBER]": PlaceholderService.generate_reference_number(),
            "[CONFIRMATION_CODE]": PlaceholderService.generate_confirmation_code(),
            "[DATE]": PlaceholderService.generate_date(),
            "[TIME]": PlaceholderService.generate_time(),
            "[DELIVERY_SERVICE]": PlaceholderService.generate_delivery_service(),
            "[COMPANY_NAME]": PlaceholderService.generate_company_name(),
            "[BANK_NAME]": PlaceholderService.generate_bank_name(),
            "[ACCOUNT_NUMBER]": PlaceholderService.generate_account_number(),
            "[VERIFICATION_LINK]": PlaceholderService.generate_verification_link(),
        }

    @staticmethod
    def replace_generic_placeholders(text: str) -> str:
        """Replace generic placeholders in text with realistic values.
        
        This is called on the final output to fill in realistic values
        for common placeholders like [DATE], [TRACKING_NUMBER], etc.
        
        Args:
            text: Text containing placeholders
            
        Returns:
            Text with placeholders replaced
        """
        if not text:
            return text
        
        placeholders = PlaceholderService.generate_all_placeholders()
        
        for placeholder, value in placeholders.items():
            if placeholder in text:
                text = text.replace(placeholder, value)
                logger.debug(f"Replaced {placeholder} with {value}")
        
        return text


placeholder_service = PlaceholderService()
