"""
Tests for scripts/dispatch_pipeline.py — pure logic only.

Covers: classify(), _is_empty(), scan_files() with temp directories.
No Ollama calls; all model-dependent paths are in tests/integration/.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from dispatch_pipeline import classify, _is_empty, scan_files


# ── classify ──────────────────────────────────────────────────────────────────

class TestClassify:
    # Prose
    def test_md_is_prose(self):        assert classify(Path("readme.md")) == "prose"
    def test_txt_is_prose(self):       assert classify(Path("notes.txt")) == "prose"
    def test_rst_is_prose(self):       assert classify(Path("docs.rst")) == "prose"
    def test_adoc_is_prose(self):      assert classify(Path("guide.adoc")) == "prose"

    # Code
    def test_py_is_code(self):         assert classify(Path("app.py")) == "code"
    def test_js_is_code(self):         assert classify(Path("index.js")) == "code"
    def test_ts_is_code(self):         assert classify(Path("types.ts")) == "code"
    def test_go_is_code(self):         assert classify(Path("main.go")) == "code"
    def test_rs_is_code(self):         assert classify(Path("lib.rs")) == "code"
    def test_sh_is_code(self):         assert classify(Path("deploy.sh")) == "code"
    def test_ps1_is_code(self):        assert classify(Path("start.ps1")) == "code"
    def test_sql_is_code(self):        assert classify(Path("schema.sql")) == "code"
    def test_java_is_code(self):       assert classify(Path("Main.java")) == "code"

    # Config
    def test_yaml_is_config(self):     assert classify(Path("config.yaml")) == "config"
    def test_yml_is_config(self):      assert classify(Path("ci.yml")) == "config"
    def test_toml_is_config(self):     assert classify(Path("pyproject.toml")) == "config"
    def test_json_is_config(self):     assert classify(Path("package.json")) == "config"
    def test_ini_is_config(self):      assert classify(Path("setup.ini")) == "config"
    def test_env_is_config(self):      assert classify(Path("prod.env")) == "config"

    # Skip
    def test_png_is_skip(self):        assert classify(Path("logo.png")) == "skip"
    def test_pdf_is_skip(self):        assert classify(Path("report.pdf")) == "skip"
    def test_pyc_is_skip(self):        assert classify(Path("app.pyc")) == "skip"
    def test_lock_is_skip(self):       assert classify(Path("uv.lock")) == "skip"
    def test_gguf_is_skip(self):       assert classify(Path("model.gguf")) == "skip"
    def test_exe_is_skip(self):        assert classify(Path("app.exe")) == "skip"

    # Dotfiles (no extension, name starts with dot) -> config
    def test_gitignore_is_config(self):
        assert classify(Path(".gitignore")) == "config"

    def test_editorconfig_is_config(self):
        assert classify(Path(".editorconfig")) == "config"

    # Unknown extension -> unknown
    def test_unknown_extension_is_unknown(self):
        assert classify(Path("data.xyz123")) == "unknown"

    # Case insensitivity
    def test_uppercase_extension_handled(self):
        # Extensions are lowercased before lookup
        assert classify(Path("README.MD")) == "prose"

    def test_mixed_case_py(self):
        assert classify(Path("App.PY")) == "code"


# ── _is_empty ─────────────────────────────────────────────────────────────────

class TestIsEmpty:
    def test_empty_dict_is_empty(self):
        assert _is_empty({}) is True

    def test_empty_lists_is_empty(self):
        assert _is_empty({"entities": [], "relations": [], "edges": []}) is True

    def test_has_entities_not_empty(self):
        assert _is_empty({"entities": [{"name": "X"}], "relations": []}) is False

    def test_has_relations_not_empty(self):
        assert _is_empty({"entities": [], "relations": [{"s": "a", "p": "b", "o": "c"}]}) is False

    def test_has_edges_not_empty(self):
        assert _is_empty({"entities": [], "relations": [], "edges": [{"a": "b"}]}) is False

    def test_none_values_treated_as_empty(self):
        # get() returns None for missing keys, which is falsy
        assert _is_empty({"entities": None, "relations": None}) is True


# ── scan_files ────────────────────────────────────────────────────────────────

class TestScanFiles:
    def _make_tree(self, root):
        """Create a small synthetic repo tree."""
        (root / "src").mkdir()
        (root / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
        (root / "src" / "utils.py").write_text("def f(): pass", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "overview.md").write_text("# Overview", encoding="utf-8")
        (root / "config.yaml").write_text("key: value", encoding="utf-8")
        # Should be excluded
        (root / "node_modules").mkdir()
        (root / "node_modules" / "pkg" / "index.js").mkdir(parents=True)
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"fake\x00pyc")

    def test_scan_finds_py_md_yaml(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=[])
        paths = [p for p, _ in results]
        names = {p.name for p in paths}
        assert "main.py" in names
        assert "utils.py" in names
        assert "overview.md" in names
        assert "config.yaml" in names

    def test_scan_excludes_node_modules(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=[])
        paths = [p for p, _ in results]
        assert not any("node_modules" in str(p) for p in paths)

    def test_scan_excludes_pycache(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=[])
        paths = [p for p, _ in results]
        assert not any("__pycache__" in str(p) for p in paths)

    def test_scan_skips_binary_pyc(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=[])
        paths = [p for p, _ in results]
        assert not any(p.suffix == ".pyc" for p in paths)

    def test_scan_categories_are_correct(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=[])
        by_name = {p.name: cat for p, cat in results}
        assert by_name.get("main.py") == "code"
        assert by_name.get("overview.md") == "prose"
        assert by_name.get("config.yaml") == "config"

    def test_extra_excludes_respected(self, tmp_path):
        self._make_tree(tmp_path)
        results = scan_files(tmp_path, extra_excludes=["src"])
        paths = [p for p, _ in results]
        assert not any(p.parent.name == "src" for p in paths)

    def test_no_defaults_includes_venv(self, tmp_path):
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "site.py").write_text("x=1", encoding="utf-8")
        results_default = scan_files(tmp_path, extra_excludes=[], no_defaults=False)
        results_no_def  = scan_files(tmp_path, extra_excludes=[], no_defaults=True)
        default_names = {p.name for p, _ in results_default}
        nodef_names   = {p.name for p, _ in results_no_def}
        assert "site.py" not in default_names
        assert "site.py" in nodef_names
