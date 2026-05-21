"""
Integration test configuration.

These tests call real Ollama endpoints and require:
  - Ollama running: ollama serve
  - nuextract3 model pulled
  - phi4 model pulled

Run with: pytest -m integration
Skip with: pytest (default — no -m flag)
"""

import urllib.request
import pytest


def _ollama_available():
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def _model_available(name):
    try:
        import json
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        available = [m["name"].split(":")[0] for m in data.get("models", [])]
        return any(a == name or a.startswith(name) for a in available)
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running — start with: ollama serve",
)

requires_nuextract3 = pytest.mark.skipif(
    not _model_available("nuextract3"),
    reason="nuextract3 not in Ollama — see README Prerequisites",
)

requires_phi4 = pytest.mark.skipif(
    not _model_available("phi4"),
    reason="phi4 not in Ollama — run: ollama pull phi4",
)
