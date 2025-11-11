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
