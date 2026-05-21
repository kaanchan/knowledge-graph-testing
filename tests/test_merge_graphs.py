"""
Tests for scripts/merge_graphs.py

Covers: slugify, dominant_slug, load_graphify, load_nuextract, merge, write_json.
Uses fixtures from conftest.py for on-disk JSON files.
"""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from merge_graphs import (
    slugify,
    dominant_slug,
    load_graphify,
    load_nuextract,
    merge,
    write_json,
)


# ── slugify ───────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_simple_name(self):
        assert slugify("main.py") == "main_py"

    def test_spaces_become_underscores(self):
        assert slugify("My Class Name") == "my_class_name"

    def test_special_chars_removed(self):
        # trailing underscore from "()" is stripped by s.strip("_")
        assert slugify("get_free_vram_mb()") == "get_free_vram_mb"

    def test_already_snake_case_unchanged(self):
        assert slugify("src_main_py") == "src_main_py"

    def test_empty_string_returns_unknown(self):
        assert slugify("") == "unknown"

    def test_only_special_chars_returns_unknown(self):
        assert slugify("!!!") == "unknown"

    def test_leading_trailing_underscores_stripped(self):
        result = slugify("  hello  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_uppercase_lowercased(self):
        assert slugify("DataLoader") == "dataloader"


# ── dominant_slug ─────────────────────────────────────────────────────────────

class TestDominantSlug:
    def test_exact_match(self):
        ids = {"src_main_py", "src_utils_py"}
        assert dominant_slug("src_main_py", ids) == "src_main_py"

    def test_suffix_match(self):
        ids = {"src_main_py", "diagnostics_d1_ollama_check"}
        # "check" should match via endswith("_check")
        assert dominant_slug("check", ids) == "diagnostics_d1_ollama_check"

    def test_substring_match(self):
        ids = {"src_router_py", "src_main_py"}
        # "main" is a substring of "src_main_py"
        assert dominant_slug("main", ids) == "src_main_py"

    def test_no_match_returns_none(self):
        ids = {"src_main_py", "src_utils_py"}
        assert dominant_slug("totally_absent", ids) is None

    def test_empty_ids_returns_none(self):
        assert dominant_slug("anything", set()) is None


# ── load_graphify ─────────────────────────────────────────────────────────────

class TestLoadGraphify:
    def test_returns_nodes_and_links(self, sample_graphify_json):
        nodes, links = load_graphify(str(sample_graphify_json))
        assert len(nodes) == 3
        assert len(links) == 2

    def test_node_has_id(self, sample_graphify_json):
        nodes, _ = load_graphify(str(sample_graphify_json))
        assert all("id" in n for n in nodes)

    def test_link_has_source_target(self, sample_graphify_json):
        _, links = load_graphify(str(sample_graphify_json))
        assert all("source" in lnk and "target" in lnk for lnk in links)


# ── load_nuextract ────────────────────────────────────────────────────────────

class TestLoadNuextract:
    def test_returns_entities_and_relations(self, sample_nuextract_json):
        entities, relations = load_nuextract(str(sample_nuextract_json))
        assert len(entities) == 3   # 2 from doc1, 1 from doc2
        assert len(relations) == 1

    def test_entities_have_name(self, sample_nuextract_json):
        entities, _ = load_nuextract(str(sample_nuextract_json))
        assert all("name" in e for e in entities)

    def test_entities_have_source_doc(self, sample_nuextract_json):
        entities, _ = load_nuextract(str(sample_nuextract_json))
        assert all("_source_doc" in e for e in entities)

    def test_relations_have_source_doc(self, sample_nuextract_json):
        _, relations = load_nuextract(str(sample_nuextract_json))
        assert all("_source_doc" in r for r in relations)

    def test_empty_name_entity_skipped(self, tmp_path):
        data = [{"source_file": "x.md", "entities": [{"name": ""}], "relations": []}]
        p = tmp_path / "nu.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        entities, _ = load_nuextract(str(p))
        assert entities == []


# ── merge ─────────────────────────────────────────────────────────────────────

class TestMerge:
    def _graphify_data(self):
        nodes = [
            {"id": "src_main_py", "label": "main.py", "file_type": "code",
             "community": 1, "source_file": "src/main.py", "source_location": "L1"},
            {"id": "src_utils_py", "label": "utils.py", "file_type": "code",
             "community": 1, "source_file": "src/utils.py", "source_location": "L1"},
        ]
        links = [
            {"source": "src_main_py", "target": "src_utils_py",
             "relation": "imports", "weight": 1.0, "source_file": "src/main.py"},
        ]
        return nodes, links

    def test_graphify_nodes_preserved(self):
        g_nodes, g_links = self._graphify_data()
        nodes, edges = merge(g_nodes, g_links, [], [])
        node_ids = {n["id"] for n in nodes}
        assert "src_main_py" in node_ids
        assert "src_utils_py" in node_ids

    def test_graphify_edges_in_code_layer(self):
        g_nodes, g_links = self._graphify_data()
        _, edges = merge(g_nodes, g_links, [], [])
        assert all(e["layer"] == "code" for e in edges)

    def test_nuextract_entities_added_as_nodes(self):
        g_nodes, g_links = self._graphify_data()
        nu_entities = [
            {"name": "DataLoader", "type": "Class", "_source_doc": "overview.md"},
        ]
        nodes, _ = merge(g_nodes, g_links, nu_entities, [])
        node_ids = {n["id"] for n in nodes}
        assert "dataloader" in node_ids

    def test_fusion_when_entity_matches_graphify_node(self):
        g_nodes, g_links = self._graphify_data()
        # "main.py" slugifies to "main_py", which is a substring of "src_main_py"
        nu_entities = [
            {"name": "main.py", "type": "File", "_source_doc": "docs.md"},
        ]
        nodes, _ = merge(g_nodes, g_links, nu_entities, [])
        merged_nodes = [n for n in nodes if n["source"] == "merged"]
        assert len(merged_nodes) >= 1

    def test_no_fusion_when_entity_has_no_match(self):
        g_nodes, g_links = self._graphify_data()
        nu_entities = [
            {"name": "CompletlyUnrelated", "type": "Concept", "_source_doc": "docs.md"},
        ]
        nodes, _ = merge(g_nodes, g_links, nu_entities, [])
        # Should be added as a nuextract3 node, not fused
        nu_nodes = [n for n in nodes if n["source"] == "nuextract3"]
        assert any("completlyunrelated" in n["id"] for n in nu_nodes)

    def test_nuextract_relations_in_semantic_layer(self):
        g_nodes, g_links = self._graphify_data()
        nu_entities = [
            {"name": "Alpha", "type": "Concept", "_source_doc": "docs.md"},
            {"name": "Beta",  "type": "Concept", "_source_doc": "docs.md"},
        ]
        nu_relations = [
            {"subject": "Alpha", "predicate": "depends on", "object": "Beta",
             "_source_doc": "docs.md"},
        ]
        _, edges = merge(g_nodes, g_links, nu_entities, nu_relations)
        semantic = [e for e in edges if e["layer"] == "semantic"]
        assert len(semantic) == 1
        assert semantic[0]["relation"] == "depends on"

    def test_empty_inputs_returns_empty(self):
        nodes, edges = merge([], [], [], [])
        assert nodes == []
        assert edges == []

    def test_relation_object_not_in_entity_list_creates_node(self):
        g_nodes, g_links = self._graphify_data()
        nu_entities = [
            {"name": "Alpha", "type": "Concept", "_source_doc": "docs.md"},
        ]
        nu_relations = [
            # "Gamma" not in entity list — merge should create it on the fly
            {"subject": "Alpha", "predicate": "uses", "object": "Gamma",
             "_source_doc": "docs.md"},
        ]
        nodes, _ = merge(g_nodes, g_links, nu_entities, nu_relations)
        node_ids = {n["id"] for n in nodes}
        assert "gamma" in node_ids


# ── write_json ────────────────────────────────────────────────────────────────

class TestWriteJson:
    def test_output_file_created(self, tmp_path):
        nodes = [{"id": "a", "label": "A", "source": "graphify"}]
        edges = [{"source": "a", "target": "a", "layer": "code"}]
        p = write_json(nodes, edges, tmp_path)
        assert p.exists()

    def test_output_is_valid_json(self, tmp_path):
        nodes = [{"id": "a", "label": "A", "source": "graphify"}]
        edges = []
        p = write_json(nodes, edges, tmp_path)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "nodes" in data
        assert "edges" in data
        assert "meta" in data

    def test_meta_counts_are_correct(self, tmp_path):
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"source": "a", "target": "b"}]
        p = write_json(nodes, edges, tmp_path)
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["meta"]["node_count"] == 2
        assert data["meta"]["edge_count"] == 1
