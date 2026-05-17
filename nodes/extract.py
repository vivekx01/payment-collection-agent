from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


class ExtractedData(BaseModel):
    account_id: Optional[str] = Field(None, description="Account ID in ACCXXXX format, normalized")
    full_name: Optional[str] = Field(None, description="Person's complete full name as stated")
    dob: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    aadhaar_last4: Optional[str] = Field(None, description="Exactly 4 digits of Aadhaar")
    pincode: Optional[str] = Field(None, description="Exactly 6-digit pincode")
    payment_amount: Optional[float] = Field(None, description="Payment amount as a float")
    wants_full_amount: bool = Field(False, description="User wants to pay the full balance")
    card_number: Optional[str] = Field(None, description="Card number digits, stripped of spaces and dashes. Extract whatever the user provides even if not exactly 16 digits.")
    cvv: Optional[str] = Field(None, description="CVV digits only")
    expiry_month: Optional[int] = Field(None, description="Card expiry month as integer 1-12")
    expiry_year: Optional[int] = Field(None, description="Card expiry year as 4-digit integer")
    cardholder_name: Optional[str] = Field(None, description="Name printed on the card")


EXTRACTION_SYSTEM = """You are a data extraction assistant for a payment collection system.
Extract ALL relevant payment information from the user's message.

Rules:
- Account IDs: normalize to ACCXXXX format (remove spaces, uppercase). "acc 1001" → "ACC1001", "ACC 1001" → "ACC1001"
- Full name: extract exactly as the user typed it — preserve their capitalisation character-for-character. Do NOT auto-capitalise, title-case, or correct casing. "it's Nithin, Nithin Jain" → "Nithin Jain". "nithin jain" → "nithin jain". "NITHIN JAIN" → "NITHIN JAIN"
- Dates: convert to YYYY-MM-DD. "14th May 1990" → "1990-05-14", "May 14, 90" → "1990-05-14", "14-05-1990" → "1990-05-14"
- Aadhaar last 4: exactly 4 digits. Convert word-form and spaced digits. "last four is 4321" → "4321", "four three two one" → "4321", "4 3 2 1" → "4321"
- Pincode: exactly 6 digits. Convert word-form and spaced digits. "4 0 0 0 0 1" → "400001", "four zero zero zero zero one" → "400001", "4,00,001" → "400001"
- Card number: strip spaces and dashes, extract whatever digits the user provides even if not 16. "4532 0151 1283 0366" → "4532015112830366". "0001 2000 5000" → "000120005000"
- CVV: digits only. Convert word-form. "one two three" → "123", "1 2 3" → "123"
- Expiry: parse month and year. "December 2027" → month=12, year=2027. "12/27" → month=12, year=2027. "12/2027" → month=12, year=2027
- Payment amount: parse to float. "a thousand rupees" → 1000.0. "five hundred" → 500.0. "can I do 500 for now" → 500.0
- "full amount", "pay all", "clear everything", "clear the full amount", "just clear it" → set wants_full_amount=True
- Only extract what is explicitly stated. Return null for anything not mentioned."""


_extractor: Optional[ChatOpenAI] = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(ExtractedData)
    return _extractor


def extract(message: str) -> ExtractedData:
    extractor = _get_extractor()
    return extractor.invoke([
        SystemMessage(content=EXTRACTION_SYSTEM),
        HumanMessage(content=message),
    ])


def get_last_human_message(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""
