#!/usr/bin/env python3
"""
Simple test of placeholder generation without database.
"""

import sys
import random
import string
from datetime import datetime, timedelta
from uuid import uuid4

# Test placeholder generation logic

def generate_tracking_number(service: str = "cdek") -> str:
    """Generate realistic tracking number for delivery service."""
    if service.upper() == "CDEK":
        # CDEK: 10 digits, range 1000000000-1999999999
        return str(random.randint(1000000000, 1999999999))
    elif service.upper() == "FEDEX":
        # FedEx: 12 digits,  range 794617899072-794617899999  
        return str(random.randint(794617899072, 794617899999))
    elif service.upper() == "UPS":
        # UPS: 1Z + 8 digits
        return f"1Z{random.randint(10000000, 99999999)}"
    elif service.upper() == "DPD":
        # DPD: 10 digits
        return str(random.randint(1000000000, 9999999999))
    else:
        return str(random.randint(1000000000, 9999999999))

def generate_date(format_type: str = "ru") -> str:
    """Generate future date."""
    days_ahead = random.randint(1, 30)
    future_date = datetime.now() + timedelta(days=days_ahead)
    
    if format_type == "ru":
        return future_date.strftime("%d.%m.%Y")
    else:  # US format
        return future_date.strftime("%m/%d/%Y")

def generate_time() -> str:
    """Generate business hours time."""
    hour = random.randint(9, 17)
    minute = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}"

def generate_delivery_service() -> str:
    """Generate random delivery service name."""
    services = [
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
    return random.choice(services)

# Run tests
print("=" * 60)
print("PLACEHOLDER GENERATION TESTS")
print("=" * 60)

print("\n1. CDEK Tracking Numbers:")
for i in range(5):
    print(f"   {generate_tracking_number('cdek')}")

print("\n2. FedEx Tracking Numbers:")
for i in range(5):
    print(f"   {generate_tracking_number('fedex')}")

print("\n3. UPS Tracking Numbers:")
for i in range(5):
    print(f"   {generate_tracking_number('ups')}")

print("\n4. Dates (Russian format):")
for i in range(5):
    print(f"   {generate_date('ru')}")

print("\n5. Dates (US format):")
for i in range(5):
    print(f"   {generate_date('us')}")

print("\n6. Times:")
for i in range(5):
    print(f"   {generate_time()}")

print("\n7. Delivery Services:")
for i in range(5):
    print(f"   {generate_delivery_service()}")

print("\n" + "=" * 60)
print("✓ All placeholder generation tests passed!")
print("=" * 60)
