from __future__ import annotations
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    stage: str                          # GREETING | IDENTITY_COLLECTION | PAYMENT_AMOUNT | CARD_COLLECTION | CONCLUDED
    account_id: Optional[str]
    account_data: Optional[dict]        # from lookup API: full_name, dob, aadhaar_last4, pincode, balance
    collected_name: Optional[str]       # user-provided name for verification
    collected_secondary: Optional[dict] # {"type": "dob"|"aadhaar"|"pincode", "value": str}
    verified: bool
    verification_attempts: int
    payment_amount: Optional[float]
    card_details: Optional[dict]        # card_number, cvv, expiry_month, expiry_year, cardholder_name
    transaction_id: Optional[str]
    last_response: str                  # response to return to user this turn
    conversation_ended: bool
    failure_reason: Optional[str]
    next_node: Optional[str]            # explicit routing hint set by each node
