"""
extract_config.py -- Shared ignore/scan configuration for the extraction pipeline.

All three extraction scripts import from here.  One place to change, all scripts
inherit the change automatically.

=============================================================================
HOW IGNORING WORKS
=============================================================================

Exclusions are resolved in a single pre-scan pass BEFORE the main file walk.
Two complementary mechanisms are combined:

  1. Directory-name set  (always active)
     Fast check: if any ancestor directory name (lowercased) is in the set,
     the entire subtree is skipped.  Applied via DEFAULT_EXCLUDE_DIRS plus
     --exclude CLI additions and --no-defaults opt-out.

  2. pathspec glob rules  (active when 'pathspec' is installed)
     Full gitignore semantics: globs, wildcards, negation (!pattern),
     anchored patterns, directory-specific scoping.
     Each .*ignore file's rules are scoped to the directory that contains it,
     exactly as git does.
     If pathspec is NOT installed, falls back to extracting bare dir-names only.

     Install pathspec (strongly recommended):
       pip install pathspec
     or with uv:
       uv add pathspec

Ignore file sources (all merged before the main scan):
  a. DEFAULT_EXCLUDE_DIRS hardcoded below  (disable with --no-defaults)
  b. Every .gitignore found anywhere under the scan root  (--no-gitignore to skip)
  c. Every .extractignore found anywhere under the scan root  (always active)
  d. A custom file pointed to by --ignore-path
  e. Bare dir names from --exclude on the CLI

=============================================================================
.extractignore FORMAT
=============================================================================

Place a .extractignore at the repo root or any subdirectory.  All are
discovered automatically.  The file in the subdirectory applies only to that
subtree (with pathspec) or globally as dir-names (without pathspec).

Format is identical to .gitignore:

  # This is a comment
  node_modules          <- skip this directory wherever it appears
  dist/                 <- trailing slash is stripped, same effect
  *.min.js              <- skip all minified JS files  (pathspec only)
  !important.min.js     <- but keep this one  (negation, pathspec only)
  /local_scratch        <- anchored: skip only at the root level  (pathspec only)

Without pathspec, only bare directory names (no wildcards) are honoured.

=============================================================================
ADDING / REMOVING A DEFAULT EXCLUSION
=============================================================================

Edit DEFAULT_EXCLUDE_DIRS below.  Each entry has a comment explaining why
it exists so future maintainers can make an informed decision about removing it.

To let a user include something from the defaults (e.g. they want to scan
their venv docs), they pass --no-defaults and re-add only what they want via
--exclude.

=============================================================================
BINARY FILE DETECTION
=============================================================================

Binary files are detected by reading the first 8 KB and checking for a null
byte (the same heuristic git uses).  Files that fail this check are skipped
before any model call -- feeding raw binary to a language model produces
garbage output and wastes GPU time.

Binary formats that carry extractable knowledge (PDFs, DOCX, images with text)
require pre-processing before extraction.  Graphify plugins handle this by
decoding the format (OCR, document parsing) before passing text to the model.
This pipeline processes plain text only and documents its limitation clearly.
"""

from pathlib import Path
import sys

# ── pathspec: optional but strongly recommended ────────────────────────────────
try:
    import pathspec as _pathspec
    _HAS_PATHSPEC = True
except ImportError:
    _pathspec = None
    _HAS_PATHSPEC = False


# ── Built-in default exclusions ────────────────────────────────────────────────
# Each entry is a lowercase directory name.  If any ancestor directory of a
# file matches an entry, that file's entire subtree is skipped.
#
# WHY THESE ARE HERE (and when it is safe to remove them):
#   Override all of these with --no-defaults, then add back only what you need
#   via --exclude.  Per-directory .extractignore is the cleanest opt-out.

DEFAULT_EXCLUDE_DIRS: frozenset = frozenset({

    # --- Version control internals ---
    # These contain metadata, object stores, and history -- not source content.
    ".git", ".svn", ".hg",

    # --- Python virtual environments ---
    # Your project's third-party installed packages live here.  Including them
    # would add thousands of library files that describe dependencies, not your
    # own codebase.  If you specifically want to index a venv (e.g. to graph
    # your dependency relationships), use --no-defaults.
    ".venv", "venv", "env", ".env",

    # --- Python tool caches ---
    # Compiled bytecode and tool-state dirs.  Not human-authored content.
    "__pycache__",
    ".tox", ".nox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",

    # --- JavaScript / Node.js ---
    # node_modules can contain tens of thousands of files.  Same principle as
    # .venv above.
    "node_modules", ".yarn", ".pnp",

    # --- Build and distribution outputs ---
    # Generated artefacts that are derived from source, not the source itself.
    # If you want to graph your compiled output (e.g. to compare with source),
    # remove these entries via --no-defaults.
    "dist", "build", "target", "out", "_build", "site",

    # --- IDE and editor state ---
    # Project settings, run configurations, scratch files.  Not source content.
    ".idea", ".vscode", ".vs",

    # --- Claude Code / session state ---
    # Project-management files (PENDING-TASK, PROGRESS, TODO) and session logs.
    # These describe the development process, not the codebase being indexed.
    ".claude", ".remember",

    # --- Previous extraction outputs ---
    # The pipeline writes its own output into 'responses/'.  Excluding it
    # prevents circular indexing (the graph describing itself).
    "responses",
})


# ── Binary detection ───────────────────────────────────────────────────────────

def is_binary(path: Path, sample_size: int = 8192) -> bool:
    """
    Return True if path is a binary file that cannot be usefully extracted.

    Method: read the first sample_size bytes and check for a null byte (0x00).
    This is the same heuristic git uses and correctly identifies compiled code,
    images, archives, and most binary formats while never false-positiving on
    valid UTF-8 text.

    What to do with binary files:
      - Skip them in this pipeline (plain text only).
      - For PDFs, DOCX, images with embedded text: use graphify plugins, which
        can decode those formats before passing text to the extraction model.
      - For compiled code (.pyc, .class, .wasm): index the source instead.

    Returns True (treat as binary) if the file cannot be opened.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
        return b"\x00" in chunk
    except OSError:
        return True  # unreadable -> skip safely


# ── IgnoreSpec ─────────────────────────────────────────────────────────────────

class IgnoreSpec:
    """
    Encapsulates all ignore rules built during the pre-scan pass.
    Call .match(path) to test whether a file should be excluded.
    """

    def __init__(
        self,
        root: Path,
        exclude_dirs: set,
        pathspec_rules: list,
        ignore_files: list,
    ):
        self._root = root
        self._exclude_dirs = exclude_dirs       # set of lowercase dir names
        self._pathspec_rules = pathspec_rules   # list of (base_dir, PathSpec)
        self._ignore_files = ignore_files       # list of (Path, label) for reporting

    def match(self, path: Path) -> bool:
        """
        Return True if path should be excluded from extraction.

        Step 1 -- directory-name check (fast, no I/O):
          If any ancestor directory matches an entry in exclude_dirs, return True.

        Step 2 -- pathspec glob rules (only when pathspec is installed):
          Each rule is scoped to the directory containing its .*ignore file.
          The path is tested relative to that base directory, preserving the
          same semantics as git (a .gitignore in src/ only affects src/**).
        """
        try:
            parts = path.relative_to(self._root).parts
        except ValueError:
            parts = path.parts

        # Step 1: dir-name check
        for part in parts[:-1]:
            if part.lower() in self._exclude_dirs:
                return True

        # Step 2: pathspec rules
        for base_dir, spec in self._pathspec_rules:
            try:
                rel = path.relative_to(base_dir)
                # pathspec expects forward slashes
                if spec.match_file(str(rel).replace("\\", "/")):
                    return True
            except ValueError:
                pass  # path is not under this base_dir, skip this rule

        return False

    def summary(self) -> str:
        """Return a brief human-readable description of active ignore sources."""
        dir_count = len(self._exclude_dirs)
        dirs_preview = ", ".join(sorted(self._exclude_dirs)[:8])
        if dir_count > 8:
            dirs_preview += f" ... (+{dir_count - 8} more)"
        lines = [f"  Excluded dir names ({dir_count}): {dirs_preview}"]
        if self._ignore_files:
            lines.append(f"  Ignore files applied ({len(self._ignore_files)}):")
            for p, label in self._ignore_files:
                lines.append(f"    [{label}]  {p}")
        if not _HAS_PATHSPEC:
            lines.append(
                "  NOTE: pathspec not installed -- dir-name matching only.\n"
                "        For full glob/wildcard gitignore support: pip install pathspec"
            )
        return "\n".join(lines)


# ── Pre-scan builder ───────────────────────────────────────────────────────────

def _load_pathspec(path: Path, label: str, found: list) -> tuple:
    """Parse one ignore file into a pathspec.  Returns (base_dir, spec) or None."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        spec = _pathspec.PathSpec.from_lines("gitignore", lines)
        found.append((path, label))
        return (path.parent, spec)
    except Exception:
        return None


def _load_simple_dirs(path: Path, label: str, found: list) -> set:
    """Parse one ignore file for bare dir names (pathspec fallback)."""
    dirs: set = set()
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            name = line.rstrip("/").rstrip("\\").strip()
            if any(c in name for c in ("/", "\\", "*", "?")):
                continue
            if name:
                dirs.add(name.lower())
        found.append((path, label))
    except Exception:
        pass
    return dirs


def build_ignore_spec(
    root: Path,
    respect_gitignore: bool = True,
    extra_excludes: list = None,
    ignore_path: str = None,
    no_defaults: bool = False,
) -> "IgnoreSpec":
    """
    Pre-scan pass: discover all .*ignore files, parse them, and return an
    IgnoreSpec that answers .match(path) for any file in the tree.

    This runs ONCE before the main scan.  The cost is proportional to the
    number of .*ignore files found, not the number of files being scanned.

    Parameters
    ----------
    root : Path
        Directory being scanned.  .*ignore files are searched recursively here.
    respect_gitignore : bool
        If True (default), find and apply every .gitignore under root,
        each scoped to its own directory.  Disable with --no-gitignore.
    extra_excludes : list[str]
        Bare directory names from --exclude on the CLI.
    ignore_path : str
        Path to a single custom ignore file (--ignore-path).
        Applied as if it were a .extractignore at the scan root.
    no_defaults : bool
        If True, start with an EMPTY exclusion set (DEFAULT_EXCLUDE_DIRS is
        not applied).  Use when the defaults exclude something you need.
        Enable with --no-defaults.

    Returns
    -------
    IgnoreSpec
        Call .match(path) -> bool on any Path to test exclusion.
        Call .summary() to print a human-readable description.
    """
    exclude_dirs: set = set() if no_defaults else set(DEFAULT_EXCLUDE_DIRS)

    if extra_excludes:
        exclude_dirs |= {e.lower() for e in extra_excludes if e}

    pathspec_rules: list = []
    ignore_files_found: list = []

    if _HAS_PATHSPEC:
        # Full gitwildmatch semantics: find every .*ignore, scope it to its dir
        if respect_gitignore:
            for p in sorted(root.rglob(".gitignore")):
                rule = _load_pathspec(p, ".gitignore", ignore_files_found)
                if rule:
                    pathspec_rules.append(rule)

        for p in sorted(root.rglob(".extractignore")):
            rule = _load_pathspec(p, ".extractignore", ignore_files_found)
            if rule:
                pathspec_rules.append(rule)

        if ignore_path:
            custom = Path(ignore_path)
            if custom.exists():
                rule = _load_pathspec(custom, "--ignore-path", ignore_files_found)
                if rule:
                    # Custom file scoped to root (applies globally)
                    pathspec_rules.append((root, rule[1]))
            else:
                print(f"  WARNING: --ignore-path not found: {custom}", file=sys.stderr)

    else:
        # pathspec unavailable: extract bare dir-names only
        print(
            "\n  INFO: 'pathspec' not installed.\n"
            "        Glob patterns in .*ignore files will be ignored.\n"
            "        Only bare directory names will be respected.\n"
            "        Install for full gitignore support: pip install pathspec\n",
            file=sys.stderr,
        )
        if respect_gitignore:
            for p in sorted(root.rglob(".gitignore")):
                exclude_dirs |= _load_simple_dirs(p, ".gitignore", ignore_files_found)

        for p in sorted(root.rglob(".extractignore")):
            exclude_dirs |= _load_simple_dirs(p, ".extractignore", ignore_files_found)

        if ignore_path:
            custom = Path(ignore_path)
            if custom.exists():
                exclude_dirs |= _load_simple_dirs(custom, "--ignore-path", ignore_files_found)
            else:
                print(f"  WARNING: --ignore-path not found: {custom}", file=sys.stderr)

    return IgnoreSpec(root, exclude_dirs, pathspec_rules, ignore_files_found)


# ── Output cleanup ────────────────────────────────────────────────────────────

def clean_output(paths, yes: bool = False) -> bool:
    """Delete one or more output files after optional confirmation.

    Parameters
    ----------
    paths : Path | list[Path]
        File(s) to delete.  Non-existent paths are silently skipped.
    yes : bool
        Skip the interactive prompt (for scripting / --yes flag).

    Returns
    -------
    bool
        True if at least one file was deleted, False if nothing was cleaned
        (nothing existed, or the user declined).
    """
    if isinstance(paths, Path):
        paths = [paths]

    existing = [p for p in paths if p.exists()]
    if not existing:
        print("  Nothing to clean — no output files found.")
        return False

    if not yes:
        print("  The following file(s) will be permanently deleted:")
        for p in existing:
            print(f"    {p}")
        answer = input("  Confirm? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted — nothing deleted.")
            return False

    for p in existing:
        p.unlink()
        print(f"  Cleaned: {p}")
    return True
