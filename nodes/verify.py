from __future__ import annotations
from state import AgentState

MAX_ATTEMPTS = 3


def verify_identity(state: AgentState) -> dict:
    account = state["account_data"]
    name = state.get("collected_name")
    secondary = state.get("collected_secondary")

    name_match = name == account["full_name"]

    secondary_match = False
    if secondary:
        t, v = secondary["type"], secondary["value"]
        if t == "dob":
            secondary_match = v == account["dob"]
        elif t == "aadhaar":
            secondary_match = v == account["aadhaar_last4"]
        elif t == "pincode":
            secondary_match = v == account["pincode"]

    if name_match and secondary_match:
        balance = account["balance"]
        if balance == 0:
            return {
                "verified": True,
                "conversation_ended": True,
                "stage": "CONCLUDED",
                "last_response": (
                    "Identity verified! ✓\n\n"
                    "Your outstanding balance is ₹0.00. There's nothing to pay at this time. "
                    "Have a great day!"
                ),
                "next_node": "end",
            }
        return {
            "verified": True,
            "stage": "PAYMENT_AMOUNT",
            "last_response": (
                f"Identity verified! ✓\n\n"
                f"Your outstanding balance is ₹{balance:.2f}. "
                f"How much would you like to pay today? "
                f"You can pay the full amount or a partial amount."
            ),
            "next_node": "end",
        }

    attempts = state["verification_attempts"] + 1

    if attempts >= MAX_ATTEMPTS:
        return {
            "verification_attempts": attempts,
            "conversation_ended": True,
            "stage": "CONCLUDED",
            "failure_reason": "max_verification_attempts",
            "last_response": (
                "We were unable to verify your identity after multiple attempts. "
                "For your security, this session has been closed. "
                "Please contact customer support for further assistance."
            ),
            "next_node": "end",
        }

    retries_left = MAX_ATTEMPTS - attempts

    # Always clear both fields on any failure — never confirm which part was correct.
    # Keeping a "correct" field would let an attacker narrow their search across retries.
    if not name_match:
        message = (
            f"The name you entered doesn't match our records. "
            f"Please re-enter your full legal name with correct capitalisation "
            f"(e.g. 'Nithin Jain') along with your verification factor. "
            f"You have {retries_left} attempt(s) remaining."
        )
    else:
        message = (
            f"The verification factor you provided doesn't match our records. "
            f"Please re-enter your name and try a different factor "
            f"(date of birth, Aadhaar last 4 digits, or pincode). "
            f"You have {retries_left} attempt(s) remaining."
        )

    return {
        "verification_attempts": attempts,
        "collected_name": None,
        "collected_secondary": None,
        "last_response": message,
        "next_node": "end",
    }
