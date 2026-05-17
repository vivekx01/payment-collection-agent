from __future__ import annotations
from state import AgentState


def conclude(state: AgentState) -> dict:
    # If already ended and re-entered (subsequent next() calls after conversation_ended),
    # return a polite closed message.
    if not state.get("last_response"):
        return {
            "last_response": "This conversation has already ended. Thank you!",
            "next_node": "end",
        }
    return {"next_node": "end"}
