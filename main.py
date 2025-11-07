from __future__ import annotations

import sys

from samples.demo_run import run_scenario

if __name__ == "__main__":
    scenario = (sys.argv[1] if len(sys.argv) > 1 else "happy").lower()
    run_scenario(scenario)
