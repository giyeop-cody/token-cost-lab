"""Offline regression suite. Mocks are not new model observations."""
import sys
from pathlib import Path
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent_setup"))


@pytest.fixture(autouse=True)
def no_paid_requests(monkeypatch):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    def reject(*args, **kwargs):
        raise AssertionError("Unexpected HTTP call: offline tests must mock API requests")
    monkeypatch.setattr(urllib.request, "urlopen", reject)


@pytest.fixture(scope="session")
def evidence():
    from lab.evidence import build
    return build()
