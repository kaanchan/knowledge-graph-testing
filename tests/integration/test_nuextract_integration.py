"""
Integration tests for nuextract_pipeline.py

These make real Ollama calls. Run with: pytest -m integration
"""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from .conftest import requires_ollama, requires_nuextract3


@requires_ollama
@requires_nuextract3
@pytest.mark.integration
class TestNuextractIntegration:
    def test_single_doc_produces_entities(self, tmp_path):
        """A real markdown document should yield at least one entity."""
        doc = tmp_path / "sample.md"
        doc.write_text(
            "# Overview\n\nThe DataLoader class reads CSV files. "
            "It uses pandas and connects to the FileReader module.",
            encoding="utf-8",
        )
        # Import here so missing deps don't break the unit test collection
        from nuextract_pipeline import extract_document, MODEL_NAME
        result = extract_document(str(doc))
        assert "entities" in result
        assert len(result["entities"]) >= 1, (
            f"Expected at least 1 entity, got: {result['entities']}"
        )

    def test_single_doc_produces_relations(self, tmp_path):
        """A prose document with clear relationships should yield at least one relation."""
        doc = tmp_path / "relations.md"
        doc.write_text(
            "# Architecture\n\nThe Router module delegates requests to the Handler. "
            "The Handler depends on the Database connection.",
            encoding="utf-8",
        )
        from nuextract_pipeline import extract_document
        result = extract_document(str(doc))
        assert "relations" in result
        assert len(result["relations"]) >= 1, (
            f"Expected at least 1 relation, got: {result['relations']}"
        )

    def test_result_has_required_fields(self, tmp_path):
        doc = tmp_path / "fields.md"
        doc.write_text("# Test\n\nSystem A uses Component B.", encoding="utf-8")
        from nuextract_pipeline import extract_document
        result = extract_document(str(doc))
        for field in ("source_file", "token_count", "chunks_processed", "entities", "relations"):
            assert field in result, f"Missing field: {field}"


@requires_ollama
@requires_nuextract3
@pytest.mark.integration
class TestDispatchNuextractIntegration:
    def test_dispatch_prose_file_uses_nuextract3(self, tmp_path):
        """dispatch_pipeline extract_file should route prose to nuextract3 and return a record."""
        doc = tmp_path / "overview.md"
        doc.write_text(
            "The ConfigManager reads settings from YAML files and exposes them to the Router.",
            encoding="utf-8",
        )
        from dispatch_pipeline import extract_file
        record = extract_file(
            file_path=doc,
            primary="nuextract3",
            fallback=None,
            model_prose="nuextract3",
            model_code="ollama_chat/phi4",
            api_base="http://localhost:11434",
            no_fallback=True,
        )
        assert record["model_used"] == "nuextract3"
        assert "entities" in record
        assert "relations" in record
