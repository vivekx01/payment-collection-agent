# Payment Collection Agent

A production-ready conversational AI agent for end-to-end payment collection, built with LangGraph + GPT-4o.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY in .env
# API_BASE_URL is pre-filled in .env.example — change only if needed
```

## Run

**Web UI (recommended):**
```bash
streamlit run ui.py
```

**Interactive CLI:**
```bash
python cli.py
```

**Use the Agent class directly:**
```python
from agent import Agent

agent = Agent()
print(agent.next("Hi"))
print(agent.next("My account is ACC1001"))
```

**Run tests:**
```bash
pytest eval/test_cases.py -v
```

**Run LLM evaluator:**
```bash
python eval/evaluator.py
```

## Docs

- [`DESIGN.md`](DESIGN.md) — Architecture, key decisions, tradeoffs, and future improvements
- [`CONVERSATIONS.md`](CONVERSATIONS.md) — Full sample conversations (happy path, failures, edge cases)

## Architecture

```
agent.py          → Agent class (exposes next() interface)
graph.py          → LangGraph StateGraph definition
state.py          → AgentState TypedDict
nodes/
  extract.py      → GPT-4o structured extraction from natural language
  collect.py      → Conversation nodes (account ID, identity, amount, card)
  tools.py        → API call nodes (lookup_account, process_payment)
  verify.py       → Deterministic identity verification
  conclude.py     → Conversation close node
eval/
  test_cases.py   → pytest test scenarios
  evaluator.py    → LLM-based quality scoring
```

## Flow

```
GREETING → ACCOUNT_LOOKUP → IDENTITY_COLLECTION → PAYMENT_AMOUNT → CARD_COLLECTION → CONCLUDED
```

## Test Accounts

| Account ID | Name | DOB | Aadhaar Last 4 | Pincode | Balance |
|---|---|---|---|---|---|
| ACC1001 | Nithin Jain | 1990-05-14 | 4321 | 400001 | ₹1,250.75 |
| ACC1002 | Rajarajeswari Balasubramaniam | 1985-11-23 | 9876 | 400002 | ₹540.00 |
| ACC1003 | Priya Agarwal | 1992-08-10 | 2468 | 400003 | ₹0.00 |
| ACC1004 | Rahul Mehta | 1988-02-29 | 1357 | 400004 | ₹3,200.50 |

## Sample Conversations

### Successful Payment
```
You: Hi
Agent: Hello! I'm here to help with your payment. Could you share your account ID?

You: my account is ACC1001
Agent: To verify your identity, I'll need your full name and one of: DOB, Aadhaar last 4, or pincode.

You: Nithin Jain
Agent: Thank you. To complete verification, please provide one of: date of birth, Aadhaar last 4, or pincode.

You: born 14th May 1990
Agent: Identity verified! ✓ Your outstanding balance is ₹1,250.75. How much to pay?

You: full amount
Agent: To process ₹1,250.75, please share card number, CVV, expiry, and cardholder name.

You: 4532 0151 1283 0366 CVV 123 expiry 12/2027 Nithin Jain
Agent: Payment successful! ✓ Amount: ₹1,250.75 | Transaction ID: txn_...
```

### Verification Failure (3 attempts)
```
You: ACC1001
Agent: Please provide your full name.

You: John Doe  →  Agent: Doesn't match, 2 attempts left.
You: Jane Doe  →  Agent: Doesn't match, 1 attempt left.
You: Bob Smith →  Agent: Session closed. Please contact support.
```

### Payment Failure (invalid card)
```
You: [after verification and amount]
Agent: Please share card details.

You: card 1234567890123456 CVV 123 exp 12/2027 Nithin Jain
Agent: Card number is invalid. Please re-enter your card details.

You: card 4532015112830366 CVV 123 exp 12/2027 Nithin Jain
Agent: Payment successful! ✓
```

### Edge Case: Zero Balance
```
You: ACC1003 / Priya Agarwal / DOB 1992-08-10
Agent: Identity verified! ✓ Your outstanding balance is ₹0.00. Nothing to pay. Have a great day!
```
