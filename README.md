# teller_ai — TPBank LiveBank Voice Reissue (LangGraph FSM)

Production-grade, config-driven orchestrator + agent for **voice-controlled card reissue** on LiveBank kiosks. **LLM (HTTP API)** only performs *intent inference*; the **LangGraph** FSM handles transitions, guards, counters, timeouts, rollback, and actions (UI/API/TTS).

> This version implements your latest requirements:
>
> * Uses your **internal HTTP LLM API** only (no OpenAI, no rule-based stub).
> * Adds a safe fallback intent **`others`** to keep state + TTS re-prompt with thresholds.
> * Renames node **`inference` → `think`** for clarity.
> * Removes all OpenAI code and any “Internal*” naming; generic `HttpLLMDecider` is used.
