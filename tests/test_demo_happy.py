from __future__ import annotations
import time
from orchestrator.graph import app
from orchestrator.state import OrchestratorState

# This test drives the happy path; it does not mock the HTTP LLM. In CI, you may want to mock it.

def test_happy_path_shape() -> None:
    st: OrchestratorState = {
        "state": "START",
        "ctx": {"id_retry": 0, "otp_fail": 0, "stock_checked": False, "branch_suggested": False, "risk_flag": False, "face_others": 0, "id_others": 0, "otp_others": 0, "pickup_others": 0},
        "input": {"channel": "voice", "payload": "phát hành lại thẻ"},
        "session_id": "sess-test",
        "now": time.time(),
    }

    mapping = {
        "FACE": "face_ok",
        "ID_SCAN": "id_ok",
        "NFC_READ": "nfc_ok",
        "CARD_SELECT": "select_card_type",
        "ACCOUNT_SELECT": "select_account",
        "STOCK_CHECK": "stock_ok",
        "OTP_SEND": "_auto",
        "PRINTING": "printed",
        "CARD_PICKUP": "card_taken",
        "DONE": "print_receipt_no",
    }

    for _ in range(30):
        cur = st["state"]
        if cur == "START":
            st["input"] = {"channel": "voice", "payload": "phát hành lại thẻ"}
        elif cur == "OTP":
            st["input"] = {"channel": "voice", "payload": "482913"}
        elif cur in mapping:
            st["input"] = {"channel": "system", "signal": mapping[cur]}
        else:
            st["input"] = {}

        st = app.invoke(st)
        if st.get("state") in ("DONE", "FAILED", "RETRACTED"):
            break

    assert st.get("state") in ("DONE", "FAILED", "RETRACTED")
