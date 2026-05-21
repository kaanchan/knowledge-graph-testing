"""
Shared fixtures for the knowledge-graph-testing test suite.
"""

import json
import pytest
from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path):
    """A temporary directory, cleaned up after each test."""
    return tmp_path


@pytest.fixture
def sample_graphify_json(tmp_path):
    """Minimal valid graphify graph.json on disk."""
    data = {
        "nodes": [
            {"id": "src_main_py", "label": "main.py", "file_type": "code",
             "community": 1, "source_file": "src/main.py", "source_location": "L1"},
            {"id": "src_utils_py", "label": "utils.py", "file_type": "code",
             "community": 1, "source_file": "src/utils.py", "source_location": "L1"},
            {"id": "src_main_run", "label": "run()", "file_type": "code",
             "community": 1, "source_file": "src/main.py", "source_location": "L10"},
        ],
        "links": [
            {"source": "src_main_py", "target": "src_utils_py",
             "relation": "imports", "weight": 1.0,
             "confidence": "EXTRACTED", "source_file": "src/main.py"},
            {"source": "src_main_run", "target": "src_utils_py",
             "relation": "calls", "weight": 1.0,
             "confidence": "EXTRACTED", "source_file": "src/main.py"},
        ],
    }
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def sample_nuextract_json(tmp_path):
    """Minimal valid nuextract-output.json on disk."""
    data = [
        {
            "source_file": "docs/overview.md",
            "token_count": 500,
            "chunks_processed": 1,
            "entities": [
                {"name": "main.py", "type": "File"},
                {"name": "DataLoader", "type": "Class"},
            ],
            "relations": [
                {"subject": "main.py", "predicate": "imports", "object": "DataLoader"},
            ],
        },
        {
            "source_file": "docs/api.md",
            "token_count": 300,
            "chunks_processed": 1,
            "entities": [
                {"name": "ConfigParser", "type": "Class"},
            ],
            "relations": [],
        },
    ]
    p = tmp_path / "nuextract-output.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p
