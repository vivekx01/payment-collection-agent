# Technical Specification — Payment Collection Agent

**Version:** 1.0  
**Date:** 2026-05-17  
**Role:** Agent Engineer Take-Home Assignment (Prodigal Tech)

---

## 1. Overview

A conversational AI agent that collects payments from users over chat. The agent handles identity verification, payment collection, and API integration while gracefully managing free-form, messy natural language input at every step.

---

## 2. Technology Stack

| Layer | Technology | Version | Reason |
|---|---|---|---|
| Language | Python | 3.11+ | Required by spec (Agent class interface) |
| LLM | GPT-4o | latest | Best-in-class NLU for messy input extraction |
| Agent Framework | LangGraph | >=0.2.0 | Native stateful graph with checkpointing |
| LLM SDK | langchain-openai | >=0.3.0 | ChatOpenAI + structured output |
| HTTP | httpx | >=0.27.0 | Sync client for external API calls |
| Data Validation | pydantic | >=2.7.0 | Structured extraction schema, type safety |
| CLI | rich | >=13.7.0 | Terminal UI |
| Package Manager | uv | latest | Fast dependency resolution |
| Testing | pytest | >=8.0.0 | Automated test scenarios |

---

## 3. Required Interface

The agent exposes exactly this interface (used by automated evaluator):

```python
class Agent:
    def next(self, user_input: str) -> dict:
        """
        Process one turn of the conversation.
        Returns: {"message": str}
        """
```

- All conversation state is maintained internally between calls
- No manual state resets required between turns
- Deterministic and consistent across repeated runs

---

## 4. Conversation Flow

### 4.1 Stages

```
GREETING → IDENTITY_COLLECTION → PAYMENT_AMOUNT → CARD_COLLECTION → CONCLUDED
```

| Stage | Agent is waiting for | Auto-nodes that run |
|---|---|---|
| `GREETING` | Account ID | lookup_account (after ID received) |
| `IDENTITY_COLLECTION` | Full name + secondary factor | verify_identity (after both received) |
| `PAYMENT_AMOUNT` | Payment amount | — |
| `CARD_COLLECTION` | Card details (all 5 fields) | process_payment (after all fields received) |
| `CONCLUDED` | Nothing — terminal | — |

### 4.2 Step-by-step

1. Greet user, ask for account ID
2. Look up account via `POST /api/lookup-account`
3. Collect full name + secondary verification factor
4. Run deterministic verification (in-agent, no API)
5. Share outstanding balance with verified user
6. Collect payment amount (full or partial)
7. Collect card details (number, CVV, expiry, cardholder name)
8. Process payment via `POST /api/process-payment`
9. Communicate outcome (success with transaction ID or failure with reason)

---

## 5. LangGraph Architecture

### 5.1 AgentState

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # full conversation history
    stage: str                        # current stage enum
    account_id: Optional[str]         # normalized e.g. "ACC1001"
    account_data: Optional[dict]      # from lookup API (full_name, dob, aadhaar_last4, pincode, balance)
    collected_name: Optional[str]     # user-claimed name
    collected_secondary: Optional[dict]  # {"type": "dob"|"aadhaar"|"pincode", "value": str}
    verified: bool
    verification_attempts: int
    payment_amount: Optional[float]
    card_details: Optional[dict]      # card_number, cvv, expiry_month, expiry_year, cardholder_name
    transaction_id: Optional[str]
    last_response: str                # message returned to user this turn
    conversation_ended: bool
    failure_reason: Optional[str]
    next_node: Optional[str]          # explicit routing hint set by each node
```

### 5.2 Node Inventory

| Node | Type | Inputs from state | Sets in state |
|---|---|---|---|
| `collect_account_id` | LLM | `messages` | `account_id`, `collected_name`*, `next_node`, `last_response` |
| `lookup_account` | API call | `account_id` | `account_data`, `stage`, `next_node`, `last_response` |
| `collect_identity` | LLM | `messages`, `collected_name`, `collected_secondary` | `collected_name`, `collected_secondary`, `next_node`, `last_response` |
| `verify_identity` | Deterministic | `collected_name`, `collected_secondary`, `account_data` | `verified`, `stage`, `verification_attempts`, `last_response`, `next_node` |
| `collect_payment_amount` | LLM | `messages`, `account_data` | `payment_amount`, `stage`, `next_node`, `last_response` |
| `collect_card_details` | LLM | `messages`, `card_details`, `payment_amount` | `card_details`, `next_node`, `last_response` |
| `process_payment` | API call | `account_id`, `payment_amount`, `card_details` | `transaction_id`, `stage`, `conversation_ended`, `next_node`, `last_response` |
| `conclude` | Passthrough | `last_response` | `next_node` |

*eagerly captured if volunteered out of order

### 5.3 Graph Topology

```
START
  │
  ▼  (_stage_router based on state.stage)
  ├─ GREETING ──────────────────▶ collect_account_id
  ├─ IDENTITY_COLLECTION ───────▶ collect_identity
  ├─ PAYMENT_AMOUNT ────────────▶ collect_payment_amount
  ├─ CARD_COLLECTION ───────────▶ collect_card_details
  └─ CONCLUDED ─────────────────▶ conclude ──▶ END

collect_account_id
  ├─ next_node="lookup_account" ▶ lookup_account
  └─ next_node="end" ───────────▶ END

lookup_account
  ├─ next_node="collect_identity" ▶ collect_identity
  └─ next_node="end" ─────────────▶ END  (404 or error)

collect_identity
  ├─ next_node="verify_identity" ▶ verify_identity
  └─ next_node="end" ────────────▶ END

verify_identity
  └─ next_node="end" ────────────▶ END  (always — sets stage/response itself)

collect_payment_amount
  ├─ next_node="collect_card_details" ▶ collect_card_details
  └─ next_node="end" ─────────────────▶ END

collect_card_details
  ├─ next_node="process_payment" ▶ process_payment
  └─ next_node="end" ────────────▶ END

process_payment
  ├─ next_node="collect_payment_amount" ▶ collect_payment_amount  (insufficient_balance)
  ├─ next_node="collect_card_details" ──▶ collect_card_details    (invalid_card/cvv/expiry)
  └─ next_node="end" ───────────────────▶ END
```

### 5.4 Multi-node Turns

Some `next()` calls execute multiple nodes before returning to the user:

| User message | Nodes executed in one turn |
|---|---|
| "ACC1001" | collect_account_id → lookup_account → collect_identity |
| "Nithin Jain, DOB 1990-05-14" | collect_identity → verify_identity |
| "500 rupees" | collect_payment_amount → collect_card_details |
| "card 4532... CVV 123 exp 12/27 Nithin" | collect_card_details → process_payment |

### 5.5 Checkpointing

`MemorySaver` persists state between `next()` calls using a fixed `thread_id` per `Agent` instance. The graph resumes from the last checkpoint on each call.

---

## 6. Natural Language Extraction

### 6.1 Strategy

Every user message is passed through a single GPT-4o structured extraction call (`ExtractedData` Pydantic model) that attempts to extract ALL relevant fields simultaneously. This handles out-of-order information naturally.

```python
class ExtractedData(BaseModel):
    account_id: Optional[str]       # normalized ACCXXXX
    full_name: Optional[str]
    dob: Optional[str]              # YYYY-MM-DD
    aadhaar_last4: Optional[str]    # exactly 4 digits
    pincode: Optional[str]          # exactly 6 digits
    payment_amount: Optional[float]
    wants_full_amount: bool
    card_number: Optional[str]      # 16 digits, stripped
    cvv: Optional[str]
    expiry_month: Optional[int]
    expiry_year: Optional[int]
    cardholder_name: Optional[str]
```

### 6.2 Normalization Examples

| Raw input | Extracted value | Note |
|---|---|---|
| "acc 1001" | `ACC1001` | |
| "it's Nithin, Nithin Jain" | `Nithin Jain` | casing preserved as typed |
| "nithin jain" | `nithin jain` | casing preserved — will fail verification |
| "born on 14th May 1990" | `1990-05-14` | |
| "May 14, 90" | `1990-05-14` | |
| "4 0 0 0 0 1" | `400001` | |
| "four zero zero zero zero one" | `400001` | word-form digits |
| "4532 0151 1283 0366" | `4532015112830366` | |
| "0001 2000 5000" | `000120005000` | extracted as-is; length validated in collect node |
| "one two three" (CVV) | `123` | |
| "December 2027" | month=12, year=2027 | |
| "a thousand rupees" | `1000.0` | |
| "just clear the full amount" | `wants_full_amount=True` | |

---

## 7. Verification Logic

Implemented entirely in Python (`nodes/verify.py`) — no LLM involvement.

### 7.1 Rules

```python
name_match = collected_name == account_data["full_name"]   # exact, case-sensitive

secondary_match = (
    collected_secondary["value"] == account_data["dob"]          # if type == "dob"
    or collected_secondary["value"] == account_data["aadhaar_last4"]  # if type == "aadhaar"
    or collected_secondary["value"] == account_data["pincode"]   # if type == "pincode"
)

verified = name_match and secondary_match
```

### 7.2 Retry Behaviour

- Max attempts: **3**
- On failure: clear `collected_name` and `collected_secondary`, decrement attempts counter, return error message
- On max retries: set `conversation_ended=True`, `stage=CONCLUDED`, close session
- Sensitive data (DOB, Aadhaar, pincode) is **never** included in error messages

### 7.3 Edge Cases

| Case | Behaviour |
|---|---|
| Zero balance account (ACC1003) | Verified → show ₹0.00 → close (no payment step) |
| Leap year DOB (ACC1004: 1988-02-29) | Extractor normalizes correctly; comparison is string equality |
| Name with prefix ("you can call me Raja...") | LLM extracts full legal name from context |

---

## 8. Payment Handling

### 8.1 Amount Validation (client-side)
- Must be > 0
- Must be ≤ outstanding balance
- Rounded to 2 decimal places

### 8.2 Card Fields Required
| Field | Format |
|---|---|
| `card_number` | 16 digits, no spaces |
| `cvv` | 3-4 digits |
| `expiry_month` | Integer 1–12 |
| `expiry_year` | 4-digit integer |
| `cardholder_name` | String (not validated against account name) |

Card details are collected progressively — partial card state is stored and missing fields are requested individually.

### 8.3 API Error Handling

| Error Code | Action |
|---|---|
| `insufficient_balance` | Clear amount, return to PAYMENT_AMOUNT, ask for lower amount |
| `invalid_card` | Clear card_details, return to CARD_COLLECTION, re-collect |
| `invalid_cvv` | Clear card_details, return to CARD_COLLECTION, re-collect |
| `invalid_expiry` | Clear card_details, return to CARD_COLLECTION, re-collect |
| `invalid_amount` | Clear amount, return to PAYMENT_AMOUNT |
| Network error | Terminal failure, close conversation |
| Other | Terminal failure, close conversation |

---

## 9. External API Reference

**Base URL:** read from `API_BASE_URL` env var (defaults to `https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com`)

### POST /api/lookup-account
```json
Request:  { "account_id": "ACC1001" }
Response 200: { "account_id", "full_name", "dob", "aadhaar_last4", "pincode", "balance" }
Response 404: { "error_code": "account_not_found", "message": "..." }
```

### POST /api/process-payment
```json
Request: {
  "account_id": "ACC1001",
  "amount": 500.00,
  "payment_method": {
    "type": "card",
    "card": { "cardholder_name", "card_number", "cvv", "expiry_month", "expiry_year" }
  }
}
Response 200: { "success": true, "transaction_id": "txn_..." }
Response 422: { "success": false, "error_code": "..." }
```

---

## 10. Evaluation

### 10.1 Automated Tests (`eval/test_cases.py`)

18 pytest test cases covering:

| Category | Tests |
|---|---|
| Happy path | Full amount, partial payment, Aadhaar verification, pincode verification |
| Messy inputs | Spaced account ID, lowercase, repeated name, natural language DOB, short year, "full amount", spaced card number, CVV as words |
| Verification failure | Wrong name, wrong secondary, max retries → session closed |
| Payment failure | Insufficient balance, invalid card retry |
| Edge cases | Zero balance, leap year DOB, account not found, long name, out-of-order name, progressive card collection, post-close messages |

### 10.2 LLM Evaluator (`eval/evaluator.py`)

GPT-4o judge scores each agent response on:

| Metric | Description |
|---|---|
| **Correctness** (0–10) | Does the agent take the right action for this step? |
| **Safety** (0–10) | Does it avoid exposing sensitive data? |
| **Clarity** (0–10) | Is the message clear and professional? |

5 scored scenarios: happy_path_clean, messy_inputs, verification_failure, payment_failure, edge_zero_balance.

---

## 11. Hard Constraints

- Never proceed to payment without `verified == True`
- Never expose `dob`, `aadhaar_last4`, or `pincode` in any response
- Never skip steps even if user volunteers information early
- Verification matching is strict — no fuzzy matching, no case normalization at the comparison layer; extraction preserves exact user-typed casing for names
- Card data is not logged or stored beyond the current API call
- Retry limit for verification: 3 attempts, then terminal close

---

## 12. Known Limitations & Future Improvements

| Limitation | Improvement |
|---|---|
| MemorySaver is in-memory only | Replace with Redis/Postgres checkpointer for production |
| Single thread_id per Agent instance | Support multi-session / resumable sessions |
| No async support | Migrate to async httpx + async LangGraph for scalability |
| GPT-4o extraction called on every turn | Cache extraction results, batch where possible |
| No rate limiting or abuse detection | Add turn limits, anomaly detection |
| Card data held in state until payment | Encrypt or tokenize card fields in state |
| No human escalation path | Add "speak to an agent" exit for terminal failures |
