from __future__ import annotations
from fsm.guards import apply_after, eval_guard

def test_eval_guard() -> None:
    ctx = {"otp_fail": 3}
    assert eval_guard("ctx.otp_fail < 5", ctx) is True
    assert eval_guard("ctx.otp_fail >= 5", ctx) is False

def test_apply_after() -> None:
    ctx = {"otp_fail": 0}
    apply_after("ctx.otp_fail += 1", ctx)
    assert ctx["otp_fail"] == 1
