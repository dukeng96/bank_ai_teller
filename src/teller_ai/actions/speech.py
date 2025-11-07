from __future__ import annotations
from rich import print as rprint

def speak(text: str) -> None:
    rprint(f"[bold magenta][TTS][/bold magenta] {text}")
