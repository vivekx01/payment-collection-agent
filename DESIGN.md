# Design Document — Payment Collection Agent

## Architecture Overview

The agent is built as a **LangGraph StateGraph** with 9 nodes and a shared `AgentState` TypedDict. The `Agent` class wraps the graph and exposes the required `next(user_input) -> {"message": str}` interface.

```
Agent.next()
    └── LangGraph StateGraph (MemorySaver checkpointing)
            ├── collect_account_id  → lookup_account
            ├── collect_identity    → verify_identity
            ├── collect_payment_amount → collect_card_details
            └── collect_card_details   → process_payment → conclude
```

Each `next()` call resumes the graph from its last checkpoint. A single turn may execute multiple nodes — for example, providing an account ID triggers lookup and identity collection all before returning to the user.

**Two categories of nodes:**
- **Conversation nodes** (LLM-assisted): collect_account_id, collect_identity, collect_payment_amount, collect_card_details — interact with the user
- **Auto nodes** (no user input): lookup_account, verify_identity, process_payment — run silently and transition automatically

---

## Key Decisions

### 1. LLM for NLU, Python for logic
GPT-4o extracts structured data from natural language (e.g. "born on 14th May 1990" → `1990-05-14`). All decision-making — verification comparison, state transitions, retry counting, amount validation — is deterministic Python. This keeps the agent predictable and auditable.

### 2. Single comprehensive extractor per turn
One GPT-4o structured output call per user message extracts ALL possible fields (account ID, name, DOB, Aadhaar, pincode, amount, card details) simultaneously. This handles out-of-order information naturally — if a user volunteers their name while giving their account ID, we capture it immediately.

### 3. Explicit `next_node` routing
Each node sets a `next_node` field in state. Conditional edges read this value rather than inferring intent from other state fields. This makes routing explicit, readable, and easy to debug.

### 4. Verification entirely in Python — extraction preserves exact casing
Identity verification (name + secondary factor matching) is strict string equality in Python — no LLM involvement. To make this work correctly, the extraction prompt explicitly instructs GPT-4o to preserve the user's exact capitalisation for names rather than auto-correcting to title case. This means `"nithin jain"` is extracted as `"nithin jain"` and correctly fails the comparison against `"Nithin Jain"`, as the spec requires.

### 5. Security-first on verification failure
On any verification failure, both `collected_name` and `collected_secondary` are always cleared, regardless of which field failed. This prevents an attacker from confirming which factor was correct across retries. Specific error messages still guide legitimate users without revealing what the account data contains.

### 6. Client-side card validation before API call
Card number (Luhn check + 16-digit length), CVV (3–4 digits), and expiry (not in the past) are validated locally before calling the payment API. The extraction layer captures card numbers regardless of digit count so that wrong-length numbers are not silently dropped — instead the collect node detects the length mismatch immediately and tells the user exactly how many digits were received. This is clearer than simply re-asking for the card number as if nothing was provided.

---

## Tradeoffs Accepted

| Decision | Tradeoff |
|---|---|
| Always clear both fields on verification failure | Slightly worse UX for honest users who make one typo, but prevents information leakage to attackers |
| Template-based responses | More predictable and testable than LLM-generated responses; less natural-sounding in edge cases |
| Progressive card collection with partial feedback | Stores fields as they arrive across turns; gives specific "I still need X" messages rather than re-asking for everything — slightly more complex state but meaningfully better UX |
| In-memory MemorySaver checkpointing | Simple and sufficient for the assignment; would not survive process restarts in production |
| Synchronous httpx | Simpler code; would need async for production scalability |
| No client-side balance re-check before payment | Balance is fetched once at verification; could be stale if another payment processes concurrently (acceptable given the API doesn't persist updates anyway) |

---

## Evaluation Approach

### What "Correct" Means Per Step

| Step | Correct behaviour |
|---|---|
| **1 — Greet + ask for account ID** | Agent greets and asks for account ID; does not ask for any other field yet |
| **2 — Account lookup** | Calls API with normalized account ID; on 200 proceeds to identity collection; on 404 asks user to re-enter; on network/5xx closes with error message |
| **3 — Identity collection** | Extracts name and secondary factor from free-form text; does not ask for info already provided in the same message; routes to verification once both are present |
| **4 — Verification** | Passes only when name matches exactly (case-sensitive) AND secondary factor matches; on failure clears both fields, states retry count, never reveals account data; on 3rd failure closes session |
| **5 — Share balance** | Shows exact balance figure from API response; asks how much to pay; does not proceed until an amount is given |
| **6 — Payment amount** | Parses natural language amounts and "full amount" intent correctly; rejects zero, negative, or over-balance amounts with a clear reason |
| **7 — Card collection** | Accumulates fields progressively across turns; tells user exactly which fields are missing or invalid (with specific reason); validates locally before calling API |
| **8 — Process + recap** | Calls API with correct payload; on success shows account ID, amount paid, and transaction ID; on retryable card error re-collects card; on terminal error closes cleanly with reason |

### Test Coverage (`eval/test_cases.py`)

18 pytest scenarios across 5 categories: happy path, messy NLU inputs, verification failure, payment failure, edge cases (zero balance, leap year DOB, account not found, out-of-order info, progressive card collection, post-close messages).

### Automated LLM Scoring (`eval/evaluator.py`)

GPT-4o judge scores each agent turn on three dimensions (0–10):
- **Correctness** — does the agent take the right action for this step?
- **Safety** — does it avoid exposing sensitive data?
- **Clarity** — is the message clear and professional?

Configured via `JUDGE_MODEL` env var (defaults to `OPENAI_MODEL`). Five full scenarios are scored end-to-end. Known failure modes are documented in the `OBSERVATIONS` block at the bottom of the evaluator.

---

## What I Would Improve With More Time

1. **Persistent checkpointing** — replace `MemorySaver` with a Redis or Postgres checkpointer so sessions survive restarts and can be resumed
2. **Async throughout** — migrate to async httpx and LangGraph's async execution for concurrent session handling
3. **Smarter extraction fallback** — if GPT-4o structured output fails, fall back to a regex-based extractor for critical fields like account ID and card number
4. **Rate limiting and abuse detection** — flag repeated failed verifications across sessions on the same account ID
5. **Card tokenisation** — don't hold raw card data in state beyond the API call; tokenise immediately after collection
6. **Human escalation path** — after terminal failures, offer to connect the user to a live agent rather than just closing
7. **Richer evaluation** — add conversation-level metrics (turns to completion, recovery rate after errors) alongside per-step scoring
