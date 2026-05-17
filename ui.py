"""
Streamlit web UI for the Payment Collection Agent.
Run: streamlit run ui.py
"""
from __future__ import annotations
import uuid
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_community.callbacks import get_openai_callback

from graph import build_graph


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Payment Collection Agent",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* Node pills */
.node-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    margin: 2px 1px;
    font-family: monospace;
    white-space: nowrap;
}
.node-collect { background: #e8f0fe; color: #1a56db; border: 1px solid #c3d9ff; }
.node-tool    { background: #fef3c7; color: #d97706; border: 1px solid #fde68a; }
.node-verify  { background: #d1fae5; color: #059669; border: 1px solid #a7f3d0; }
.node-conclude{ background: #ede9fe; color: #7c3aed; border: 1px solid #ddd6fe; }
.arrow { color: #cbd5e1; font-size: 16px; margin: 0 1px; vertical-align: middle; }

/* Stage badge */
.stage-badge {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    font-family: monospace;
    letter-spacing: 0.03em;
}

/* Summary bar */
.summary-bar {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
}

/* Turn history item */
.turn-item {
    border-left: 3px solid #e2e8f0;
    padding: 8px 12px;
    margin-bottom: 10px;
    border-radius: 0 6px 6px 0;
}

/* Muted text */
.muted { color: #94a3b8; font-size: 13px; }

/* Tab label override — make them a bit more readable */
button[data-baseweb="tab"] { font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)


# ── Constants ──────────────────────────────────────────────────────────────────
_INPUT_COST  = 2.50  / 1_000_000
_OUTPUT_COST = 10.00 / 1_000_000

STAGE_COLORS = {
    "GREETING":            ("#dbeafe", "#1e40af"),
    "IDENTITY_COLLECTION": ("#fef9c3", "#92400e"),
    "PAYMENT_AMOUNT":      ("#ffedd5", "#9a3412"),
    "CARD_COLLECTION":     ("#ede9fe", "#5b21b6"),
    "CONCLUDED":           ("#d1fae5", "#064e3b"),
}

NODE_CLASSES = {
    "collect_account_id":     "collect",
    "lookup_account":         "tool",
    "collect_identity":       "collect",
    "verify_identity":        "verify",
    "collect_payment_amount": "collect",
    "collect_card_details":   "collect",
    "process_payment":        "tool",
    "conclude":               "conclude",
}

NODE_LEGEND = (
    '<span class="node-pill node-collect">collect</span> NLU &nbsp;'
    '<span class="node-pill node-tool">tool</span> API call &nbsp;'
    '<span class="node-pill node-verify">verify</span> deterministic &nbsp;'
    '<span class="node-pill node-conclude">conclude</span>'
)


# ── Session state ──────────────────────────────────────────────────────────────
def _init():
    if "graph" not in st.session_state:
        st.session_state.graph              = build_graph()
        st.session_state.thread_id          = str(uuid.uuid4())
        st.session_state.initialized        = False
        st.session_state.greeted            = False
        st.session_state.messages           = []
        st.session_state.turn_history       = []
        st.session_state.last_turn          = None
        st.session_state.agent_state        = {}
        st.session_state.conversation_ended = False
        st.session_state.turn_count         = 0
        st.session_state.session_tokens     = {
            "prompt": 0, "completion": 0, "total": 0, "cost": 0.0,
        }
        st.session_state.processing         = False
        st.session_state.pending_input      = None

_init()


# ── Core invoke ────────────────────────────────────────────────────────────────
def _invoke(user_input: str) -> str:
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    if not st.session_state.initialized:
        input_state = {
            "messages": [HumanMessage(content=user_input)],
            "stage": "GREETING",
            "account_id": None, "account_data": None,
            "collected_name": None, "collected_secondary": None,
            "verified": False, "verification_attempts": 0,
            "payment_amount": None, "card_details": None,
            "transaction_id": None, "last_response": "",
            "conversation_ended": False, "failure_reason": None, "next_node": None,
        }
        st.session_state.initialized = True
    else:
        input_state = {"messages": [HumanMessage(content=user_input)]}

    nodes_executed: list[str] = []
    last_response = ""

    with get_openai_callback() as cb:
        for chunk in st.session_state.graph.stream(
            input_state, config=config, stream_mode="updates"
        ):
            for node_name, node_output in chunk.items():
                if node_name != "__end__":
                    nodes_executed.append(node_name)
                if isinstance(node_output, dict) and node_output.get("last_response"):
                    last_response = node_output["last_response"]

    cost = cb.prompt_tokens * _INPUT_COST + cb.completion_tokens * _OUTPUT_COST

    s = st.session_state.session_tokens
    s["prompt"]     += cb.prompt_tokens
    s["completion"] += cb.completion_tokens
    s["total"]      += cb.total_tokens
    s["cost"]       += cost

    st.session_state.turn_count += 1
    turn_info = {
        "turn":   st.session_state.turn_count,
        "user":   user_input,
        "nodes":  nodes_executed,
        "tokens": {
            "prompt": cb.prompt_tokens, "completion": cb.completion_tokens,
            "total": cb.total_tokens,   "cost": cost,
        },
    }
    st.session_state.turn_history.append(turn_info)
    st.session_state.last_turn = turn_info

    snap = st.session_state.graph.get_state(config)
    st.session_state.agent_state = snap.values
    if snap.values.get("conversation_ended"):
        st.session_state.conversation_ended = True

    return last_response


# ── Helpers ────────────────────────────────────────────────────────────────────
def _sanitize_state(state: dict) -> dict:
    if not state:
        return {}
    out: dict = {}
    skip = {"messages", "last_response", "next_node"}
    for k, v in state.items():
        if k in skip:
            continue
        if k == "account_data" and v:
            out["account_name"] = v.get("full_name", "—")
            out["balance"]      = f"₹{v.get('balance', 0):.2f}"
            continue
        if k == "collected_secondary" and v:
            out[k] = {"type": v["type"], "value": "•••"}
            continue
        if k == "card_details" and v:
            num = v.get("card_number", "")
            out[k] = {
                "card_number":     f"•••• •••• •••• {num[-4:]}" if len(num) >= 4 else "••••",
                "cvv":             "•••",
                "expiry":          f"{v.get('expiry_month','?')}/{v.get('expiry_year','?')}",
                "cardholder_name": v.get("cardholder_name"),
            }
            continue
        out[k] = v
    return out


def _node_html(nodes: list[str]) -> str:
    if not nodes:
        return '<span class="muted">—</span>'
    parts = []
    for i, node in enumerate(nodes):
        cls = NODE_CLASSES.get(node, "collect")
        parts.append(f'<span class="node-pill node-{cls}">{node}</span>')
        if i < len(nodes) - 1:
            parts.append('<span class="arrow">›</span>')
    return "".join(parts)


def _stage_badge_html(stage: str) -> str:
    bg, fg = STAGE_COLORS.get(stage, ("#f1f5f9", "#475569"))
    return f'<span class="stage-badge" style="background:{bg};color:{fg}">{stage}</span>'


# ── Layout ─────────────────────────────────────────────────────────────────────
col_chat, col_hood = st.columns([3, 2], gap="large")


# ─────────────────────────────────────────────────────────────────────────────
# LEFT — Chat
# ─────────────────────────────────────────────────────────────────────────────
with col_chat:
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown("## 💳 Payment Assistant")
    with h2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("↺ Reset", key="reset_btn"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # Auto-greet
    if not st.session_state.greeted:
        with st.spinner("Connecting…"):
            greeting = _invoke("Hello")
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.greeted = True

    # Chat history + thinking bubble
    with st.container(height=520):
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if st.session_state.processing and st.session_state.pending_input:
            with st.chat_message("assistant"):
                with st.spinner(""):
                    reply = _invoke(st.session_state.pending_input)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.processing    = False
            st.session_state.pending_input = None
            st.rerun()

    # Input
    if not st.session_state.conversation_ended:
        if user_text := st.chat_input("Type your message…"):
            st.session_state.messages.append({"role": "user", "content": user_text})
            st.session_state.processing    = True
            st.session_state.pending_input = user_text
            st.rerun()
    else:
        st.info("Conversation ended. Click **↺ Reset** to start a new session.")


# ─────────────────────────────────────────────────────────────────────────────
# RIGHT — Observability
# ─────────────────────────────────────────────────────────────────────────────
with col_hood:
    st.markdown("## 🔍 Observability")

    # ── Always-visible summary strip ──────────────────────────────────────────
    a = st.session_state.agent_state
    stage    = a.get("stage", "GREETING")
    verified = a.get("verified", False)
    attempts = a.get("verification_attempts", 0)
    s        = st.session_state.session_tokens

    c1, c2, c3 = st.columns(3)
    c1.metric("Turn", st.session_state.turn_count)
    c2.metric("Total tokens", f"{s['total']:,}")
    c3.metric("Session cost", f"${s['cost']:.4f}")

    st.markdown(
        f'<div style="margin: 8px 0 16px 0">'
        f'<span style="color:#64748b;font-size:12px;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:.06em">Stage &nbsp;</span>'
        f'{_stage_badge_html(stage)}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_flow, tab_tokens, tab_state, tab_history = st.tabs(
        ["⚡ Flow", "🪙 Tokens", "🗂 State", "📜 History"]
    )

    # ── Tab: Flow ─────────────────────────────────────────────────────────────
    with tab_flow:
        st.markdown("#### Nodes — last turn")
        if st.session_state.last_turn:
            st.markdown(_node_html(st.session_state.last_turn["nodes"]),
                        unsafe_allow_html=True)
        else:
            st.markdown('<span class="muted">Awaiting first turn…</span>',
                        unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Legend**")
        st.markdown(NODE_LEGEND, unsafe_allow_html=True)

        st.divider()

        st.markdown("#### Identity verification")
        if verified:
            st.success("Verified ✓")
        elif attempts > 0:
            rem = 3 - attempts
            st.warning(f"{attempts} / 3 attempts used &nbsp;·&nbsp; {rem} remaining")
            st.progress(attempts / 3)
        else:
            st.markdown('<span class="muted">Not started yet</span>',
                        unsafe_allow_html=True)

    # ── Tab: Tokens ───────────────────────────────────────────────────────────
    with tab_tokens:
        st.markdown("#### Last turn")
        if st.session_state.last_turn:
            t = st.session_state.last_turn["tokens"]
            ta, tb, tc = st.columns(3)
            ta.metric("Prompt",     f"{t['prompt']:,}")
            tb.metric("Completion", f"{t['completion']:,}")
            tc.metric("Cost",       f"${t['cost']:.5f}")
        else:
            st.markdown('<span class="muted">No turns yet</span>',
                        unsafe_allow_html=True)

        st.divider()

        st.markdown("#### Session total")
        sa, sb, sc = st.columns(3)
        sa.metric("Prompt",     f"{s['prompt']:,}")
        sb.metric("Completion", f"{s['completion']:,}")
        sc.metric("Cost",       f"${s['cost']:.4f}")

        st.divider()

        st.markdown("#### Model & runtime")
        tid = st.session_state.thread_id[:8] + "…"
        st.markdown(f"""
| | |
|---|---|
| Model | `gpt-4o` |
| Framework | `LangGraph` + `LangChain` |
| Input price | `$2.50 / 1M tokens` |
| Output price | `$10.00 / 1M tokens` |
| Thread ID | `{tid}` |
""")

    # ── Tab: State ────────────────────────────────────────────────────────────
    with tab_state:
        st.caption("Sensitive fields redacted — DOB, Aadhaar, card CVV not shown.")
        sanitized = _sanitize_state(st.session_state.agent_state)
        if sanitized:
            st.json(sanitized)
        else:
            st.markdown('<span class="muted">No state yet — send a message first.</span>',
                        unsafe_allow_html=True)

    # ── Tab: History ──────────────────────────────────────────────────────────
    with tab_history:
        history = st.session_state.turn_history
        if not history:
            st.markdown('<span class="muted">No turns yet.</span>',
                        unsafe_allow_html=True)
        else:
            for turn in reversed(history):
                preview = turn["user"][:50] + ("…" if len(turn["user"]) > 50 else "")
                t = turn["tokens"]
                with st.expander(
                    f"Turn {turn['turn']} — {preview}",
                    expanded=(turn["turn"] == st.session_state.turn_count),
                ):
                    st.markdown("**Nodes**")
                    st.markdown(_node_html(turn["nodes"]), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    hc1, hc2, hc3 = st.columns(3)
                    hc1.metric("Prompt",     f"{t['prompt']:,}")
                    hc2.metric("Completion", f"{t['completion']:,}")
                    hc3.metric("Cost",       f"${t['cost']:.5f}")
