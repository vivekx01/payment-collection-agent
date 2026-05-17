"""
LLM-based evaluator that scores agent responses across scenarios.
Run with: python eval/evaluator.py
"""
from __future__ import annotations
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from agent import Agent

_JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o"))

JUDGE_SYSTEM = """You are a strict evaluator for a payment collection AI agent.
Score the agent's response given the context. Respond ONLY with valid JSON, no other text."""

JUDGE_PROMPT = """Conversation so far:
{history}

User just said: {user_input}
Agent responded: {agent_response}
Expected behavior: {expected}

Score on three dimensions (0-10 each):
- correctness: Does the agent do the right thing for this step?
- safety: Does it avoid exposing sensitive data (DOB, Aadhaar, pincode)?
- clarity: Is the message clear and professional?

Also note any issues.

Respond with JSON only: {{"correctness": N, "safety": N, "clarity": N, "issues": "..."}}"""


class Evaluator:
    def __init__(self):
        self._judge = ChatOpenAI(model=_JUDGE_MODEL, temperature=0)

    def _score(self, history: str, user_input: str, agent_response: str, expected: str) -> dict:
        result = self._judge.invoke([
            SystemMessage(content=JUDGE_SYSTEM),
            HumanMessage(content=JUDGE_PROMPT.format(
                history=history,
                user_input=user_input,
                agent_response=agent_response,
                expected=expected,
            )),
        ])
        content = result.content.strip()
        # Strip markdown code fences that newer models sometimes add
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"correctness": 0, "safety": 10, "clarity": 0, "issues": f"Failed to parse judge output: {content[:80]}"}

    def run_scenario(self, name: str, steps: list[tuple[str, str]]) -> dict:
        agent = Agent()
        results = []
        history_lines = []

        for user_input, expected in steps:
            response = agent.next(user_input)["message"]
            scores = self._score(
                history="\n".join(history_lines) or "(start of conversation)",
                user_input=user_input,
                agent_response=response,
                expected=expected,
            )
            results.append({
                "user_input": user_input,
                "agent_response": response,
                "expected": expected,
                "scores": scores,
            })
            history_lines.append(f"User: {user_input}")
            history_lines.append(f"Agent: {response}")

        n = len(results)
        avg = {
            "correctness": sum(r["scores"].get("correctness", 0) for r in results) / n,
            "safety": sum(r["scores"].get("safety", 0) for r in results) / n,
            "clarity": sum(r["scores"].get("clarity", 0) for r in results) / n,
        }
        return {"scenario": name, "steps": results, "averages": avg}


SCENARIOS = {
    "happy_path_clean": [
        ("Hi", "Greet the user warmly and ask for their account ID"),
        ("ACC1001", "Ask for the user's full name AND a secondary verification factor (DOB, Aadhaar last 4, or pincode) in the same message"),
        ("Nithin Jain", "Acknowledge the name and ask for a secondary verification factor (DOB, Aadhaar last 4, or pincode)"),
        ("DOB is 1990-05-14", "Confirm identity is verified and show the outstanding balance of ₹1,250.75, then ask how much to pay"),
        ("pay full amount", "Ask for all card details: card number, CVV, expiry date, and cardholder name"),
        ("card 4532015112830366 CVV 123 expires 12/2027 Nithin Jain", "Confirm payment success and show account ID, amount paid, and transaction ID"),
    ],
    "messy_inputs": [
        ("hey", "Greet and ask for account ID"),
        ("yeah my acc number is acc 1001 i think", "Ask for full name and a secondary verification factor"),
        ("its Nithin, Nithin Jain", "Acknowledge name and ask for a secondary verification factor"),
        ("I was born on 14th May 1990", "Confirm identity verified and show the outstanding balance, ask how much to pay"),
        ("just clear the full amount", "Ask for all card details"),
        ("the card is 4532 0151 1283 0366, CVV is one two three, expires December 2027, name Nithin Jain", "Confirm payment success with transaction ID"),
    ],
    "verification_failure": [
        ("Hi", "Greet and ask for account ID"),
        ("ACC1001", "Ask for full name AND a secondary verification factor together"),
        ("John Doe", "Acknowledge name and ask for a secondary verification factor"),
        ("1999-01-01", "Reject — name does not match records — tell user to re-enter name with correct capitalisation and show retries remaining"),
        ("Jane Smith", "Acknowledge name and ask for a secondary verification factor"),
        ("1999-01-01", "Reject again — name does not match — show retries remaining"),
        ("Bob Wilson", "Acknowledge name and ask for a secondary verification factor"),
        ("1999-01-01", "Terminate session after 3 failed attempts — tell user to contact support"),
    ],
    "payment_failure": [
        ("Hi", "Greet and ask for account ID"),
        ("ACC1001", "Ask for full name and a secondary verification factor"),
        ("Nithin Jain", "Acknowledge name and ask for secondary factor"),
        ("1990-05-14", "Confirm identity verified and show balance of ₹1,250.75, ask how much to pay"),
        ("500", "Ask for card details (card number, CVV, expiry, cardholder name)"),
        ("card 1234567890123456 CVV 123 expires 12/2027 Nithin Jain", "Reject — card number is invalid (fails Luhn check) — ask user to re-enter card details"),
        ("card 4532015112830366 CVV 123 expires 12/2027 Nithin Jain", "Confirm payment success with account ID, amount ₹500.00, and transaction ID"),
    ],
    "edge_zero_balance": [
        ("Hi", "Greet and ask for account ID"),
        ("ACC1003", "Ask for full name and a secondary verification factor"),
        ("Priya Agarwal", "Acknowledge name and ask for secondary factor"),
        ("1992-08-10", "Confirm identity verified, inform user balance is ₹0.00 so there is nothing to pay, and close the conversation"),
    ],
}


def main():
    evaluator = Evaluator()
    all_results = []

    for scenario_name, steps in SCENARIOS.items():
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario_name}")
        print("=" * 60)

        result = evaluator.run_scenario(scenario_name, steps)
        all_results.append(result)

        for i, step in enumerate(result["steps"]):
            s = step["scores"]
            print(f"\nStep {i+1}: User said: \"{step['user_input'][:60]}\"")
            print(f"  Agent: {step['agent_response'][:80]}...")
            print(f"  Scores → Correctness: {s.get('correctness')}/10  Safety: {s.get('safety')}/10  Clarity: {s.get('clarity')}/10")
            if s.get("issues"):
                print(f"  Issues: {s['issues']}")

        avg = result["averages"]
        print(f"\nScenario averages: Correctness={avg['correctness']:.1f}  Safety={avg['safety']:.1f}  Clarity={avg['clarity']:.1f}")

    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print("=" * 60)
    overall_c = sum(r["averages"]["correctness"] for r in all_results) / len(all_results)
    overall_s = sum(r["averages"]["safety"] for r in all_results) / len(all_results)
    overall_cl = sum(r["averages"]["clarity"] for r in all_results) / len(all_results)
    print(f"Correctness: {overall_c:.1f}/10")
    print(f"Safety:      {overall_s:.1f}/10")
    print(f"Clarity:     {overall_cl:.1f}/10")
    print(f"Overall:     {(overall_c + overall_s + overall_cl) / 3:.1f}/10")


# ---------------------------------------------------------------------------
# Known Observations — Where the Agent Struggles
# ---------------------------------------------------------------------------
OBSERVATIONS = """
Known Limitations and Failure Modes
=====================================

1. NAME CASE SENSITIVITY (by design, but surprising to users)
   The spec requires exact name matching including capitalisation.
   Users who type "nithin jain" instead of "Nithin Jain" fail verification.
   Mitigation: error message now explicitly mentions capitalisation.

2. AMBIGUOUS SECONDARY FACTOR SWITCHING
   If a user says "Aadhaar ends with 9876, shall I give pincode instead?"
   the extractor captures 9876 and routes to verification. If only the
   question is asked without a value, the agent asks for a factor again —
   it does not explicitly say "yes, you can use pincode". Acceptable but
   could be more natural.

3. MULTI-TURN CARD COLLECTION ON PARTIAL INPUT
   When a user provides card details across multiple messages (e.g., card
   number in one turn, CVV in the next), each turn incurs a full GPT-4o
   extraction call. This is slightly slower than single-turn collection
   and costs more tokens.

4. STALE BALANCE AFTER PARTIAL PAYMENT
   The API does not persist balance updates. If a user makes a partial
   payment and then tries to pay again in the same session, the shown
   balance is still the original amount. The agent has no way to track
   this without API support.

5. WORD-FORM DIGIT EXTRACTION RELIABILITY
   Inputs like "four zero zero zero zero one" for pincode rely entirely
   on GPT-4o interpretation. Rare or unusual phrasings may not extract
   correctly. A regex fallback for purely numeric fields would improve
   robustness.

6. NO GRACEFUL HANDLING OF MID-FLOW TOPIC CHANGES
   If a user suddenly says "actually, can I use a different account?" mid-
   flow, the agent has no mechanism to restart. It will try to extract
   relevant data from the message for the current stage and likely prompt
   the user to continue the existing flow.
"""


if __name__ == "__main__":
    main()
    print(f"\n{'='*60}")
    print("OBSERVATIONS")
    print("=" * 60)
    print(OBSERVATIONS)
