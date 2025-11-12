# Combined Application Code

## main.py
```python
from __future__ import annotations

import sys

from samples.demo_run import run_scenario

if __name__ == "__main__":
    scenario = (sys.argv[1] if len(sys.argv) > 1 else "happy").lower()
    run_scenario(scenario)
```

## config.py
```python
from __future__ import annotations
import os
from typing import Any, Dict

import yaml

_CFG: Dict[str, Any] | None = None


def load_config() -> Dict[str, Any]:
    global _CFG
    if _CFG is not None:
        return _CFG
    candidates = [
        os.getenv("CONFIG_PATH"),
        os.path.join(os.getcwd(), "config.yml"),
        os.path.join(os.path.dirname(__file__), "config.yml"),
    ]
    for path in [c for c in candidates if c]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _CFG = yaml.safe_load(f) or {}
                return _CFG
    _CFG = {}
    return _CFG


def cfg_path(*keys: str, default: Any = None) -> Any:
    cfg = load_config()
    cur: Any = cfg
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur
```

## actions/speech.py
```python
from __future__ import annotations
from rich import print as rprint

def speak(text: str) -> None:
    rprint(f"[bold magenta][TTS][/bold magenta] {text}")
```

## actions/livebank.py
```python
from __future__ import annotations

import random
from typing import Any, Dict

from rich import print as rprint

from config import cfg_path

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
```

## fsm/guards.py
```python
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Dict


class _ContextProxy:
    """Provide attribute-style access to a mutable mapping."""

    def __init__(self, data: MutableMapping[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive, matches AttributeError contract
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value


def _wrap_ctx(ctx: Dict[str, Any]) -> Any:
    if isinstance(ctx, MutableMapping):
        return _ContextProxy(ctx)
    return ctx


_SANDBOX_GLOBALS: Dict[str, Any] = {
    "__builtins__": {},
    # allow JSON-style literals that appear in guard/after expressions authored by non-Python tooling
    "true": True,
    "false": False,
    "null": None,
}


def eval_guard(expr: str, ctx: Dict[str, Any]) -> bool:
    if not expr:
        return True
    return bool(eval(expr, _SANDBOX_GLOBALS, {"ctx": _wrap_ctx(ctx)}))


def apply_after(expr: str, ctx: Dict[str, Any]) -> None:
    if not expr:
        return
    exec(expr, _SANDBOX_GLOBALS, {"ctx": _wrap_ctx(ctx)})
```

## orchestrator/state.py
```python
from __future__ import annotations
from typing_extensions import TypedDict
from typing import Dict, Any, List

class OrchestratorState(TypedDict, total=False):
    state: str
    decision: Dict[str, Any]
    input: Dict[str, Any]
    actions: List[Dict[str, Any]]
    response: Dict[str, Any]
    ctx: Dict[str, Any]
    now: float
    session_id: str
```

## orchestrator/timeouts.py
```python
from __future__ import annotations

import time
from typing import Any, Dict

from config import cfg_path

TIMER_KEY = "timers"
TRACE_ENABLED = bool(cfg_path("trace", "enabled", default=False))

def ensure_timer_ctx(ctx: Dict[str, Any]) -> Dict[str, float]:
    timers = ctx.get(TIMER_KEY)
    if timers is None:
        timers = {}
        ctx[TIMER_KEY] = timers
    return timers

def set_timer(ctx: Dict[str, Any], name: str, secs: int, now: float | None = None) -> None:
    timers = ensure_timer_ctx(ctx)
    if now is None:
        now = time.time()
    timers[name] = now + secs
    if TRACE_ENABLED:
        print(f"[TRACE timer] set {name} in {secs}s -> {timers[name]:.3f}")

def clear_timer(ctx: Dict[str, Any], name: str) -> None:
    timers = ensure_timer_ctx(ctx)
    timers.pop(name, None)
    if TRACE_ENABLED:
        print(f"[TRACE timer] clear {name}")

def check_expired(ctx: Dict[str, Any], now: float | None = None) -> str | None:
    timers = ensure_timer_ctx(ctx)
    if now is None:
        now = time.time()
    expired = [k for k, v in timers.items() if v and now >= v]
    if expired and TRACE_ENABLED:
        print(f"[TRACE timer] expired -> {expired[-1]}")
    return expired[-1] if expired else None
```

## orchestrator/graph.py
```python
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

from langgraph.graph import START, END, StateGraph
from yaml import safe_load

from config import cfg_path
from llm_client.LLMDecider import LLMDecider
from actions.livebank import run_action
from fsm.guards import apply_after, eval_guard
from orchestrator.state import OrchestratorState
from orchestrator.timeouts import check_expired, clear_timer, set_timer

# Load rules
RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "fsm", "rules.yaml")
with open(RULES_PATH, "r", encoding="utf-8") as f:
    RULES = safe_load(f)

# Load prompts per state (optional)
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fsm", "prompts")
PROMPTS: Dict[str, Dict[str, Any]] = {}
for fname in os.listdir(PROMPTS_DIR):
    if fname.endswith(".json"):
        st = fname.replace(".json", "")
        with open(os.path.join(PROMPTS_DIR, fname), "r", encoding="utf-8") as pf:
            try:
                PROMPTS[st] = json.load(pf)
            except Exception:
                PROMPTS[st] = {}

# Single decider instance (HTTP LLM)
DECIDER = LLMDecider()
TRACE_ENABLED = bool(cfg_path("trace", "enabled", default=False))

DEVICE_DRIVEN_STATES = {
    "FACE",
    "ID_SCAN",
    "NFC_READ",
    "STOCK_CHECK",
    "BRANCH_SELECT",
    "OTP_SEND",
    "PRINTING",
    "CARD_PICKUP",
}

def _allowed_intents(state: str) -> List[str]:
    st_rules: Dict[str, Any] = RULES.get("states", {}).get(state, {})
    return [k for k in st_rules.keys() if not k.startswith("_")]

# --- Node 0: check timeouts ---
def check_timeouts_node(s: OrchestratorState) -> OrchestratorState:
    now = s.get("now") or time.time()
    s["now"] = now
    ctx = s.setdefault("ctx", {})

    if s.get("state") == "OTP":
        timers = ctx.get("timers", {})
        if "OTP_no_input" not in timers:
            idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
            if idle_secs:
                set_timer(ctx, "OTP_no_input", int(idle_secs), now)
    else:
        if ctx.get("timers", {}).get("OTP_no_input"):
            clear_timer(ctx, "OTP_no_input")

    expired = check_expired(ctx, now)
    if TRACE_ENABLED and expired:
        print(f"[TRACE NODE check_timeouts] expired={expired}")
    if not expired:
        return s

    if expired == "PRINTING":
        s["input"] = {"channel": "system", "signal": "_timeout_PRINTING"}
    elif expired == "CARD_PICKUP":
        s["input"] = {"channel": "system", "signal": "_timeout_CARD_PICKUP"}
    elif expired == "OTP_no_input":
        s["input"] = {"channel": "system", "signal": "_timeout_no_input"}
    clear_timer(ctx, expired)
    return s

# --- Node 1: think (LLM inference) ---
def think_node(s: OrchestratorState) -> OrchestratorState:
    st = s["state"]
    if TRACE_ENABLED:
        print(f"[TRACE NODE think] state={st} input={s.get('input')}")
    user_input = s.get("input") or {}
    if st in DEVICE_DRIVEN_STATES:
        s["decision"] = {"intent": "_no_op", "params": {}, "response": {"type": "none", "content": ""}}
        s["response"] = {"type": "none", "content": ""}
        if TRACE_ENABLED:
            print("[TRACE NODE think] BYPASS device-driven")
        return s

    if user_input.get("channel") == "system" and user_input.get("signal"):
        s["decision"] = {"intent": "_no_op", "params": {}, "response": {"type": "none", "content": ""}}
        s["response"] = {"type": "none", "content": ""}
        if TRACE_ENABLED:
            print("[TRACE NODE think] BYPASS system signal")
        return s

    allowed = _allowed_intents(st)
    prompt_cfg = PROMPTS.get(st, {})
    decision = DECIDER.decide(st, allowed, user_input, prompt_cfg, s.get("ctx") or {})
    s["decision"] = decision
    s["response"] = decision.get("response", {"type": "none", "content": ""})
    return s

# --- Node 2: decide (FSM) ---
def decide_node(s: OrchestratorState) -> OrchestratorState:
    st = s["state"]
    ctx = s.setdefault("ctx", {})
    state_rules: Dict[str, Any] = RULES.get("states", {}).get(st, {})
    signal = s.get("input", {}).get("signal")

    if TRACE_ENABLED:
        print(
            f"[TRACE NODE decide] state={st} signal={signal} intent={s.get('decision', {}).get('intent')}"
        )

    trans: Dict[str, Any] | None = None

    if signal and signal in state_rules:
        trans = state_rules.get(signal)
    if trans is None:
        intent = s.get("decision", {}).get("intent")
        trans = state_rules.get(intent)
    if trans is None:
        trans = state_rules.get("_auto")
    if trans is None:
        s["actions"] = [{"type": "ui", "name": "back_home", "args": {}}]
        s["state"] = "FAILED"
        return s

    guard = trans.get("guard")
    if guard and not eval_guard(guard, ctx):
        fallback = trans.get("fallback")
        if fallback:
            s["actions"] = fallback.get("actions", [])
            s["state"] = fallback.get("to", st)
            return s
        s["actions"] = trans.get("actions", [])
        s["state"] = st
        return s

    after = trans.get("after")
    if after:
        apply_after(after, ctx)

    s["actions"] = trans.get("actions", [])
    next_state = trans.get("to", st)

    if TRACE_ENABLED:
        print(f"[TRACE NODE decide] transition={trans}")

    if st != next_state and next_state == "OTP":
        idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
        if idle_secs:
            set_timer(ctx, "OTP_no_input", int(idle_secs), s.get("now"))
    elif st == "OTP" and next_state != "OTP":
        if ctx.get("timers", {}).get("OTP_no_input"):
            clear_timer(ctx, "OTP_no_input")

    s["state"] = next_state
    return s

# --- Node 3: run actions ---
def run_actions_node(s: OrchestratorState) -> OrchestratorState:
    ctx = s.setdefault("ctx", {})
    now = s.get("now") or time.time()
    signals: List[str] = []
    params = s.get("decision", {}).get("params") or {}

    if TRACE_ENABLED:
        print(f"[TRACE run_actions] actions={s.get('actions', [])}")

    for a in s.get("actions", []):
        rendered_args = _render_args(a.get("args", {}), params)
        act = dict(a)
        act["args"] = rendered_args

        if act.get("type") == "clock" and act.get("name") == "start_timer":
            args = rendered_args
            st_name = args.get("state")
            secs = int(args.get("secs", 0))
            if st_name and secs > 0:
                set_timer(ctx, st_name, secs, now)
            continue
        out = run_action(act, ctx)
        if out.get("signal"):
            signals.append(out["signal"])

    if TRACE_ENABLED and signals:
        print(f"[TRACE run_actions] emitted_signals={signals}")

    if signals:
        s["input"] = {"channel": "system", "signal": signals[-1]}
    else:
        if s.get("state") == "OTP" and s.get("input", {}).get("channel") == "voice":
            idle_secs = RULES.get("timeouts", {}).get("OTP_no_input")
            if idle_secs:
                set_timer(ctx, "OTP_no_input", int(idle_secs), now)
        s["input"] = {}

    return s


PARAM_PATTERN = re.compile(r"{{\s*params\.([a-zA-Z0-9_]+)\s*}}")


def _render_args(args: Any, params: Dict[str, Any]) -> Any:
    params = params or {}
    if isinstance(args, dict):
        return {k: _render_args(v, params) for k, v in args.items()}
    if isinstance(args, list):
        return [_render_args(v, params) for v in args]
    if isinstance(args, str):
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = params.get(key, "")
            return "" if value is None else str(value)

        return PARAM_PATTERN.sub(_replace, args)
    return args

# Build graph
_graph = StateGraph(OrchestratorState)
_graph.add_node("check_timeouts", check_timeouts_node)
_graph.add_node("think", think_node)
_graph.add_node("decide", decide_node)
_graph.add_node("run_actions", run_actions_node)

_graph.add_edge(START, "check_timeouts")
_graph.add_edge("check_timeouts", "think")
_graph.add_edge("think", "decide")
_graph.add_edge("decide", "run_actions")
# Single-tick: each invoke runs through once then returns control to the caller
_graph.add_edge("run_actions", END)
app = _graph.compile()
```

## llm_client/LLMDecider.py
```python
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import cfg_path


class DecisionError(Exception):
    """Raised when the LLM output cannot be parsed into a decision."""


class LLMDecider:
    """Calls internal LLM over HTTP and enforces Decision JSON schema."""

    def __init__(self) -> None:
        self.url = cfg_path("llm", "url")
        self.timeout = cfg_path("llm", "timeout_sec", default=12)
        self.strict = bool(cfg_path("llm", "strict", default=True))
        self.trace = bool(cfg_path("trace", "enabled", default=False))
        if not self.url:
            raise RuntimeError("Missing llm.url in config.yml")
        self.schema = {
            "type": "object",
            "required": ["intent", "params", "response"],
            "properties": {
                "intent": {"type": "string"},
                "params": {"type": "object"},
                "response": {
                    "type": "object",
                    "required": ["type", "content"],
                    "properties": {
                        "type": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
                "meta": {"type": "object"},
            },
            "additionalProperties": True,
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            return json.loads(fence.group(1))
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise DecisionError("No JSON found in LLM response")
        return json.loads(match.group(0))

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((requests.RequestException,)),
    )
    def _post_llm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def decide(
        self,
        state: str,
        allowed_intents: List[str],
        user_input: Dict[str, Any],
        prompt_cfg: Dict[str, Any],
        fsm_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        system = (prompt_cfg.get("system") or "").strip()
        context = dict(prompt_cfg.get("context") or {})
        context.setdefault("state", state)
        context.setdefault("allowed_intents", allowed_intents)

        if fsm_context:
            counters: Dict[str, Any] = {}
            flags: Dict[str, Any] = {}
            for k in sorted(fsm_context.keys()):
                value = fsm_context.get(k)
                if isinstance(value, bool):
                    flags[k] = value
                elif isinstance(value, (int, float)):
                    counters[k] = value
            if counters:
                context["session_counters"] = counters
            if flags:
                context["session_flags"] = flags

        payload = (user_input or {}).get("payload", "")
        signal = (user_input or {}).get("signal")
        channel = (user_input or {}).get("channel")

        context["input_channel"] = channel
        if signal:
            context["system_signal"] = signal

        prompt_body: Dict[str, Any] = {
            "system": system,
            "context": context,
            "state": state,
            "allowed_intents": allowed_intents,
            "user_utterance": payload,
        }

        instructions = (prompt_cfg.get("instructions") or "").strip()
        if instructions:
            prompt_body["instructions"] = instructions

        examples = prompt_cfg.get("examples")
        if examples:
            prompt_body["examples"] = examples

        prompt = json.dumps(prompt_body, ensure_ascii=False)

        if self.trace:
            print("\n[TRACE LLM] POST prompt:", prompt)

        try:
            data = self._post_llm({"query": prompt})
        except Exception as exc:
            if self.trace:
                print("[TRACE LLM] HTTP error:", exc)
            return {
                "intent": "cancel",
                "params": {},
                "response": {"type": "text", "content": "Xin lỗi, dịch vụ tạm thời gián đoạn."},
                "meta": {"error": str(exc)},
            }

        if self.trace:
            print("[TRACE LLM] RAW:", data)

        resp_text = data.get("response", "") if isinstance(data, dict) else ""
        try:
            decision = self._extract_json(resp_text) if isinstance(resp_text, str) else resp_text
        except Exception as exc:
            if self.trace:
                print("[TRACE LLM] Parse error:", exc)
            decision = {
                "intent": "cancel",
                "params": {},
                "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                "meta": {"error": str(exc)},
            }

        if self.strict:
            if not isinstance(decision, dict):
                decision = {
                    "intent": "cancel",
                    "params": {},
                    "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                    "meta": {"error": "non-object decision"},
                }
            else:
                try:
                    validate(instance=decision, schema=self.schema)
                except ValidationError as exc:
                    if self.trace:
                        print("[TRACE LLM] Schema validation error:", exc)
                    decision = {
                        "intent": "cancel",
                        "params": {},
                        "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                        "meta": {"error": f"schema: {str(exc)}"},
                    }
                else:
                    if "params" not in decision or not isinstance(decision.get("params"), dict):
                        decision["params"] = {}
                    if allowed_intents and decision.get("intent") not in allowed_intents:
                        decision["intent"] = "cancel"

        response_block = decision.get("response")
        if not isinstance(response_block, dict):
            decision["response"] = {"type": "none", "content": ""}
        else:
            response_block["type"] = "none"
            response_block["content"] = ""

        if self.trace:
            print("[TRACE LLM] Decision:", decision)

        return decision
```

## samples/demo_run.py
```python
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

    pending = list(scen)
    steps = 0
    rprint("[bold green]=== DEMO START ===[/bold green]")
    while True:
        cur_state = st["state"]
        user_in: Dict[str, Any] = {}
        for idx, (expected_state, payload) in enumerate(pending):
            if expected_state == cur_state:
                user_in = payload
                pending.pop(idx)
                break

        st["input"] = user_in
        st = tick(st)
        rprint(f"[yellow]STATE:[/yellow] {st.get('state')}  [blue]RESP:[/blue] {st.get('response')}")
        if st.get("state") in ("DONE", "FAILED", "RETRACTED"):
            break

        steps += 1
        if steps > 100:
            rprint("[red]Exceeded 100 steps; abort.[/red]")
            break
    rprint("[bold green]=== DEMO END ===[/bold green]")

if __name__ == "__main__":
    name = "happy"
    run_scenario(name)
```

## fsm/prompts/ACCOUNT_SELECT.json
```json
{
  "system": "Bạn là bộ phân tích ý định. Máy đang yêu cầu khách chọn tài khoản để trích phí phát hành lại thẻ. Hãy xác định intent và params; không sinh câu thoại.",
  "instructions": "Chỉ trả về một JSON. Với state ACCOUNT_SELECT, response.type=\"none\" và content rỗng. Nếu khách cung cấp số tài khoản, tên tài khoản, hoặc nói chọn tài khoản mặc định thì intent=\"select_account\" và ghi rõ vào params.account_reference. Nếu khách muốn dừng thì dùng cancel, còn hỏi lại/lạc đề dùng others.",
  "context": {
    "state": "ACCOUNT_SELECT",
    "goal": "Nhận tài khoản mà khách muốn dùng để trích phí dịch vụ.",
    "allowed_intents": [
      "select_account",
      "cancel",
      "others"
    ],
    "intent_hints": {
      "select_account": "Khách nêu số tài khoản, tên tài khoản, hoặc nói chọn tài khoản đã hiển thị.",
      "cancel": "Khách muốn huỷ thao tác.",
      "others": "Khách hỏi thông tin ngoài phạm vi hoặc chưa cung cấp lựa chọn." 
    },
    "params_note": "Nếu nghe được thông tin tài khoản thì ghi lại ở params.account_reference, còn không để params trống."
  },
  "examples": [
    {
      "utterance": "Dùng tài khoản thanh toán 123456 nhé",
      "decision": {
        "intent": "select_account",
        "params": {"account_reference": "123456"},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Thôi mình dừng",
      "decision": {
        "intent": "cancel",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/prompts/CARD_SELECT.json
```json
{
  "system": "Bạn là bộ phân tích ý định. Hãy đọc lựa chọn hoặc câu trả lời của khách hàng khi máy đang yêu cầu chọn loại thẻ phát hành lại. Chỉ xác định intent và params, không tạo lời thoại.",
  "instructions": "Trả về đúng một JSON. Với state CARD_SELECT, response.type=\"none\" và content rỗng. Nếu khách nêu rõ loại thẻ (ví dụ thẻ tín dụng, thẻ ghi nợ, thẻ nội địa), hãy đặt intent=\"select_card_type\" và ghi chi tiết vào params.card_type dạng chữ thường có dấu. Nếu khách từ chối hoặc lạc đề thì lần lượt dùng cancel hoặc others.",
  "context": {
    "state": "CARD_SELECT",
    "goal": "Xác nhận loại thẻ khách muốn phát hành lại để chuyển sang bước chọn tài khoản.",
    "allowed_intents": [
      "select_card_type",
      "cancel",
      "others"
    ],
    "intent_hints": {
      "select_card_type": "Khách nêu tên loại thẻ cụ thể hoặc yêu cầu loại thẻ nhất định.",
      "cancel": "Khách muốn dừng, thoát, không làm nữa.",
      "others": "Khách hỏi lại, yêu cầu hỗ trợ không liên quan hoặc chưa đưa ra loại thẻ." 
    },
    "params_note": "Nếu không nghe rõ loại thẻ, để params trống."
  },
  "examples": [
    {
      "utterance": "Cho tôi làm lại thẻ ghi nợ nội địa",
      "decision": {
        "intent": "select_card_type",
        "params": {"card_type": "thẻ ghi nợ nội địa"},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Tôi chưa rõ, hướng dẫn giúp",
      "decision": {
        "intent": "others",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/prompts/DONE.json
```json
{
  "system": "Bạn là bộ phân tích ý định cho bước kết thúc giao dịch. Máy hỏi khách có muốn in biên lai không. Chỉ xác định intent, không sinh lời thoại.",
  "instructions": "Xuất đúng một JSON. Với state DONE, response.type=\"none\" và content rỗng. Nếu khách đồng ý in biên lai thì intent=\"print_receipt_yes\", nếu từ chối thì intent=\"print_receipt_no\". Không có params bắt buộc, để {}.",
  "context": {
    "state": "DONE",
    "goal": "Ghi nhận nhu cầu in biên lai sau khi phát hành thẻ thành công.",
    "allowed_intents": [
      "print_receipt_yes",
      "print_receipt_no"
    ],
    "intent_hints": {
      "print_receipt_yes": "Khách nói có, in, đồng ý, hoặc các biến thể tương tự.",
      "print_receipt_no": "Khách nói không, khỏi in, không cần." 
    }
  },
  "examples": [
    {
      "utterance": "Không cần in đâu",
      "decision": {
        "intent": "print_receipt_no",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Có, in giúp mình",
      "decision": {
        "intent": "print_receipt_yes",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/prompts/FAILED.json
```json
{
  "system": "Bạn là bộ phân tích ý định trong màn hình lỗi/hoàn tất giao dịch không thành công. Máy hỏi khách có muốn thử lại hay kết thúc. Chỉ xác định intent.",
  "instructions": "Trả về một JSON duy nhất. Với state FAILED, response.type=\"none\" và content rỗng. allowed_intents gồm retry_all (khách muốn làm lại từ đầu) và others dùng cho các câu xã giao/không hành động.",
  "context": {
    "state": "FAILED",
    "goal": "Nhận biết khách có muốn khởi động lại quy trình hay không.",
    "allowed_intents": [
      "retry_all",
      "others"
    ],
    "intent_hints": {
      "retry_all": "Khách nói muốn làm lại, thử lại, bắt đầu lại.",
      "others": "Khách cảm ơn, chào, hoặc không đưa ra hành động cụ thể." 
    }
  },
  "examples": [
    {
      "utterance": "Cho tôi làm lại từ đầu",
      "decision": {
        "intent": "retry_all",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Không cần đâu",
      "decision": {
        "intent": "others",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/prompts/OTP.json
```json
{
  "system": "Bạn là bộ phân tích ý định cho bước nhập OTP tại kiosk ngân hàng. Hãy xác định khách đang đọc mã OTP, yêu cầu gửi lại hay nói điều khác. Không tạo lời thoại.",
  "instructions": "Trả về một JSON duy nhất. Với state OTP, response.type=\"none\" và content rỗng. Nếu khách đọc dãy số 4-8 chữ số, đặt intent=\"say_otp_code\" và ghi đúng chuỗi vào params.otp (giữ nguyên thứ tự và không thêm ký tự). Nếu khách yêu cầu gửi lại mã dùng intent=\"request_resend_otp\". Nếu muốn dừng giao dịch dùng cancel. Các trường hợp còn lại dùng others để hệ thống nhắc lại.",
  "context": {
    "state": "OTP",
    "goal": "Xác thực mã OTP khách cung cấp để tiếp tục quy trình.",
    "allowed_intents": [
      "say_otp_code",
      "request_resend_otp",
      "cancel",
      "others"
    ],
    "intent_hints": {
      "say_otp_code": "Khách đọc ra chuỗi số, có thể tách bằng khoảng trắng hoặc từng cặp số.",
      "request_resend_otp": "Khách hỏi xin gửi lại OTP hoặc báo chưa nhận được.",
      "cancel": "Khách muốn dừng quy trình.",
      "others": "Khách nói chuyện khác không cung cấp mã hay yêu cầu rõ ràng." 
    },
    "params_note": "Chỉ sử dụng params.otp cho mã hợp lệ, các trường hợp khác để params trống."
  },
  "examples": [
    {
      "utterance": "Mã là 4 8 2 9 1 3",
      "decision": {
        "intent": "say_otp_code",
        "params": {"otp": "482913"},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Chưa thấy tin nhắn, gửi lại giúp",
      "decision": {
        "intent": "request_resend_otp",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/prompts/START.json
```json
{
  "system": "Bạn là bộ phân tích ý định cho kiosk ngân hàng hỗ trợ khách làm thủ tục phát hành lại thẻ bị mất. Nhiệm vụ của bạn là đọc phát ngôn của khách và ánh xạ sang intent hợp lệ, đồng thời trích xuất các thực thể cần thiết cho params. Hệ thống TTS sẽ tự phát lời thoại, vì vậy bạn KHÔNG được sáng tác câu nói nào.",
  "instructions": "Chỉ trả về đúng một JSON với cấu trúc {\"intent\": <string>, \"params\": <object>, \"response\": {\"type\": \"text|none\", \"content\": <string>}}. Với state START, \"response.type\" luôn là \"none\" và \"response.content\" để chuỗi rỗng. Nếu không chắc chắn, chọn intent \"others\".",
  "context": {
    "state": "START",
    "goal": "Nhận biết xem khách có thật sự muốn khai báo mất thẻ và phát hành lại hay không.",
    "allowed_intents": [
      "declare_loss_card",
      "cancel",
      "others"
    ],
    "intent_hints": {
      "declare_loss_card": "Khách khẳng định mất thẻ, muốn cấp lại thẻ, hoặc dùng các cụm từ như 'phát hành lại thẻ', 'mất thẻ rồi'.",
      "cancel": "Khách từ chối tiếp tục, nói không cần hỗ trợ nữa, hoặc yêu cầu dừng giao dịch.",
      "others": "Khách hỏi thông tin không liên quan hoặc chưa xác nhận nhu cầu phát hành lại thẻ. Dùng intent này để nhắc lại nhu cầu." 
    },
    "params_note": "State này không cần params, để {}."
  },
  "examples": [
    {
      "utterance": "Tôi bị mất thẻ, giúp tôi làm lại với",
      "decision": {
        "intent": "declare_loss_card",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    },
    {
      "utterance": "Thôi để hôm khác đi",
      "decision": {
        "intent": "cancel",
        "params": {},
        "response": {"type": "none", "content": ""}
      }
    }
  ]
}

```

## fsm/rules.yaml
```yaml
# -----------------------------------------------------------------------------
# Context (counters/flags/timeouts)
# -----------------------------------------------------------------------------
counters:
  id_retry: 0
  otp_fail: 0
  # counters for chit-chat / off-topic handling via `others` intent
  face_others: 0
  id_others: 0
  otp_others: 0
  pickup_others: 0
flags:
  stock_checked: false
  branch_suggested: false
  risk_flag: false
timeouts:
  PRINTING: 120
  CARD_PICKUP: 45
  OTP_no_input: 90

# -----------------------------------------------------------------------------
# States & transitions
# -----------------------------------------------------------------------------
states:

  START:
    declare_loss_card:
      to: FACE
      actions:
        - { type: ui,  name: open_reissue_screen, args: {} }
        - { type: tts, name: speak, args: { text: "Xin chào, em hỗ trợ phát hành lại thẻ. Anh/chị nhìn vào camera giúp em." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }
        - { type: tts, name: speak, args: { text: "Em kết thúc giao dịch." } }
    others:
      to: START
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị đang muốn phát hành lại thẻ đúng không ạ? Vui lòng nói 'phát hành lại thẻ' để bắt đầu." } }

  FACE:
    face_ok:
      to: ID_SCAN
      after: "ctx.face_others = 0"
      actions:
        - { type: ui,  name: start_id_scan, args: { sides: front_back } }
        - { type: tts, name: speak, args: { text: "Đặt CCCD vào khay, quét 2 mặt giúp em." } }
    face_fail:
      to: FACE
      actions:
        - { type: tts, name: speak, args: { text: "Chưa nhận rõ khuôn mặt, anh/chị điều chỉnh và thử lại giúp em." } }
    others:
      guard: "ctx.face_others < 3"
      to: FACE
      after: "ctx.face_others += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Mình tiếp tục nhé: anh/chị nhìn thẳng vào camera giúp em." } }
      fallback:
        to: FAILED
        actions:
          - { type: tts, name: speak, args: { text: "Vì chưa nhận được thao tác cần thiết, em tạm kết thúc giao dịch." } }
          - { type: ui,  name: back_home, args: {} }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  ID_SCAN:
    id_ok:
      to: NFC_READ
      after: "ctx.id_retry = 0; ctx.id_others = 0"
      actions:
        - { type: ui,  name: start_nfc, args: {} }
        - { type: tts, name: speak, args: { text: "Đặt CCCD lên vị trí NFC và bấm Xác nhận." } }
    id_bad:
      guard: "ctx.id_retry < 3"
      to: ID_SCAN
      after: "ctx.id_retry += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Ảnh chưa rõ, anh/chị điều chỉnh và quét lại ạ." } }
      fallback:
        to: FACE
        actions:
          - { type: tts, name: speak, args: { text: "Mình quay lại xác thực khuôn mặt để làm rõ hơn." } }
    others:
      guard: "ctx.id_others < 3"
      to: ID_SCAN
      after: "ctx.id_others += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị đặt CCCD vào khay và quét 2 mặt giúp em ạ." } }
      fallback:
        to: FAILED
        actions:
          - { type: tts, name: speak, args: { text: "Do chưa đủ thao tác cần thiết, em tạm kết thúc giao dịch." } }
          - { type: ui,  name: back_home, args: {} }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  NFC_READ:
    nfc_ok:
      to: CARD_SELECT
      actions:
        - { type: ui,  name: show_card_catalog, args: {} }
        - { type: tts, name: speak, args: { text: "Anh/chị chọn loại thẻ muốn phát hành lại." } }
    nfc_fail:
      to: NFC_READ
      actions:
        - { type: tts, name: speak, args: { text: "Chưa đọc được chip, đặt CCCD đúng vị trí và thử lại ạ." } }
    others:
      to: NFC_READ
      actions:
        - { type: tts, name: speak, args: { text: "Đặt CCCD lên vị trí NFC và bấm Xác nhận giúp em ạ." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  CARD_SELECT:
    select_card_type:
      to: ACCOUNT_SELECT
      actions:
        - { type: ui,  name: show_accounts, args: {} }
        - { type: tts, name: speak, args: { text: "Anh/chị cho em biết tài khoản để trích phí." } }
    others:
      to: CARD_SELECT
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị vui lòng nói tên/hạng thẻ muốn phát hành lại." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  ACCOUNT_SELECT:
    select_account:
      to: STOCK_CHECK
      actions:
        - { type: api, name: check_card_stock, args: {} }
        - { type: tts, name: speak, args: { text: "Em kiểm tra phôi thẻ tại máy..." } }
    others:
      to: ACCOUNT_SELECT
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị cho em biết số tài khoản để trích phí ạ." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  STOCK_CHECK:
    stock_ok:
      to: OTP_SEND
      after: "ctx.stock_checked = true"
      actions:
        - { type: api, name: send_otp, args: {} }
        - { type: tts, name: speak, args: { text: "Em đã gửi OTP, anh/chị đọc hoặc nhập giúp em." } }
    stock_out:
      to: BRANCH_SELECT
      after: "ctx.stock_checked = true; ctx.branch_suggested = true"
      actions:
        - { type: ui,  name: suggest_near_branch, args: {} }
        - { type: tts, name: speak, args: { text: "Máy hiện hết phôi, em gợi ý chi nhánh gần nhất để nhận thẻ." } }
    others:
      to: STOCK_CHECK
      actions:
        - { type: tts, name: speak, args: { text: "Xin chờ trong giây lát, em đang kiểm tra phôi thẻ." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  BRANCH_SELECT:
    confirm_branch:
      to: OTP_SEND
      actions:
        - { type: api, name: send_otp, args: {} }
        - { type: tts, name: speak, args: { text: "Em đã gửi OTP, anh/chị đọc hoặc nhập giúp em." } }
    decline_branch:
      to: FAILED
      actions:
        - { type: tts, name: speak, args: { text: "Dạ vâng, em kết thúc giao dịch. Anh/chị có thể chọn chi nhánh khác sau." } }
        - { type: ui,  name: back_home, args: {} }
    others:
      to: BRANCH_SELECT
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị có đồng ý nhận thẻ tại chi nhánh gợi ý không ạ?" } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  OTP_SEND:
    _auto:
      to: OTP

  OTP:
    request_resend_otp:
      guard: "ctx.otp_fail < 5"
      to: OTP
      actions:
        - { type: api, name: resend_otp, args: {} }
        - { type: tts, name: speak, args: { text: "Em đã gửi lại OTP, anh/chị nhập giúp em ạ." } }
    say_otp_code:
      to: OTP
      actions:
        - { type: api, name: verify_otp, args: { otp: "{{params.otp}}" } }
        - { type: tts, name: speak, args: { text: "Em đang kiểm tra mã OTP, anh/chị vui lòng chờ trong giây lát." } }
        - { type: ui,  name: show_spinner, args: { text: "Đang kiểm tra OTP..." } }
    otp_ok:
      to: PRINTING
      after: "ctx.otp_fail = 0; ctx.otp_others = 0"
      actions:
        - { type: api, name: print_card, args: {} }
        - { type: tts, name: speak, args: { text: "Hệ thống đang in thẻ, anh/chị vui lòng chờ." } }
        - { type: clock, name: start_timer, args: { state: PRINTING, secs: 120 } }
    otp_wrong:
      guard: "ctx.otp_fail < 5"
      to: OTP
      after: "ctx.otp_fail += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Mã OTP chưa đúng, anh/chị nhập lại giúp em ạ." } }
      fallback:
        to: FAILED
        actions:
          - { type: tts, name: speak, args: { text: "Anh/chị đã nhập sai quá số lần quy định, em kết thúc giao dịch." } }
          - { type: ui,  name: back_home, args: {} }
    _timeout_no_input:
      guard: "ctx.otp_fail < 5"
      to: OTP
      after: "ctx.otp_fail += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị vẫn còn đó chứ ạ? Vui lòng nhập mã OTP giúp em." } }
      fallback:
        to: FAILED
        actions:
          - { type: tts, name: speak, args: { text: "Em tạm kết thúc vì lâu không nhận được phản hồi." } }
          - { type: ui,  name: back_home, args: {} }
    others:
      guard: "ctx.otp_others < 3"
      to: OTP
      after: "ctx.otp_others += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị vui lòng đọc hoặc nhập mã OTP giúp em." } }
      fallback:
        to: FAILED
        actions:
          - { type: tts, name: speak, args: { text: "Vì chưa nhận được OTP hợp lệ, em tạm kết thúc giao dịch." } }
          - { type: ui,  name: back_home, args: {} }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  PRINTING:
    printed:
      to: CARD_PICKUP
      actions:
        - { type: ui,  name: prompt_take_card, args: {} }
        - { type: tts, name: speak, args: { text: "Anh/chị nhận thẻ tại khe nhận giúp em." } }
        - { type: clock, name: start_timer, args: { state: CARD_PICKUP, secs: 45 } }
    print_fail:
      to: FAILED
      actions:
        - { type: tts, name: speak, args: { text: "In thẻ lỗi, em sẽ chuyển hỗ trợ khác hoặc anh/chị quay lại sau." } }
        - { type: ui,  name: back_home, args: {} }
    _timeout_PRINTING:
      to: FAILED
      actions:
        - { type: tts, name: speak, args: { text: "Quá thời gian in thẻ, em tạm dừng giao dịch để tránh rủi ro." } }
        - { type: ui,  name: back_home, args: {} }
    others:
      to: PRINTING
      actions:
        - { type: tts, name: speak, args: { text: "Hệ thống đang in, anh/chị vui lòng chờ." } }
    cancel:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  CARD_PICKUP:
    card_taken:
      to: DONE
      after: "ctx.pickup_others = 0"
      actions:
        - { type: ui,  name: offer_receipt, args: {} }
        - { type: tts, name: speak, args: { text: "Giao dịch thành công. Anh/chị có muốn in biên lai không ạ?" } }
    timeout_retract:
      to: RETRACTED
      actions:
        - { type: ui,  name: retract_card, args: {} }
        - { type: tts, name: speak, args: { text: "Thẻ đã bị thu hồi do quá thời gian nhận." } }
    _timeout_CARD_PICKUP:
      to: RETRACTED
      actions:
        - { type: ui,  name: retract_card, args: {} }
        - { type: tts, name: speak, args: { text: "Thẻ đã bị thu hồi do quá thời gian nhận." } }
    others:
      guard: "ctx.pickup_others < 3"
      to: CARD_PICKUP
      after: "ctx.pickup_others += 1"
      actions:
        - { type: tts, name: speak, args: { text: "Anh/chị nhận thẻ tại khe nhận giúp em ạ." } }
      fallback:
        to: RETRACTED
        actions:
          - { type: ui,  name: retract_card, args: {} }
          - { type: tts, name: speak, args: { text: "Do chưa nhận thẻ, hệ thống đã thu hồi để đảm bảo an toàn." } }
    cancel:
      to: RETRACTED
      actions:
        - { type: ui,  name: retract_card, args: {} }

  DONE:
    print_receipt_yes:
      to: DONE
      actions:
        - { type: ui,  name: print_receipt, args: {} }
        - { type: tts, name: speak, args: { text: "Em in biên lai, cảm ơn anh/chị đã sử dụng dịch vụ." } }
        - { type: ui,  name: back_home, args: {} }
    print_receipt_no:
      to: DONE
      actions:
        - { type: tts, name: speak, args: { text: "Cảm ơn anh/chị. Hẹn gặp lại!" } }
        - { type: ui,  name: back_home, args: {} }
    _auto:
      to: DONE
      actions:
        - { type: ui,  name: back_home, args: {} }

  RETRACTED:
    acknowledge:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }
    _auto:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

  FAILED:
    retry_all:
      to: START
      after: "ctx.id_retry = 0; ctx.otp_fail = 0; ctx.branch_suggested = false; ctx.face_others = 0; ctx.id_others = 0; ctx.otp_others = 0; ctx.pickup_others = 0"
      actions:
        - { type: ui,  name: open_home, args: {} }
        - { type: tts, name: speak, args: { text: "Mình bắt đầu lại từ đầu ạ." } }
    _auto:
      to: FAILED
      actions:
        - { type: ui,  name: back_home, args: {} }

```

