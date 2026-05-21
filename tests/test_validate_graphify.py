"""
Tests for scripts/validate_graphify_output.py

Covers: validate() — success gate logic for node IDs, confidence enum, edge count.
Pure logic; no file I/O in the validator itself.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_graphify_output import validate


def _node(id="src_main_py", label="main.py", file_type="code"):
    return {"id": id, "label": label, "file_type": file_type}


def _edge(source="src_main_py", target="src_utils_py", confidence="EXTRACTED", relation="calls"):
    return {"source": source, "target": target, "confidence": confidence, "relation": relation}


def _valid_record():
    return {
        "nodes": [_node("src_main_py"), _node("src_utils_py", "utils.py")],
        "edges": [_edge()],
    }


# ── Passing cases ─────────────────────────────────────────────────────────────

class TestValidatePassing:
    def test_valid_record_passes(self):
        passed, errors, warnings = validate(_valid_record())
        assert passed is True
        assert errors == []

    def test_all_confidence_values_accepted(self):
        for conf in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
            data = {
                "nodes": [_node("a"), _node("b")],
                "edges": [_edge("a", "b", confidence=conf)],
            }
            passed, errors, _ = validate(data)
            assert passed is True, f"Expected PASS for confidence={conf}"

    def test_multiple_edges_passes(self):
        data = {
            "nodes": [_node("a"), _node("b"), _node("c")],
            "edges": [_edge("a", "b"), _edge("b", "c")],
        }
        passed, errors, _ = validate(data)
        assert passed is True


# ── Node ID failures ──────────────────────────────────────────────────────────

class TestNodeIdValidation:
    def test_hyphen_in_id_fails(self):
        data = {"nodes": [_node("src-main")], "edges": [_edge("src-main", "src-main")]}
        passed, errors, _ = validate(data)
        assert passed is False
        assert any("FAILS regex" in e for e in errors)

    def test_uppercase_in_id_fails(self):
        data = {"nodes": [_node("SrcMain")], "edges": [_edge("SrcMain", "SrcMain")]}
        passed, errors, _ = validate(data)
        assert passed is False

    def test_dot_in_id_fails(self):
        data = {"nodes": [_node("src.main")], "edges": [_edge("src.main", "src.main")]}
        passed, errors, _ = validate(data)
        assert passed is False

    def test_valid_snake_case_passes(self):
        data = {"nodes": [_node("src_main_py"), _node("src_utils_py")],
                "edges": [_edge()]}
        passed, errors, _ = validate(data)
        assert passed is True

    def test_missing_id_field_fails(self):
        data = {"nodes": [{"label": "main.py"}], "edges": [_edge()]}
        passed, errors, _ = validate(data)
        assert passed is False
        assert any("missing 'id'" in e for e in errors)

    def test_duplicate_node_id_warns(self):
        data = {
            "nodes": [_node("src_main_py"), _node("src_main_py")],
            "edges": [_edge()],
        }
        _, _, warnings = validate(data)
        assert any("duplicate" in w for w in warnings)


# ── Edge failures ─────────────────────────────────────────────────────────────

class TestEdgeValidation:
    def test_zero_edges_fails(self):
        data = {"nodes": [_node("a"), _node("b")], "edges": []}
        passed, errors, _ = validate(data)
        assert passed is False
        assert any("edge count = 0" in e for e in errors)

    def test_missing_confidence_fails(self):
        data = {
            "nodes": [_node("a"), _node("b")],
            "edges": [{"source": "a", "target": "b", "relation": "calls"}],
        }
        passed, errors, _ = validate(data)
        assert passed is False
        assert any("missing 'confidence'" in e for e in errors)

    def test_invalid_confidence_fails(self):
        data = {
            "nodes": [_node("a"), _node("b")],
            "edges": [_edge("a", "b", confidence="MAYBE")],
        }
        passed, errors, _ = validate(data)
        assert passed is False
        assert any("MAYBE" in e for e in errors)

    def test_source_not_in_nodes_warns(self):
        data = {
            "nodes": [_node("b")],
            "edges": [_edge("ghost_node", "b")],
        }
        _, _, warnings = validate(data)
        assert any("ghost_node" in w for w in warnings)

    def test_target_not_in_nodes_warns(self):
        data = {
            "nodes": [_node("a")],
            "edges": [_edge("a", "ghost_target")],
        }
        _, _, warnings = validate(data)
        assert any("ghost_target" in w for w in warnings)


# ── Warning cases (pass but flag) ─────────────────────────────────────────────

class TestValidateWarnings:
    def test_empty_label_warns(self):
        data = {
            "nodes": [{"id": "src_main_py", "label": ""}],
            "edges": [_edge()],
        }
        _, _, warnings = validate(data)
        assert any("empty 'label'" in w for w in warnings)

    def test_unexpected_file_type_warns(self):
        data = {
            "nodes": [{"id": "src_main_py", "label": "main.py", "file_type": "spreadsheet"}],
            "edges": [_edge()],
        }
        _, _, warnings = validate(data)
        assert any("spreadsheet" in w for w in warnings)

    def test_unknown_relation_warns(self):
        data = {
            "nodes": [_node("a"), _node("b")],
            "edges": [_edge("a", "b", relation="vibes_with")],
        }
        _, _, warnings = validate(data)
        assert any("vibes_with" in w for w in warnings)
