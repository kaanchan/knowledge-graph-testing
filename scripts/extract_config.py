"""
extract_config.py -- Shared ignore/scan configuration for the extraction pipeline.

All three extraction scripts (nuextract_pipeline, kggen_pipeline, dispatch_pipeline)
import from here so exclusion rules stay in one place.

HOW IGNORING WORKS
  Exclusions are directory names (not file patterns). If a directory name appears
  in the exclusion set, the entire subtree beneath it is skipped.

  Sources merged in order (all applied together, union):
    1. DEFAULT_EXCLUDE_DIRS -- hardcoded sensible defaults (below)
    2. .gitignore at the scan root -- simple dir-name entries (if respect_gitignore=True)
    3. All .extractignore files found anywhere under the scan root -- global merge
    4. ignore_path -- a custom ignore file you point to with --ignore-path
    5. extra_excludes -- dir names passed via --exclude on the CLI

.extractignore FORMAT
  Place a .extractignore file at the repo root or any subdirectory.
  All .extractignore files are discovered automatically and merged globally.

  Format (same as .gitignore):
    # This is a comment
    node_modules       <- directory name to skip (no wildcards needed)
    dist/              <- trailing slash is stripped, same effect
    my_test_fixtures   <- any simple directory name

  Rules:
    - Lines starting with '#' are comments
    - Lines starting with '!' are ignored (negation not supported)
    - Entries with '/', '\\', '*', or '?' are skipped (use dir names only)
    - Matching is case-insensitive

ADDING A NEW DEFAULT EXCLUSION
  Edit DEFAULT_EXCLUDE_DIRS below. The change applies to all three scripts
  automatically -- no need to update each one separately.
"""

from pathlib import Path

# ── Built-in defaults ──────────────────────────────────────────────────────────
# These are always excluded regardless of any flags.
# Common virtual-env, build-output, tool-state, and third-party dirs.

DEFAULT_EXCLUDE_DIRS: frozenset = frozenset({
    # Version control
    ".git", ".svn", ".hg",
    # Python environments and caches
    ".venv", "venv", "env", ".env", "__pycache__", ".pyc",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    # JS / Node
    "node_modules", ".yarn", ".pnp",
    # Build outputs
    "dist", "build", "target", "out", "_build", "site",
    # IDE / tool state
    ".idea", ".vscode", ".vs",
    # Claude / session state (project management, session logs)
    ".claude", ".remember",
    # Previous extraction outputs (avoid circular indexing)
    "responses",
})


# ── Ignore file parser ─────────────────────────────────────────────────────────

def _parse_ignore_file(path: Path) -> set:
    """
    Parse a .gitignore-style file and return a set of simple directory names.

    Only bare names are extracted (no wildcards, no path separators).
    This covers the most common .gitignore entries like 'node_modules' or '.venv/'.
    Complex glob patterns are silently skipped.
    """
    dirs: set = set()
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            name = line.rstrip("/").rstrip("\\").strip()
            # Skip anything with path separators or wildcard characters
            if any(c in name for c in ("/", "\\", "*", "?")):
                continue
            if name:
                dirs.add(name.lower())
    except Exception:
        pass
    return dirs


# ── Main API ───────────────────────────────────────────────────────────────────

def build_exclude_set(
    root: Path,
    respect_gitignore: bool = True,
    extra_excludes: list = None,
    ignore_path: str = None,
) -> set:
    """
    Build the complete directory-name exclusion set for a scan.

    Parameters
    ----------
    root : Path
        The directory being scanned. .gitignore and .extractignore files
        are searched relative to this root.
    respect_gitignore : bool
        If True (default), read root/.gitignore and add simple dir-name entries.
        Pass False (--no-gitignore) to skip this.
    extra_excludes : list[str]
        Additional dir names from the --exclude CLI argument.
    ignore_path : str
        Path to a custom ignore file (--ignore-path). Parsed the same way
        as .extractignore.

    Returns
    -------
    set[str]
        Lowercase directory names. Any directory whose name (lowercased)
        appears in this set will be skipped entirely during scanning.
    """
    result: set = set(DEFAULT_EXCLUDE_DIRS)

    # Source 2: .gitignore at root
    if respect_gitignore:
        gitignore = root / ".gitignore"
        if gitignore.exists():
            found = _parse_ignore_file(gitignore)
            if found:
                result |= found

    # Source 3: all .extractignore files anywhere under root (global merge)
    try:
        for extractignore in sorted(root.rglob(".extractignore")):
            found = _parse_ignore_file(extractignore)
            if found:
                result |= found
    except Exception:
        pass

    # Source 4: custom ignore file (--ignore-path)
    if ignore_path:
        custom = Path(ignore_path)
        if custom.exists():
            result |= _parse_ignore_file(custom)
        else:
            # Warn but don't abort -- misconfigured ignore path shouldn't crash a long run
            import sys
            print(f"  WARNING: --ignore-path not found: {custom}", file=sys.stderr)

    # Source 5: --exclude CLI args
    if extra_excludes:
        result |= {e.lower() for e in extra_excludes if e}

    return result


def is_excluded(path: Path, root: Path, exclude_dirs: set) -> bool:
    """
    Return True if any ancestor directory component of path is in exclude_dirs.

    Example: for path = root/.venv/lib/python/site.py
      parts[:-1] = ['.venv', 'lib', 'python']
      '.venv' is in exclude_dirs -> True (skip this file)
    """
    parts_lower = {p.lower() for p in path.relative_to(root).parts[:-1]}
    return bool(parts_lower & exclude_dirs)
