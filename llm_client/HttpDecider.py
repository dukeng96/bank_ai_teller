from __future__ import annotations
import os, json, re, time
from typing import Any, Dict, List
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from jsonschema import validate, ValidationError

# Strict schema for Decision JSON
DECISION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["intent", "params", "response"],
    "properties": {
        "intent": {"type": "string"},
        "params": {"type": "object"},
        "response": {
            "type": "object",
            "required": ["type", "content"],
            "properties": {
                "type": {"type": "string", "enum": ["text", "none"]},
                "content": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "meta": {"type": "object"},
    },
    "additionalProperties": True,
}

class LLMDecider:
    """Generic LLM decider.
    Expects endpoint accepting: POST { "query": "<prompt>" } -> { "status": "success", "response": "<text>" }
    The model is instructed to return a single JSON object conforming to DECISION_SCHEMA.
    """

    def __init__(self) -> None:
        self.url = os.getenv("LLM_URL", "http://10.165.24.200:30424/query").strip()
        if not self.url:
            raise RuntimeError("LLM_URL is not set")
        self.timeout = float(os.getenv("LLM_TIMEOUT", "12"))
        self.strict = os.getenv("TAI_JSON_STRICT", "1") == "1"

    def _build_prompt(self, state: str, allowed_intents: List[str], user_input: Dict[str, Any], prompt_cfg: Dict[str, Any]) -> str:
        system = (prompt_cfg.get("system") or "").strip()
        guard = (
            "YÊU CẦU BẮT BUỘC:\n"
            "- Chỉ trả về MỘT JSON hợp lệ theo schema Decision, không kèm giải thích ngoài JSON.\n"
            "- intent PHẢI thuộc whitelist: " + json.dumps(allowed_intents, ensure_ascii=False) + "\n"
            "- Nếu phát ngôn không khớp nghiệp vụ của state, chọn intent 'others' (nếu có trong whitelist) để giữ nguyên state và gợi ý ngắn.\n"
        )
        payload = {"state": state, "allowed_intents": allowed_intents, "input": user_input}
        prompt = f"{system}\n\n{guard}\nDỮ LIỆU NGỮ CẢNH:\n{json.dumps(payload, ensure_ascii=False)}\n\nCHỈ TRẢ JSON DUY NHẤT."
        return prompt

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=2))
    def _call_api(self, prompt: str) -> Dict[str, Any]:
        r = requests.post(self.url, json={"query": prompt}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"(\{[\s\S]{0,5000}\})", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        raise ValueError("Model response is not valid JSON")

    def decide(self, state: str, allowed_intents: List[str], user_input: Dict[str, Any], prompt_cfg: Dict[str, Any]) -> Dict[str, Any]:
        now = int(time.time())
        prompt = self._build_prompt(state, allowed_intents, user_input, prompt_cfg)
        try:
            raw = self._call_api(prompt)
        except Exception as e:
            return {
                "intent": "cancel",
                "params": {},
                "response": {"type": "text", "content": "Xin lỗi, dịch vụ tạm thời gián đoạn."},
                "meta": {"trace_id": f"http-ex-{now}", "error": str(e)},
            }
        text = str(raw.get("response") or "").strip()
        try:
            data = self._extract_json(text)
        except Exception as e:
            return {
                "intent": "cancel",
                "params": {},
                "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                "meta": {"trace_id": f"http-json-{now}", "error": str(e)},
            }
        if self.strict:
            try:
                validate(instance=data, schema=DECISION_SCHEMA)
            except ValidationError as ve:
                data = {
                    "intent": "cancel",
                    "params": {},
                    "response": {"type": "text", "content": "Xin lỗi, đầu ra không hợp lệ."},
                    "meta": {"trace_id": f"http-schema-{now}", "error": str(ve)},
                }
        if data.get("intent") not in allowed_intents:
            data["intent"] = "cancel"
            meta = data.get("meta", {})
            meta["note"] = "intent not allowed → cancel"
            data["meta"] = meta
        meta = data.get("meta", {})
        meta.setdefault("trace_id", f"run-{now}")
        data["meta"] = meta
        return data
