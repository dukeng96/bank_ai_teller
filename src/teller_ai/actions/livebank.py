from __future__ import annotations

import random
from typing import Any, Dict

from rich import print as rprint

from teller_ai.config import cfg_path

OTP_EXPECTED_KEY = "otp_expected"

def _log(msg: str) -> None:
    rprint(f"[bold cyan][ACTION][/bold cyan] {msg}")

def run_action(act: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    t = act.get("type")
    name = act.get("name")
    args = act.get("args", {})

    if t == "ui":
        return _ui(name, args)
    if t == "tts":
        return _tts(name, args)
    if t == "api":
        return _api(name, args, ctx)
    return {}

def _ui(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    _log(f"UI.{name}({args})")
    return {}

def _tts(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    text = (args or {}).get("text", "")
    _log(f"TTS.speak \"{text}\"")
    return {}

def _api(name: str, args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    if name == "check_card_stock":
        stock = cfg_path("demo", "stock", default="ok")
        _log(f"API.check_card_stock -> {stock}")
        return {"signal": "stock_ok" if stock == "ok" else "stock_out"}
    if name == "send_otp":
        otp = cfg_path("demo", "otp_fixed") or _gen_otp()
        ctx[OTP_EXPECTED_KEY] = str(otp)
        _log(f"API.send_otp -> sent:{otp} (demo)")
        return {}
    if name == "resend_otp":
        otp = ctx.get(OTP_EXPECTED_KEY) or _gen_otp()
        ctx[OTP_EXPECTED_KEY] = str(otp)
        _log(f"API.resend_otp -> resent:{otp} (demo)")
        return {}
    if name == "verify_otp":
        otp = str(args.get("otp", ""))
        expected = str(ctx.get(OTP_EXPECTED_KEY, ""))
        ok = (otp == expected) if expected else len(otp) in (4, 6)
        _log(f"API.verify_otp({otp}) expected={expected} -> {'ok' if ok else 'wrong'}")
        return {"signal": "otp_ok" if ok else "otp_wrong"}
    if name == "print_card":
        behavior = cfg_path("demo", "print", default="ok")
        _log(f"API.print_card -> {behavior}")
        return {"signal": "printed" if behavior == "ok" else "print_fail"}
    if name == "retract_card":
        _log("API.retract_card")
        return {"signal": "timeout_retract"}
    _log(f"API.{name} (unknown) {args}")
    return {}

def _gen_otp() -> str:
    length = int(cfg_path("demo", "otp_length", default=6))
    return "".join(str(random.randint(0, 9)) for _ in range(length))
