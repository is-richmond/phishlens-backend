#!/usr/bin/env python3
"""
Test placeholder generation service.

Quick test to verify that placeholders are being replaced with realistic values.
"""

from app.services.placeholder_service import placeholder_service

# Test 1: Generate all placeholders
print("=" * 60)
print("TEST 1: Generate all placeholders")
print("=" * 60)

all_placeholders = placeholder_service.generate_all_placeholders()
for placeholder, value in sorted(all_placeholders.items()):
    print(f"{placeholder:30} -> {str(value)[:50]}")

print()

# Test 2: Replace placeholders in text
print("=" * 60)
print("TEST 2: Replace placeholders in text")
print("=" * 60)

text_with_placeholders = """
Dear [TARGET_NAME],

Your package [TRACKING_NUMBER] from [DELIVERY_SERVICE] will arrive on [DATE] at [TIME].

Please verify your account at [VERIFICATION_LINK]

Confirmation: [CONFIRMATION_CODE]
Bank: [BANK_NAME]
Account: [ACCOUNT_NUMBER]

Regards,
[SENDER_NAME]
"""

replaced_text = placeholder_service.replace_generic_placeholders(text_with_placeholders)
print("Original text:")
print(text_with_placeholders)
print("\nReplaced text:")
print(replaced_text)

print()

# Test 3: Test specific methods
print("=" * 60)
print("TEST 3: Test specific methods")
print("=" * 60)

print(f"Tracking number: {placeholder_service.generate_tracking_number()}")
print(f"Date (Russian): {placeholder_service.generate_date('ru')}")
print(f"Date (US): {placeholder_service.generate_date('us')}")
print(f"Time: {placeholder_service.generate_time()}")
print(f"Delivery service: {placeholder_service.generate_delivery_service()}")
print(f"Verification link: {placeholder_service.generate_verification_link()}")
print(f"Confirmation code: {placeholder_service.generate_confirmation_code()}")
print(f"Bank name: {placeholder_service.generate_bank_name()}")
print(f"Account number: {placeholder_service.generate_account_number()}")

print()
print("✓ All tests completed successfully!")
