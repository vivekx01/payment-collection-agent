from __future__ import annotations
from datetime import datetime


def luhn_check(card_number: str) -> bool:
    digits = [int(d) for d in card_number]
    digits.reverse()
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_card_fields(card: dict) -> list[str]:
    """
    Validate card fields client-side before hitting the API.
    Returns a list of (field, error_message) tuples for any failures.
    """
    errors = []

    card_number = card.get("card_number", "")
    if not card_number.isdigit() or len(card_number) != 16:
        errors.append(("card_number", "Card number must be exactly 16 digits."))
    elif not luhn_check(card_number):
        errors.append(("card_number", "Card number appears to be invalid. Please double-check it."))

    cvv = card.get("cvv", "")
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        errors.append(("cvv", "CVV must be 3 digits (4 for Amex)."))

    month = card.get("expiry_month")
    year = card.get("expiry_year")
    if month and year:
        now = datetime.now()
        if year < now.year or (year == now.year and month < now.month):
            errors.append(("expiry_month", "This card has already expired."))

    return errors
