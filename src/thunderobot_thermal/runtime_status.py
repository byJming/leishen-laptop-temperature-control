from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state"
RUNTIME_STATUS_PATH = STATE_DIR / "runtime_status.json"


@dataclass(frozen=True)
class RuntimeStatus:
    mode: str
    profile: str
    manual_full: bool
    on_ac_power: bool
    updated_at: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeStatus":
        return cls(
            mode=str(data["mode"]),
            profile=str(data["profile"]),
            manual_full=bool(data["manual_full"]),
            on_ac_power=bool(data["on_ac_power"]),
            updated_at=float(data["updated_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "profile": self.profile,
            "manual_full": self.manual_full,
            "on_ac_power": self.on_ac_power,
            "updated_at": self.updated_at,
        }


def write_runtime_status(mode: str, profile: str, manual_full: bool, on_ac_power: bool) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    status = RuntimeStatus(
        mode=mode,
        profile=profile,
        manual_full=manual_full,
        on_ac_power=on_ac_power,
        updated_at=time.time(),
    )
    temporary_path = RUNTIME_STATUS_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(status.to_dict(), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_path.replace(RUNTIME_STATUS_PATH)


def read_runtime_status(max_age_seconds: float = 10.0) -> RuntimeStatus | None:
    try:
        status = RuntimeStatus.from_dict(json.loads(RUNTIME_STATUS_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if time.time() - status.updated_at > max_age_seconds:
        return None
    return status
