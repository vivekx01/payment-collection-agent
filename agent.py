from __future__ import annotations
import uuid
from langchain_core.messages import HumanMessage
from graph import build_graph


class Agent:
    def __init__(self):
        self._graph = build_graph()
        self._thread_id = str(uuid.uuid4())
        self._config = {"configurable": {"thread_id": self._thread_id}}
        self._initialized = False

    def next(self, user_input: str) -> dict:
        # Short-circuit if conversation already ended
        if self._initialized:
            snapshot = self._graph.get_state(self._config)
            if snapshot.values.get("conversation_ended", False):
                return {"message": "This conversation has already ended. Thank you!"}

        input_state: dict
        if not self._initialized:
            input_state = {
                "messages": [HumanMessage(content=user_input)],
                "stage": "GREETING",
                "account_id": None,
                "account_data": None,
                "collected_name": None,
                "collected_secondary": None,
                "verified": False,
                "verification_attempts": 0,
                "payment_amount": None,
                "card_details": None,
                "transaction_id": None,
                "last_response": "",
                "conversation_ended": False,
                "failure_reason": None,
                "next_node": None,
            }
            self._initialized = True
        else:
            input_state = {"messages": [HumanMessage(content=user_input)]}

        result = self._graph.invoke(input_state, config=self._config)
        return {"message": result["last_response"]}
