from __future__ import annotations

import json
import re
from typing import Any, Dict, List

import requests

from teller_ai.config import cfg_path


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

    def _extract_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise DecisionError("No JSON found in LLM response")
        return json.loads(match.group(0))

    def decide(
        self,
        state: str,
        allowed_intents: List[str],
        user_input: Dict[str, Any],
        prompt_cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        system = (prompt_cfg.get("system") or "").strip()
        context = prompt_cfg.get("context") or {}
        payload = (user_input or {}).get("payload", "")

        prompt = json.dumps(
            {
                "system": system,
                "context": context,
                "state": state,
                "allowed_intents": allowed_intents,
                "user_utterance": payload,
            },
            ensure_ascii=False,
        )

        if self.trace:
            print("\n[TRACE LLM] POST prompt:", prompt)

        try:
            response = requests.post(self.url, json={"query": prompt}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
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
            if "intent" not in decision or "response" not in decision:
                decision = {
                    "intent": "cancel",
                    "params": {},
                    "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                    "meta": {"error": "missing keys"},
                }
            if "params" not in decision or not isinstance(decision.get("params"), dict):
                decision["params"] = {}
            if allowed_intents and decision.get("intent") not in allowed_intents:
                decision["intent"] = "cancel"

        if self.trace:
            print("[TRACE LLM] Decision:", decision)

        return decision
