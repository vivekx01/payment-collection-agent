from __future__ import annotations
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from state import AgentState
from nodes.collect import collect_account_id, collect_identity, collect_payment_amount, collect_card_details
from nodes.tools import lookup_account, process_payment
from nodes.verify import verify_identity
from nodes.conclude import conclude


def _route(state: AgentState) -> str:
    return state.get("next_node", "end")


def _stage_router(state: AgentState) -> str:
    stage = state.get("stage", "GREETING")
    routing = {
        "GREETING": "collect_account_id",
        "IDENTITY_COLLECTION": "collect_identity",
        "PAYMENT_AMOUNT": "collect_payment_amount",
        "CARD_COLLECTION": "collect_card_details",
        "CONCLUDED": "conclude",
    }
    return routing.get(stage, "collect_account_id")


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("collect_account_id", collect_account_id)
    builder.add_node("lookup_account", lookup_account)
    builder.add_node("collect_identity", collect_identity)
    builder.add_node("verify_identity", verify_identity)
    builder.add_node("collect_payment_amount", collect_payment_amount)
    builder.add_node("collect_card_details", collect_card_details)
    builder.add_node("process_payment", process_payment)
    builder.add_node("conclude", conclude)

    builder.add_conditional_edges(START, _stage_router, {
        "collect_account_id": "collect_account_id",
        "collect_identity": "collect_identity",
        "collect_payment_amount": "collect_payment_amount",
        "collect_card_details": "collect_card_details",
        "conclude": "conclude",
    })

    _node_routing = {
        "lookup_account": "lookup_account",
        "collect_identity": "collect_identity",
        "verify_identity": "verify_identity",
        "collect_card_details": "collect_card_details",
        "collect_payment_amount": "collect_payment_amount",
        "process_payment": "process_payment",
        "end": END,
    }

    builder.add_conditional_edges("collect_account_id", _route, _node_routing)
    builder.add_conditional_edges("lookup_account", _route, _node_routing)
    builder.add_conditional_edges("collect_identity", _route, _node_routing)
    builder.add_conditional_edges("verify_identity", _route, _node_routing)
    builder.add_conditional_edges("collect_payment_amount", _route, _node_routing)
    builder.add_conditional_edges("collect_card_details", _route, _node_routing)
    builder.add_conditional_edges("process_payment", _route, _node_routing)
    builder.add_edge("conclude", END)

    return builder.compile(checkpointer=MemorySaver())
