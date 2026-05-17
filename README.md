# Payment Collection Agent

A production-ready conversational AI agent for end-to-end payment collection, built with LangGraph + GPT-4o.

---

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key
- The payment API base URL (provided separately)

### 1. Clone the repository

```bash
git clone https://github.com/vivekx01/payment-collection-agent.git
cd payment-collection-agent
```

### 2. Create a virtual environment and install dependencies

**Using `uv` (recommended):**

```bash
pip install uv
uv venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

uv pip install -r requirements.txt
```

**Using standard `venv`:**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set the following:

```env
OPENAI_API_KEY=sk-...          # Your OpenAI API key
API_BASE_URL=https://...       # Payment API base URL (provided separately)
OPENAI_MODEL=gpt-4o            # Model used by the agent (default: gpt-4o)
JUDGE_MODEL=gpt-4o             # Model used by the LLM evaluator (default: gpt-4o)
```

> The agent will not start without `OPENAI_API_KEY` and `API_BASE_URL`.

---

## Running

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

---

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

## Conversation Flow

```
GREETING → ACCOUNT_LOOKUP → IDENTITY_COLLECTION → PAYMENT_AMOUNT → CARD_COLLECTION → CONCLUDED
```

## Docs

- [`DESIGN.md`](DESIGN.md) — Architecture, key decisions, tradeoffs, and future improvements
- [`CONVERSATIONS.md`](CONVERSATIONS.md) — Full sample conversations (happy path, failures, edge cases)

---

## Test Accounts

| Account ID | Name | DOB | Aadhaar Last 4 | Pincode | Balance |
|---|---|---|---|---|---|
| ACC1001 | Nithin Jain | 1990-05-14 | 4321 | 400001 | ₹1,250.75 |
| ACC1002 | Rajarajeswari Balasubramaniam | 1985-11-23 | 9876 | 400002 | ₹540.00 |
| ACC1003 | Priya Agarwal | 1992-08-10 | 2468 | 400003 | ₹0.00 |
| ACC1004 | Rahul Mehta | 1988-02-29 | 1357 | 400004 | ₹3,200.50 |

---

## Sample Conversations

### Successful Payment

```
You:   Hi
Agent: Hello! I'm here to help with your payment. Could you share your account ID?

You:   my account is ACC1001
Agent: To verify your identity, I'll need your full name and one of: DOB, Aadhaar last 4, or pincode.

You:   Nithin Jain
Agent: Thank you. To complete verification, please provide one of: date of birth, Aadhaar last 4, or pincode.

You:   born 14th May 1990
Agent: Identity verified! Your outstanding balance is ₹1,250.75. How much would you like to pay?

You:   full amount
Agent: To process ₹1,250.75, please share your card number, CVV, expiry date, and cardholder name.

You:   4532 0151 1283 0366 CVV 123 expiry 12/2027 Nithin Jain
Agent: Payment successful! Amount: ₹1,250.75 | Transaction ID: txn_...
```

### Verification Failure (3 attempts)

```
You:   ACC1001
Agent: Please provide your full name and a secondary verification factor.

You:   John Doe  →  Agent: Name doesn't match. 2 attempts remaining.
You:   Jane Doe  →  Agent: Name doesn't match. 1 attempt remaining.
You:   Bob Smith →  Agent: Session closed. Please contact support.
```

### Payment Failure (invalid card)

```
You:   [after verification and amount selection]
Agent: Please share your card details.

You:   card 1234567890123456 CVV 123 exp 12/2027 Nithin Jain
Agent: Card number is invalid (fails Luhn check). Please re-enter your card details.

You:   card 4532015112830366 CVV 123 exp 12/2027 Nithin Jain
Agent: Payment successful!
```

### Edge Case: Zero Balance

```
You:   ACC1003 / Priya Agarwal / DOB 1992-08-10
Agent: Identity verified! Your outstanding balance is ₹0.00 — nothing to pay. Have a great day!
```
