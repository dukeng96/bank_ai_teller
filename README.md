# teller_ai — TPBank LiveBank Voice Reissue (LangGraph FSM)

Production-grade, config-driven orchestrator + agent for **voice-controlled card reissue** on LiveBank kiosks.

## Quick start (PyCharm / CLI)

1. Clone repo and install dependencies (`pip install -r requirements.txt`).
2. Optional: adjust [`config.yml`](config.yml) for your LLM endpoint, tracing, or demo behaviours.
3. Run the orchestrator demo:
   ```bash
   python main.py            # defaults to the "happy" scenario
   python main.py stockout   # or pick another canned scenario
   ```

The entry point requires no environment variables—`config.yml` provides all defaults. Toggle `trace.enabled` to view
full prompts, raw LLM output, FSM decisions, transitions, actions, emitted signals, and timer events.

## Project layout

```
config.yml                  # single source of truth for runtime configuration
main.py                     # demo entry point
config.py                   # cached YAML loader with cfg_path helper
actions/                    # device/API/UI/TTS demo actions
fsm/                        # rules + prompts (conversation-only prompts kept)
llm_client/                 # HTTP LLM decider
orchestrator/               # LangGraph FSM nodes, timeouts, state typing
samples/                    # scenario driver for demos/tests
```

## Testing

The default test suite exercises rules, guards, and the happy-path demo shape:

```bash
pytest
```

Remember to stub or mock the LLM endpoint when running tests in CI if the real service is unavailable.
