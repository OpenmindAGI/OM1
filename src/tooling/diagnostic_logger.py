import os
import json
import sqlite3

from input.orchestrator import InputEvent
from llm.output_model import Command


class DiagnosticLogger:
    _instance: "DiagnosticLogger"
    _db: sqlite3.Connection

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super(DiagnosticLogger, cls).__new__(cls)
            os.makedirs(os.path.expanduser("~/.omos"), exist_ok=True)
            cls._db = sqlite3.connect(os.path.expanduser("~/.omos/diagnostic.db"))
            # Create tables if they don't exist
            cls._db.execute("""
                CREATE TABLE IF NOT EXISTS input_events (
                    tick_id TEXT,
                    event TEXT
                )
            """)
            cls._db.execute("""
                CREATE TABLE IF NOT EXISTS fuser_prompt (
                    tick_id TEXT,
                    prompt TEXT
                )
            """)
            cls._db.execute("""
                CREATE TABLE IF NOT EXISTS llm_events (
                    tick_id TEXT,
                    event TEXT
                )
            """)
            cls._enabled = os.environ.get("DIAGNOSTIC") == "true"
            cls._instance.__init__()
        return cls._instance

    def write_input_events(self, tick_id: str, events: list[InputEvent]) -> None:
        if not self._enabled:
            return
        events_json = json.dumps(
            [
                {
                    "input_type": event.input.__class__.__name__,
                    "text_prompt": event.text_prompt,
                }
                for event in events
            ]
        )
        self._db.execute(
            "INSERT INTO input_events (tick_id, event) VALUES (?, ?)",
            (tick_id, events_json),
        )
        self._db.commit()

    def write_fuser_prompt(self, tick_id: str, prompt: str) -> None:
        if not self._enabled:
            return
        self._db.execute(
            "INSERT INTO fuser_prompt (tick_id, prompt) VALUES (?, ?)",
            (tick_id, prompt),
        )
        self._db.commit()

    def write_llm_events(self, tick_id: str, events: list[Command]) -> None:
        if not self._enabled:
            return
        events_json = json.dumps([event.dict() for event in events])
        self._db.execute(
            "INSERT INTO llm_events (tick_id, event) VALUES (?, ?)",
            (tick_id, events_json),
        )
        self._db.commit()
