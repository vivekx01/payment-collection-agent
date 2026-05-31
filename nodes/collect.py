from __future__ import annotations
from state import AgentState
from nodes.extract import extract, get_last_human_message
from nodes.validate import validate_card_fields


def _capture_early_info(extracted, state: AgentState) -> dict:
    """Eagerly capture any identity info volunteered out of order."""
    updates = {}
    if extracted.full_name and not state.get("collected_name"):
        updates["collected_name"] = extracted.full_name
    if not state.get("collected_secondary"):
        if extracted.dob:
            updates["collected_secondary"] = {"type": "dob", "value": extracted.dob}
        elif extracted.aadhaar_last4:
            updates["collected_secondary"] = {"type": "aadhaar", "value": extracted.aadhaar_last4}
        elif extracted.pincode:
            updates["collected_secondary"] = {"type": "pincode", "value": extracted.pincode}
    return updates


def collect_account_id(state: AgentState) -> dict:
    last_msg = get_last_human_message(state["messages"])
    extracted = extract(last_msg)
    updates = _capture_early_info(extracted, state)

    if extracted.account_id:
        updates["account_id"] = extracted.account_id
        updates["next_node"] = "lookup_account"
        return updates

    is_first_turn = len(state["messages"]) <= 1
    if is_first_turn:
        response = "Hello! I'm here to help you with your payment. To get started, could you please share your account ID?"
    else:
        response = "I didn't catch your account ID. It should look like ACC1001. Could you provide it?"

    updates["last_response"] = response
    updates["next_node"] = "end"
    return updates


def collect_identity(state: AgentState) -> dict:
    last_msg = get_last_human_message(state["messages"])
    extracted = extract(last_msg)
    updates = {}

    if extracted.full_name and not state.get("collected_name"):
        updates["collected_name"] = extracted.full_name

    if not state.get("collected_secondary"):
        if extracted.dob:
            updates["collected_secondary"] = {"type": "dob", "value": extracted.dob}
        elif extracted.aadhaar_last4:
            updates["collected_secondary"] = {"type": "aadhaar", "value": extracted.aadhaar_last4}
        elif extracted.pincode:
            updates["collected_secondary"] = {"type": "pincode", "value": extracted.pincode}

    collected_name = updates.get("collected_name") or state.get("collected_name")
    collected_secondary = updates.get("collected_secondary") or state.get("collected_secondary")

    if collected_name and collected_secondary:
        updates["next_node"] = "verify_identity"
        return updates

    if not collected_name and not collected_secondary:
        response = (
            "To verify your identity, I'll need your full name and one of the following: "
            "your date of birth, the last 4 digits of your Aadhaar, or your pincode."
        )
    elif not collected_name:
        response = "Could you please provide your full name as it appears on your account?"
    else:
        response = (
            "Thank you. To complete verification, please provide one of: "
            "your date of birth, the last 4 digits of your Aadhaar, or your pincode."
        )

    updates["last_response"] = response
    updates["next_node"] = "end"
    return updates


def collect_payment_amount(state: AgentState) -> dict:
    last_msg = get_last_human_message(state["messages"])
    extracted = extract(last_msg)
    balance = state["account_data"]["balance"]

    amount = None
    if extracted.wants_full_amount:
        amount = balance
    elif extracted.payment_amount is not None:
        amount = round(extracted.payment_amount, 2)

    if amount is not None:
        if amount <= 0:
            return {
                "last_response": "The payment amount must be greater than zero. How much would you like to pay?",
                "next_node": "end",
            }
        if amount > balance:
            return {
                "last_response": (
                    f"The amount ₹{amount:.2f} exceeds your outstanding balance of ₹{balance:.2f}. "
                    f"Please enter an amount up to ₹{balance:.2f}."
                ),
                "next_node": "end",
            }
        return {
            "payment_amount": amount,
            "stage": "CARD_COLLECTION",
            "last_response": (
                f"To process your payment of ₹{amount:.2f}, I'll need your card details. "
                f"Please share your card number, CVV, expiry date, and the name as it appears on your card."
            ),
            "next_node": "end",
        }

    return {
        "last_response": (
            f"Your outstanding balance is ₹{balance:.2f}. "
            f"How much would you like to pay today? "
            f"You can pay the full amount or choose a partial amount."
        ),
        "next_node": "end",
    }


def collect_card_details(state: AgentState) -> dict:
    last_msg = get_last_human_message(state["messages"])
    extracted = extract(last_msg)

    # User is correcting the amount — go back to amount collection
    has_card_fields = any([
        extracted.card_number, extracted.cvv,
        extracted.expiry_month, extracted.expiry_year, extracted.cardholder_name,
    ])
    if (extracted.payment_amount is not None or extracted.wants_full_amount) and not has_card_fields:
        return {"stage": "PAYMENT_AMOUNT", "next_node": "collect_payment_amount"}

    current_card = dict(state.get("card_details") or {})

    invalid_card_note = ""
    if extracted.card_number:
        if len(extracted.card_number) != 16:
            invalid_card_note = (
                f"The card number you provided ({len(extracted.card_number)} digits) "
                f"must be 16 digits — please double-check it. "
            )
        else:
            current_card["card_number"] = extracted.card_number
    if extracted.cvv:
        current_card["cvv"] = extracted.cvv
    if extracted.expiry_month:
        current_card["expiry_month"] = extracted.expiry_month
    if extracted.expiry_year:
        current_card["expiry_year"] = extracted.expiry_year
    if extracted.cardholder_name:
        current_card["cardholder_name"] = extracted.cardholder_name
    elif extracted.full_name and not current_card.get("cardholder_name"):
        # At card collection stage any name the user provides is the cardholder name
        current_card["cardholder_name"] = extracted.full_name

    required = ["card_number", "cvv", "expiry_month", "expiry_year", "cardholder_name"]
    missing = [f for f in required if not current_card.get(f)]

    if not missing:
        errors = validate_card_fields(current_card)
        if errors:
            error_fields = {f for f, _ in errors}
            for f in error_fields:
                current_card.pop(f, None)
            error_msgs = " ".join(msg for _, msg in errors)
            return {
                "card_details": current_card if current_card else None,
                "last_response": f"{error_msgs} Please re-enter the correct details.",
                "next_node": "end",
            }
        return {
            "card_details": current_card,
            "next_node": "process_payment",
        }

    field_labels = {
        "card_number": "card number",
        "cvv": "CVV",
        "expiry_month": "expiry month",
        "expiry_year": "expiry year",
        "cardholder_name": "name on the card",
    }

    if not current_card and not invalid_card_note:
        response = (
            f"To process your payment of ₹{state['payment_amount']:.2f}, I'll need your card details. "
            f"Please share your card number, CVV, expiry date, and the name as it appears on your card."
        )
    else:
        missing_readable = ", ".join(field_labels[f] for f in missing)
        response = f"{invalid_card_note}I still need your {missing_readable}." if missing_readable else invalid_card_note

    return {
        "card_details": current_card if current_card else None,
        "last_response": response,
        "next_node": "end",
    }
