# Payment Collection Agent

A production-ready conversational AI agent for end-to-end payment collection.
Built for a take-home assignment (Agent Engineer role at Prodigal Tech).

## Stack
- **Language:** Python 3.11+
- **LLM:** GPT-4o via `langchain-openai`
- **Agent framework:** `langgraph` (StateGraph with MemorySaver checkpointing)
- **HTTP:** `httpx` for API calls
- **Validation:** `pydantic` v2
- **CLI:** `rich`
- **Package manager:** `uv`
- **Tests:** `pytest`

## Project Structure
```
agent.py          → Agent class — exposes next(user_input) -> {"message": str}
graph.py          → LangGraph StateGraph (nodes + conditional edges)
state.py          → AgentState TypedDict
nodes/
  extract.py      → GPT-4o structured extraction from natural language (ExtractedData)
  collect.py      → LLM conversation nodes: collect_account_id, collect_identity,
                    collect_payment_amount, collect_card_details
  tools.py        → API call nodes: lookup_account, process_payment (httpx)
  verify.py       → Deterministic identity verification (no LLM)
  conclude.py     → Conversation close node
eval/
  test_cases.py   → pytest test cases (18 scenarios)
  evaluator.py    → LLM judge scoring correctness, safety, clarity
cli.py            → Interactive terminal interface
```

## Conversation Flow (8 stages)
```
GREETING → IDENTITY_COLLECTION → PAYMENT_AMOUNT → CARD_COLLECTION → CONCLUDED
               ↑ (lookup_account runs silently between GREETING and IDENTITY_COLLECTION)
               ↑ (verify_identity runs silently between IDENTITY_COLLECTION and PAYMENT_AMOUNT)
               ↑ (process_payment runs silently between CARD_COLLECTION and CONCLUDED)
```

## LangGraph Graph Design
- **9 nodes:** collect_account_id, lookup_account, collect_identity, verify_identity,
  collect_payment_amount, collect_card_details, process_payment, conclude
- **Routing:** each node sets `next_node` in state; `_route()` reads it for conditional edges
- **Stage router:** `_stage_router()` dispatches from START based on current `stage`
- **MemorySaver:** persists state between `next()` calls via `thread_id`
- **Auto-nodes:** lookup_account, verify_identity, process_payment run silently within a turn
- **Multi-node turns:** e.g., giving account ID → lookup → ask identity all in one turn

## Key Design Decisions
- **LLM does:** NLU extraction (messy → structured), response generation
- **Python does:** verification comparison, state transitions, retry counting
- **Verification is strict:** exact name match + one secondary factor (DOB/Aadhaar/Pincode)
- **Name extraction preserves exact casing** — GPT-4o is instructed not to auto-capitalise; "nithin jain" stays "nithin jain" so the strict comparison works correctly
- **Card number extraction captures any digit length** — wrong-length numbers are caught in the collect node with a specific message rather than silently dropped
- **No fuzzy matching** on any verification field
- **Retry limit:** 3 attempts for verification, then terminal failure
- **Sensitive data** (DOB, Aadhaar, pincode) never exposed in responses

## External API
Base URL: `https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com`

- `POST /api/lookup-account` — takes `account_id`, returns account data + balance
- `POST /api/process-payment` — takes account_id, amount, card details; returns transaction_id

Error codes: `account_not_found`, `invalid_amount`, `insufficient_balance`,
`invalid_card`, `invalid_cvv`, `invalid_expiry`

## Test Accounts
| ID | Name | DOB | Aadhaar Last 4 | Pincode | Balance |
|---|---|---|---|---|---|
| ACC1001 | Nithin Jain | 1990-05-14 | 4321 | 400001 | ₹1,250.75 |
| ACC1002 | Rajarajeswari Balasubramaniam | 1985-11-23 | 9876 | 400002 | ₹540.00 |
| ACC1003 | Priya Agarwal | 1992-08-10 | 2468 | 400003 | ₹0.00 |
| ACC1004 | Rahul Mehta | 1988-02-29 | 1357 | 400004 | ₹3,200.50 |

Note: ACC1004 has a leap year DOB (1988-02-29) — intentional edge case.

## Environment
Requires `.env` with (see `.env.example`):
- `OPENAI_API_KEY` — OpenAI API key
- `API_BASE_URL` — payment API base URL (has a default fallback in code)
- `OPENAI_MODEL` — model used by the agent for extraction (default: `gpt-4o`)
- `JUDGE_MODEL` — model used by the LLM evaluator (default: `OPENAI_MODEL`)

## Running
```bash
uv venv && .venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python cli.py                        # interactive
pytest eval/test_cases.py -v         # tests
python eval/evaluator.py             # LLM scoring
```
