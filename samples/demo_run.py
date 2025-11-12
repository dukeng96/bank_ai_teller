from __future__ import annotations
import sys
import time
from typing import Any, Dict

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
    pending = list(scen)
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
    steps = 0
    while True:
        # Nếu có input dành cho state hiện tại, bơm NGAY rồi tick
        fed = False
        while pending and pending[0][0] == st["state"]:
            st["input"] = pending.pop(0)[1]
            st = tick(st)   # chạy ngay, không để tick trống
            rprint(f"[yellow]STATE:[/yellow] {st.get('state')}  [blue]RESP:[/blue] {st.get('response')}")
            fed = True
            if st.get("state") in ("DONE", "FAILED", "RETRACTED"):
                rprint("[bold green]=== DEMO END ===[/bold green]")
                return

        if not fed:
            # ⚠️ Đừng xoá input nếu đang có system-signal được xếp hàng (ví dụ 'otp_ok')
            queued = st.get("input") or {}
            has_system_signal = queued.get("channel") == "system" and queued.get("signal")
            if not has_system_signal:
                st["input"] = {}
            # Dù có hay không, đều tick để máy tiêu thụ tín hiệu / xử lý timer
            st = tick(st)
            rprint(f"[yellow]STATE:[/yellow] {st.get('state')}  [blue]RESP:[/blue] {st.get('response')}")
            if st.get("state") in ("DONE", "FAILED", "RETRACTED"):
                rprint("[bold green]=== DEMO END ===[/bold green]")
                return

        steps += 1
        if steps > 100:
            rprint("[red]Exceeded 100 steps; abort.[/red]")
            return

if __name__ == "__main__":
    name = "happy"
    run_scenario(name)
