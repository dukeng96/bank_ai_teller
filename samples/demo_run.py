from __future__ import annotations
import sys
import time
from typing import Dict, Any
from rich import print as rprint

from orchestrator.graph import app
from orchestrator.state import OrchestratorState

SCENARIOS = {
    "happy": [
        ("START", {"channel": "voice", "payload": "tôi muốn phát hành lại thẻ"}),
        ("FACE", {"channel": "system", "signal": "face_ok"}),
        ("ID_SCAN", {"channel": "system", "signal": "id_ok"}),
        ("NFC_READ", {"channel": "system", "signal": "nfc_ok"}),
        ("CARD_SELECT", {"channel": "system", "signal": "select_card_type"}),
        ("ACCOUNT_SELECT", {"channel": "system", "signal": "select_account"}),
        ("STOCK_CHECK", {"channel": "system", "signal": "stock_ok"}),
        ("OTP_SEND", {"channel": "system", "signal": "_auto"}),
        ("OTP", {"channel": "voice", "payload": "482913"}),
        ("PRINTING", {"channel": "system", "signal": "printed"}),
        ("CARD_PICKUP", {"channel": "system", "signal": "card_taken"}),
        ("DONE", {"channel": "system", "signal": "print_receipt_no"}),
    ],
    "stockout": [
        ("START", {"channel": "voice", "payload": "phát hành lại thẻ giúp"}),
        ("FACE", {"channel": "system", "signal": "face_ok"}),
        ("ID_SCAN", {"channel": "system", "signal": "id_ok"}),
        ("NFC_READ", {"channel": "system", "signal": "nfc_ok"}),
        ("CARD_SELECT", {"channel": "system", "signal": "select_card_type"}),
        ("ACCOUNT_SELECT", {"channel": "system", "signal": "select_account"}),
        ("STOCK_CHECK", {"channel": "system", "signal": "stock_out"}),
        ("BRANCH_SELECT", {"channel": "system", "signal": "confirm_branch"}),
        ("OTP_SEND", {"channel": "system", "signal": "_auto"}),
        ("OTP", {"channel": "voice", "payload": "482913"}),
        ("PRINTING", {"channel": "system", "signal": "printed"}),
        ("CARD_PICKUP", {"channel": "system", "signal": "card_taken"}),
        ("DONE", {"channel": "system", "signal": "print_receipt_yes"}),
    ],
    "otp_wrong": [
        ("START", {"channel": "voice", "payload": "tôi bị mất thẻ"}),
        ("FACE", {"channel": "system", "signal": "face_ok"}),
        ("ID_SCAN", {"channel": "system", "signal": "id_ok"}),
        ("NFC_READ", {"channel": "system", "signal": "nfc_ok"}),
        ("CARD_SELECT", {"channel": "system", "signal": "select_card_type"}),
        ("ACCOUNT_SELECT", {"channel": "system", "signal": "select_account"}),
        ("STOCK_CHECK", {"channel": "system", "signal": "stock_ok"}),
        ("OTP_SEND", {"channel": "system", "signal": "_auto"}),
        ("OTP", {"channel": "voice", "payload": "111111"}),
        ("OTP", {"channel": "voice", "payload": "222222"}),
        ("OTP", {"channel": "voice", "payload": "333333"}),
        ("OTP", {"channel": "voice", "payload": "444444"}),
        ("OTP", {"channel": "voice", "payload": "555555"}),
    ],
}


def tick(state: OrchestratorState) -> OrchestratorState:
    return app.invoke(state)


def run_scenario(name: str) -> None:
    scen = SCENARIOS[name]
    st: OrchestratorState = {
        "state": "START",
        "ctx": {
            "id_retry": 0,
            "otp_fail": 0,
            "stock_checked": False,
            "branch_suggested": False,
            "risk_flag": False,
            "face_others": 0,
            "id_others": 0,
            "otp_others": 0,
            "pickup_others": 0,
        },
        "input": {},
        "session_id": f"sess-{int(time.time())}",
        "now": time.time(),
    }

    rprint("[bold green]=== DEMO START ===[/bold green]")
    for (expect_state, user_in) in scen:
        if st["state"] != expect_state:
            st["state"] = expect_state
        st["input"] = user_in
        st = tick(st)
        rprint(f"[yellow]STATE:[/yellow] {st.get('state')}  [blue]RESP:[/blue] {st.get('response')}")
        if st.get("state") in ("DONE", "FAILED", "RETRACTED"):
            break
    rprint("[bold green]=== DEMO END ===[/bold green]")

if __name__ == "__main__":
    name = "happy"
    run_scenario(name)
