"""
Tests for scripts/extract_config.py

Covers: is_binary, DEFAULT_EXCLUDE_DIRS, IgnoreSpec.match, build_ignore_spec.
All tests are pure I/O against temp directories — no model calls.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from extract_config import (
    is_binary,
    DEFAULT_EXCLUDE_DIRS,
    IgnoreSpec,
    build_ignore_spec,
    clean_output,
)


# ── is_binary ─────────────────────────────────────────────────────────────────

class TestIsBinary:
    def test_plain_text_is_not_binary(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_bytes(b"print('hello world')\n")
        assert is_binary(f) is False

    def test_null_byte_is_binary(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"some text\x00more text")
        assert is_binary(f) is True

    def test_empty_file_is_not_binary(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert is_binary(f) is False

    def test_nonexistent_file_returns_true(self, tmp_path):
        # unreadable path -> skip safely
        assert is_binary(tmp_path / "ghost.txt") is True

    def test_utf8_with_high_bytes_is_not_binary(self, tmp_path):
        f = tmp_path / "unicode.md"
        f.write_bytes("Ünïcödé tëxt wïth ëmöjï 🎉".encode("utf-8"))
        assert is_binary(f) is False

    def test_only_checks_first_sample_size(self, tmp_path):
        # null byte beyond the first 8192 bytes should not trigger detection
        f = tmp_path / "large.txt"
        f.write_bytes(b"a" * 8192 + b"\x00")
        assert is_binary(f) is False


# ── DEFAULT_EXCLUDE_DIRS ──────────────────────────────────────────────────────

class TestDefaultExcludeDirs:
    def test_is_frozenset(self):
        assert isinstance(DEFAULT_EXCLUDE_DIRS, frozenset)

    def test_contains_venv(self):
        assert ".venv" in DEFAULT_EXCLUDE_DIRS

    def test_contains_node_modules(self):
        assert "node_modules" in DEFAULT_EXCLUDE_DIRS

    def test_contains_git(self):
        assert ".git" in DEFAULT_EXCLUDE_DIRS

    def test_contains_pycache(self):
        assert "__pycache__" in DEFAULT_EXCLUDE_DIRS

    def test_contains_responses(self):
        # extraction output dir excluded to prevent circular indexing
        assert "responses" in DEFAULT_EXCLUDE_DIRS

    def test_all_entries_lowercase(self):
        for entry in DEFAULT_EXCLUDE_DIRS:
            assert entry == entry.lower(), f"Entry not lowercase: {entry!r}"


# ── IgnoreSpec.match ──────────────────────────────────────────────────────────

class TestIgnoreSpecMatch:
    def _make_spec(self, root, exclude_dirs=None, pathspec_rules=None):
        return IgnoreSpec(
            root=root,
            exclude_dirs=set(exclude_dirs or []),
            pathspec_rules=pathspec_rules or [],
            ignore_files=[],
        )

    def test_excluded_dir_ancestor_matches(self, tmp_path):
        spec = self._make_spec(tmp_path, exclude_dirs={"node_modules"})
        deep = tmp_path / "node_modules" / "lodash" / "index.js"
        assert spec.match(deep) is True

    def test_non_excluded_file_does_not_match(self, tmp_path):
        spec = self._make_spec(tmp_path, exclude_dirs={"node_modules"})
        f = tmp_path / "src" / "main.py"
        assert spec.match(f) is False

    def test_file_named_like_excluded_dir_does_not_match(self, tmp_path):
        # "dist" as a filename, not a directory ancestor
        spec = self._make_spec(tmp_path, exclude_dirs={"dist"})
        f = tmp_path / "src" / "dist.py"
        assert spec.match(f) is False

    def test_dir_name_check_is_case_insensitive_lowered(self, tmp_path):
        # exclude_dirs entries are always lowercased; dir parts are lowercased before check
        spec = self._make_spec(tmp_path, exclude_dirs={"node_modules"})
        # If a real path had mixed case, the part comparison lowercases it
        # Simulate by building the spec's exclude_dirs with lower-only — matching logic
        # lowercases path parts before comparing
        f = tmp_path / "Node_Modules" / "pkg" / "index.js"
        assert spec.match(f) is True

    def test_empty_spec_matches_nothing(self, tmp_path):
        spec = self._make_spec(tmp_path)
        f = tmp_path / "src" / "app.py"
        assert spec.match(f) is False


# ── build_ignore_spec ─────────────────────────────────────────────────────────

class TestBuildIgnoreSpec:
    def test_returns_ignore_spec_instance(self, tmp_path):
        spec = build_ignore_spec(tmp_path)
        assert isinstance(spec, IgnoreSpec)

    def test_default_excludes_venv(self, tmp_path):
        spec = build_ignore_spec(tmp_path)
        f = tmp_path / ".venv" / "lib" / "site.py"
        assert spec.match(f) is True

    def test_no_defaults_disables_builtin_excludes(self, tmp_path):
        spec = build_ignore_spec(tmp_path, no_defaults=True)
        # Without defaults, .venv is no longer excluded
        f = tmp_path / ".venv" / "lib" / "site.py"
        assert spec.match(f) is False

    def test_extra_excludes_added(self, tmp_path):
        spec = build_ignore_spec(tmp_path, extra_excludes=["my_custom_dir"])
        f = tmp_path / "my_custom_dir" / "file.py"
        assert spec.match(f) is True

    def test_extractignore_dir_names_respected(self, tmp_path):
        # .extractignore with a bare dir name
        (tmp_path / ".extractignore").write_text("scratch\n", encoding="utf-8")
        spec = build_ignore_spec(tmp_path)
        f = tmp_path / "scratch" / "notes.md"
        assert spec.match(f) is True

    def test_gitignore_dir_names_respected(self, tmp_path):
        (tmp_path / ".gitignore").write_text("localdata\n", encoding="utf-8")
        spec = build_ignore_spec(tmp_path, respect_gitignore=True)
        f = tmp_path / "localdata" / "dump.sql"
        assert spec.match(f) is True

    def test_no_gitignore_flag_skips_gitignore(self, tmp_path):
        (tmp_path / ".gitignore").write_text("localdata\n", encoding="utf-8")
        spec = build_ignore_spec(tmp_path, respect_gitignore=False, no_defaults=True)
        f = tmp_path / "localdata" / "dump.sql"
        assert spec.match(f) is False

    def test_summary_returns_string(self, tmp_path):
        spec = build_ignore_spec(tmp_path)
        summary = spec.summary()
        assert isinstance(summary, str)
        assert "Excluded dir names" in summary

    def test_nonexistent_ignore_path_does_not_crash(self, tmp_path):
        # Should warn, not raise
        spec = build_ignore_spec(tmp_path, ignore_path=str(tmp_path / "nonexistent.ignore"))
        assert isinstance(spec, IgnoreSpec)


# ── clean_output ──────────────────────────────────────────────────────────────

class TestCleanOutput:
    def test_deletes_single_file_with_yes(self, tmp_path):
        p = tmp_path / "out.json"
        p.write_text("[]", encoding="utf-8")
        result = clean_output(p, yes=True)
        assert result is True
        assert not p.exists()

    def test_deletes_multiple_files_with_yes(self, tmp_path):
        files = [tmp_path / f"f{i}.json" for i in range(3)]
        for f in files:
            f.write_text("{}", encoding="utf-8")
        result = clean_output(files, yes=True)
        assert result is True
        assert all(not f.exists() for f in files)

    def test_nonexistent_path_returns_false(self, tmp_path):
        result = clean_output(tmp_path / "ghost.json", yes=True)
        assert result is False

    def test_mix_existing_nonexistent_deletes_existing(self, tmp_path):
        real = tmp_path / "real.json"
        real.write_text("{}", encoding="utf-8")
        ghost = tmp_path / "ghost.json"
        result = clean_output([real, ghost], yes=True)
        assert result is True
        assert not real.exists()

    def test_declined_prompt_returns_false(self, tmp_path, monkeypatch):
        p = tmp_path / "out.json"
        p.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "n")
        result = clean_output(p, yes=False)
        assert result is False
        assert p.exists()

    def test_confirmed_prompt_deletes_file(self, tmp_path, monkeypatch):
        p = tmp_path / "out.json"
        p.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("builtins.input", lambda _: "y")
        result = clean_output(p, yes=False)
        assert result is True
        assert not p.exists()

    def test_accepts_path_object_directly(self, tmp_path):
        p = tmp_path / "out.json"
        p.write_text("x", encoding="utf-8")
        result = clean_output(p, yes=True)
        assert result is True
