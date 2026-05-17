"""
Automated test cases for the payment collection agent.
Run with: pytest eval/test_cases.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent import Agent


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_full_amount():
    """Successful end-to-end payment with full amount for ACC1001."""
    agent = Agent()
    r = agent.next("Hi")
    assert any(w in r["message"].lower() for w in ["account", "id", "hello", "help"])

    r = agent.next("My account is ACC1001")
    assert "name" in r["message"].lower()

    r = agent.next("Nithin Jain")
    assert any(w in r["message"].lower() for w in ["dob", "aadhaar", "pincode", "date", "verify"])

    r = agent.next("DOB is 1990-05-14")
    assert "verified" in r["message"].lower()
    assert "1,250" in r["message"] or "1250" in r["message"]

    r = agent.next("pay the full amount")
    assert "card" in r["message"].lower()

    r = agent.next("card 4532015112830366 CVV 123 expires 12/2027 name Nithin Jain")
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()


def test_happy_path_partial_payment():
    """Partial payment of ₹500 for ACC1001."""
    agent = Agent()
    agent.next("Hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    r = agent.next("I want to pay 500 rupees")
    assert "card" in r["message"].lower()
    r = agent.next("4532015112830366 CVV 123 expiry December 2027 Nithin Jain")
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()


def test_happy_path_aadhaar_verification():
    """Verify using Aadhaar last 4 instead of DOB."""
    agent = Agent()
    agent.next("Hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    r = agent.next("last four of my aadhaar is 4321")
    assert "verified" in r["message"].lower()


def test_happy_path_pincode_verification():
    """Verify using pincode."""
    agent = Agent()
    agent.next("Hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    r = agent.next("pincode is 400001")
    assert "verified" in r["message"].lower()


# ---------------------------------------------------------------------------
# Messy natural language inputs
# ---------------------------------------------------------------------------

def test_messy_account_id_with_spaces():
    agent = Agent()
    agent.next("hello")
    r = agent.next("yeah my account number is ACC 1001 I think")
    assert "name" in r["message"].lower()


def test_messy_account_id_lowercase():
    agent = Agent()
    agent.next("hi")
    r = agent.next("account id: acc1001")
    assert "name" in r["message"].lower()


def test_messy_name_with_repetition():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    r = agent.next("it's Nithin, Nithin Jain")
    assert any(w in r["message"].lower() for w in ["dob", "aadhaar", "pincode", "verify"])


def test_messy_dob_natural_language():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    r = agent.next("I was born on 14th May 1990")
    assert "verified" in r["message"].lower()


def test_messy_dob_short_year():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    r = agent.next("DOB is May 14, 90")
    assert "verified" in r["message"].lower()


def test_messy_full_amount():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    r = agent.next("just clear the full amount")
    assert "card" in r["message"].lower()


def test_messy_card_number_spaced():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    agent.next("500")
    r = agent.next("the card number is 4532 0151 1283 0366 CVV 123 expires December 2027 Nithin Jain")
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()


def test_messy_cvv_words():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    agent.next("500")
    r = agent.next("card 4532015112830366 CVV is one two three expiry 12/2027 Nithin Jain")
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()


# ---------------------------------------------------------------------------
# Verification failure scenarios
# ---------------------------------------------------------------------------

def test_wrong_name_fails_verification():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    r = agent.next("John Doe")
    assert "dob" in r["message"].lower() or "aadhaar" in r["message"].lower() or "pincode" in r["message"].lower()
    r = agent.next("1990-05-14")
    assert "doesn't match" in r["message"].lower() or "not match" in r["message"].lower() or "unable" in r["message"].lower()


def test_wrong_secondary_fails_verification():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    r = agent.next("DOB is 1999-01-01")
    assert any(w in r["message"].lower() for w in ["match", "incorrect", "doesn't", "unable", "attempt"])


def test_max_retries_terminates_session():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")

    for _ in range(3):
        agent.next("Wrong Name")
        r = agent.next("1999-01-01")

    assert any(w in r["message"].lower() for w in ["unable", "closed", "support", "exceeded", "multiple"])
    # Further calls should indicate conversation ended
    r = agent.next("try again")
    assert "ended" in r["message"].lower() or "already" in r["message"].lower()


# ---------------------------------------------------------------------------
# Payment failure scenarios
# ---------------------------------------------------------------------------

def test_insufficient_balance():
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    r = agent.next("I want to pay 9999 rupees")
    assert "exceed" in r["message"].lower() or "balance" in r["message"].lower()


def test_invalid_card_retry():
    """Invalid card triggers re-collection, then valid card succeeds."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    agent.next("500")
    # Invalid card (fails Luhn check)
    r = agent.next("card 1234567890123456 CVV 123 expires 12/2027 Nithin Jain")
    assert "invalid" in r["message"].lower() or "card" in r["message"].lower()
    # Valid card
    r = agent.next("card 4532015112830366 CVV 123 expires 12/2027 Nithin Jain")
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_zero_balance_account():
    """ACC1003 has zero balance — should close without payment."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1003")
    agent.next("Priya Agarwal")
    r = agent.next("1992-08-10")
    assert "0.00" in r["message"] or "nothing" in r["message"].lower() or "no" in r["message"].lower()


def test_leap_year_dob():
    """ACC1004 Rahul Mehta has DOB 1988-02-29 (leap year)."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1004")
    agent.next("Rahul Mehta")
    r = agent.next("my DOB is 1988-02-29")
    assert "verified" in r["message"].lower()


def test_account_not_found():
    agent = Agent()
    agent.next("hi")
    r = agent.next("ACC9999")
    assert "couldn't find" in r["message"].lower() or "not found" in r["message"].lower() or "no account" in r["message"].lower()


def test_long_name_acc1002():
    """Rajarajeswari Balasubramaniam — long name, exact match required."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1002")
    r = agent.next("you can call me Raja but my full name is Rajarajeswari Balasubramaniam")
    assert any(w in r["message"].lower() for w in ["dob", "aadhaar", "pincode", "verify"])
    r = agent.next("1985-11-23")
    assert "verified" in r["message"].lower()


def test_out_of_order_name_with_account_id():
    """User provides name at the same time as account ID."""
    agent = Agent()
    agent.next("hi")
    r = agent.next("My name is Nithin Jain and account is ACC1001")
    # Should ask for secondary factor, not name (already captured)
    assert any(w in r["message"].lower() for w in ["dob", "aadhaar", "pincode", "verify", "date"])


def test_conversation_already_ended():
    """Calls after conversation ends return polite closed message."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    agent.next("full amount")
    agent.next("card 4532015112830366 CVV 123 expires 12/2027 Nithin Jain")
    r = agent.next("hello again")
    assert "ended" in r["message"].lower() or "already" in r["message"].lower()


def test_card_details_collected_progressively():
    """User provides card details across multiple messages."""
    agent = Agent()
    agent.next("hi")
    agent.next("ACC1001")
    agent.next("Nithin Jain")
    agent.next("1990-05-14")
    agent.next("500")
    agent.next("card 4532015112830366")      # just the number
    agent.next("CVV is 123")                 # CVV
    agent.next("expires December 2027")      # expiry
    r = agent.next("name on card is Nithin Jain")  # cardholder name
    assert "success" in r["message"].lower() or "txn_" in r["message"].lower()
