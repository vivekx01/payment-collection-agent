from __future__ import annotations
import os
import httpx
from state import AgentState

BASE_URL = os.getenv("API_BASE_URL", "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com")
TIMEOUT = 10.0


def lookup_account(state: AgentState) -> dict:
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/api/lookup-account", json={"account_id": state["account_id"]})

        if resp.status_code == 200:
            return {
                "account_data": resp.json(),
                "stage": "IDENTITY_COLLECTION",
                "next_node": "collect_identity",
            }

        if resp.status_code == 404:
            return {
                "account_id": None,
                "last_response": (
                    f"I couldn't find an account with that ID. "
                    f"Could you double-check and provide it again?"
                ),
                "next_node": "end",
            }

        return {
            "conversation_ended": True,
            "stage": "CONCLUDED",
            "failure_reason": f"api_error_{resp.status_code}",
            "last_response": "We're experiencing technical difficulties. Please try again later.",
            "next_node": "end",
        }

    except httpx.RequestError:
        return {
            "conversation_ended": True,
            "stage": "CONCLUDED",
            "failure_reason": "network_error",
            "last_response": "We're unable to connect to our systems right now. Please try again later.",
            "next_node": "end",
        }


def process_payment(state: AgentState) -> dict:
    card = state["card_details"]
    try:
        payload = {
            "account_id": state["account_id"],
            "amount": state["payment_amount"],
            "payment_method": {
                "type": "card",
                "card": {
                    "cardholder_name": card["cardholder_name"],
                    "card_number": card["card_number"],
                    "cvv": card["cvv"],
                    "expiry_month": card["expiry_month"],
                    "expiry_year": card["expiry_year"],
                },
            },
        }
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/api/process-payment", json=payload)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "transaction_id": data["transaction_id"],
                "conversation_ended": True,
                "stage": "CONCLUDED",
                "last_response": (
                    f"Payment successful! ✓\n\n"
                    f"Here's a summary of your transaction:\n"
                    f"  • Account ID    : {state['account_id']}\n"
                    f"  • Amount paid   : ₹{state['payment_amount']:.2f}\n"
                    f"  • Transaction ID: {data['transaction_id']}\n\n"
                    f"Your payment has been processed successfully. "
                    f"Please keep your transaction ID for reference. "
                    f"Thank you and have a great day!"
                ),
                "next_node": "end",
            }

        data = resp.json()
        error_code = data.get("error_code", "unknown")
        balance = state["account_data"]["balance"]

        retryable_card_errors = {
            "invalid_card": "The card number appears to be invalid (failed Luhn check).",
            "invalid_cvv": "The CVV appears to be incorrect.",
            "invalid_expiry": "The card expiry date is invalid or the card has expired.",
        }

        if error_code == "insufficient_balance":
            return {
                "payment_amount": None,
                "stage": "PAYMENT_AMOUNT",
                "last_response": (
                    f"The amount ₹{state['payment_amount']:.2f} exceeds your outstanding balance of ₹{balance:.2f}. "
                    f"Please enter a lower amount."
                ),
                "next_node": "collect_payment_amount",
            }

        if error_code in retryable_card_errors:
            return {
                "card_details": None,
                "stage": "CARD_COLLECTION",
                "last_response": f"{retryable_card_errors[error_code]} Please re-enter your card details.",
                "next_node": "collect_card_details",
            }

        if error_code == "invalid_amount":
            return {
                "payment_amount": None,
                "stage": "PAYMENT_AMOUNT",
                "last_response": "The payment amount is invalid (must be positive with at most 2 decimal places). Please enter a valid amount.",
                "next_node": "collect_payment_amount",
            }

        return {
            "conversation_ended": True,
            "stage": "CONCLUDED",
            "failure_reason": error_code,
            "last_response": "Payment could not be processed. Please contact your bank or try again later.",
            "next_node": "end",
        }

    except httpx.RequestError:
        return {
            "conversation_ended": True,
            "stage": "CONCLUDED",
            "failure_reason": "network_error",
            "last_response": "We're unable to connect to our payment system. Please try again later.",
            "next_node": "end",
        }
