"""
dispatch_pipeline.py — Unified dispatcher for knowledge graph extraction.

Classifies every file in a directory by type, routes it to the best model,
and falls back to the alternative model if the primary returns empty output
or raises an error.

ROUTING TABLE
  prose   (.md .txt .rst .adoc .tex .wiki .org)
              → nuextract3 primary  /  phi4 fallback
  code    (.py .js .ts .go .rs .java .c .cpp .cs .sh .ps1 .sql ...)
              → phi4 primary  /  nuextract3 fallback
  config  (.yaml .yml .toml .json .ini .cfg .env .xml .properties)
              → phi4 primary  /  nuextract3 fallback
  skip    (.png .jpg .pdf .zip .exe .pyc .lock ...)
              → always skipped

DEFAULT EXCLUSIONS (applied automatically, extend with --exclude)
  .git/  node_modules/  __pycache__/  .venv/  venv/  dist/  build/
  .claude/pm/  r&d/responses/

PREREQUISITES
  pip install ollama tiktoken kg-gen
  ollama pull phi4
  # and nuextract3 registered — see scripts/nuextract_pipeline.py

USAGE
  # Dry-run: see what will be routed where (no extraction)
  python scripts/dispatch_pipeline.py --dir <path> --dry-run

  # Full run
  python scripts/dispatch_pipeline.py --dir <path> --output-dir <out>

  # Disable fallback (strict: if primary fails, record the error and move on)
  python scripts/dispatch_pipeline.py --dir <path> --no-fallback

  # Override model choices
  python scripts/dispatch_pipeline.py --dir <path> \\
      --model-prose nuextract3 --model-code ollama_chat/phi4

GH issue: #10 (ref #8)
"""

import json
import argparse
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

# ── Ctrl+C / interrupt support ────────────────────────────────────────────────

_stop_event = threading.Event()


def _run_with_interrupt(fn, *args, **kwargs):
    """Run fn in a daemon thread, polling every 100ms for KeyboardInterrupt."""
    result = [None]
    exc = [None]

    def _worker():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    while t.is_alive():
        if _stop_event.is_set():
            raise KeyboardInterrupt
        t.join(timeout=0.1)

    if exc[0] is not None:
        raise exc[0]
    return result[0]


# ── Optional imports (checked at runtime with clear messages) ──────────────────

try:
    import ollama as _ollama_lib
except ImportError:
    _ollama_lib = None

try:
    from kg_gen import KGGen as _KGGen
except ImportError:
    _KGGen = None

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def _count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def _count_tokens(text: str) -> int:
        return int(len(text.split()) / 0.75)


# ── Shared scan configuration ──────────────────────────────────────────────────
from extract_config import build_ignore_spec, is_binary

# ── File classification ────────────────────────────────────────────────────────

# Maps category → set of lowercase extensions that belong to it.
# "skip" entries are never processed.
# Files with an extension not listed anywhere fall into "unknown" → treated as prose.

FILE_ROUTING: dict[str, set] = {
    "prose": {
        ".md", ".markdown", ".txt", ".rst", ".adoc", ".asciidoc",
        ".tex", ".latex", ".wiki", ".org", ".rdoc",
    },
    "code": {
        # Python / JS / TS ecosystem
        ".py", ".pyw", ".js", ".mjs", ".cjs", ".jsx",
        ".ts", ".tsx", ".vue", ".svelte",
        # JVM
        ".java", ".kt", ".kts", ".scala", ".groovy",
        # C family
        ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
        # .NET
        ".cs", ".fs", ".vb",
        # Systems
        ".go", ".rs", ".zig",
        # Scripting / shell
        ".rb", ".php", ".lua", ".pl", ".pm",
        ".sh", ".bash", ".zsh", ".fish",
        ".ps1", ".psm1", ".psd1", ".bat", ".cmd",
        # Query / data
        ".sql", ".graphql", ".gql",
        # Functional / other
        ".hs", ".ex", ".exs", ".clj", ".cljs", ".elm",
        ".r", ".rmd", ".m", ".swift",
        # Markup-as-code
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        # Notebooks (text form)
        ".ipynb",
    },
    "config": {
        ".json", ".jsonc", ".json5",
        ".yaml", ".yml",
        ".toml",
        ".ini", ".cfg", ".conf", ".config",
        ".env",
        ".xml", ".xsd", ".xsl", ".xslt", ".plist",
        ".properties", ".gradle",
        ".dockerfile",
    },
    "skip": {
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff",
        # Documents / archives
        ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
        # Binaries / compiled
        ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm",
        ".pyc", ".pyo", ".class", ".o", ".obj", ".a", ".lib",
        # Lock files (large, noisy, not useful for KG)
        ".lock",
        # Minified / source maps
        ".map",
        # Logs and runtime output (not codebase content)
        ".log", ".out", ".err",
        # Media
        ".mp3", ".mp4", ".wav", ".ogg", ".flac", ".avi", ".mov",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
        # Model weights (safety net in case repo is indexed from parent dir)
        ".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx",
    },
}



def classify(path: Path) -> str:
    """Return the routing category for a file based on its extension."""
    ext = path.suffix.lower()
    # Dot-only names like .gitignore, .env have suffix == "" — check stem
    if not ext and path.name.startswith("."):
        # Treat as config (e.g. .gitignore, .editorconfig, .env)
        return "config"
    for category, extensions in FILE_ROUTING.items():
        if ext in extensions:
            return category
    # Unknown extension → treat as prose (nuextract3 handles plain text well)
    return "unknown"


# ── Extraction functions ───────────────────────────────────────────────────────

_NUEXTRACT_TEMPLATE = json.dumps({
    "entities": [{"name": "", "type": ""}],
    "relations": [{"subject": "", "predicate": "", "object": ""}],
}, indent=2)

_NUEXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                "required": ["name", "type"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject":   {"type": "string"},
                    "predicate": {"type": "string"},
                    "object":    {"type": "string"},
                },
                "required": ["subject", "predicate", "object"],
            },
        },
    },
    "required": ["entities", "relations"],
}

_NUEXTRACT_WINDOW = 4_000   # tokens per sliding-window chunk
_PHI4_WINDOW      = 3_000   # tokens per chunk for phi-4 / kggen


def _chunk(text: str, max_tokens: int) -> list:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end, running = start, 0
        while end < len(words) and running < max_tokens:
            running = _count_tokens(" ".join(words[start:end + 1]))
            end += 1
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end
    return chunks


def _extract_nuextract3(text: str, model: str, api_base: str) -> dict:
    """Call nuextract3 (or any NuExtract-format model) via Ollama chat API."""
    if _ollama_lib is None:
        raise RuntimeError("ollama package not installed — run: pip install ollama")

    prompt = f"<|input|>\n### Template:\n{_NUEXTRACT_TEMPLATE}\n### Text:\n{text}\n\n<|output|>"
    chunks = _chunk(text, _NUEXTRACT_WINDOW)
    all_entities, all_relations = [], []

    for chunk in chunks:
        chunk_prompt = f"<|input|>\n### Template:\n{_NUEXTRACT_TEMPLATE}\n### Text:\n{chunk}\n\n<|output|>"
        response = _run_with_interrupt(
            _ollama_lib.chat,
            model=model,
            messages=[{"role": "user", "content": chunk_prompt}],
            think=False,
            format=_NUEXTRACT_SCHEMA,
            options={"temperature": 0.0},
            host=api_base,
        )
        raw = response["message"]["content"].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        all_entities.extend(e for e in parsed.get("entities", []) if e.get("name"))
        all_relations.extend(r for r in parsed.get("relations", []) if r.get("subject"))

    # Deduplicate entities by name (case-insensitive)
    seen: set = set()
    unique_entities = []
    for e in all_entities:
        key = e["name"].lower()
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    return {"entities": unique_entities, "relations": all_relations}


def _extract_phi4(text: str, model: str, api_base: str) -> dict:
    """Call phi-4 (or any LiteLLM-compatible model) via kg-gen."""
    if _KGGen is None:
        raise RuntimeError("kg-gen not installed — run: pip install kg-gen")

    kg = _KGGen(model=model, temperature=0.0, api_base=api_base)
    chunks = _chunk(text, _PHI4_WINDOW)
    all_entities, all_edges, all_relations = [], [], []

    for chunk in chunks:
        try:
            result = _run_with_interrupt(kg.generate, input_data=chunk)
            if isinstance(result, dict):
                all_entities.extend(result.get("entities", []))
                all_edges.extend(result.get("edges", []))
                all_relations.extend(result.get("relations", []))
            else:
                all_entities.extend(getattr(result, "entities", []) or [])
                all_edges.extend(getattr(result, "edges", []) or [])
                all_relations.extend(getattr(result, "relations", []) or [])
        except Exception as exc:
            raise RuntimeError(f"kg-gen chunk failed: {exc}") from exc

    return {"entities": all_entities, "edges": all_edges, "relations": all_relations}


def _is_empty(result: dict) -> bool:
    """True if a result has no usable entities or relations."""
    return (
        not result.get("entities")
        and not result.get("relations")
        and not result.get("edges")
    )


def extract_file(
    file_path: Path,
    primary: str,
    fallback: str | None,
    model_prose: str,
    model_code: str,
    api_base: str,
    no_fallback: bool,
) -> dict:
    """
    Extract knowledge graph data from one file.

    Tries the primary model first. If it raises or returns empty output,
    tries the fallback model (unless --no-fallback). Records which model
    was actually used and whether a fallback occurred.
    """
    text = file_path.read_text(encoding="utf-8", errors="replace")
    token_count = _count_tokens(text)

    def _run(model_key: str) -> dict:
        if model_key == "nuextract3":
            return _extract_nuextract3(text, model_prose, api_base)
        else:
            return _extract_phi4(text, model_code, api_base)

    primary_error = None
    result = None

    try:
        result = _run(primary)
    except Exception as exc:
        primary_error = str(exc)

    used_fallback = False
    fallback_error = None

    if (result is None or _is_empty(result)) and fallback and not no_fallback:
        reason = primary_error if primary_error else "empty output"
        print(f"    -> primary ({primary}) gave {reason}, trying fallback ({fallback})")
        used_fallback = True
        try:
            result = _run(fallback)
        except Exception as exc:
            fallback_error = str(exc)
            result = {}

    if result is None:
        result = {}

    record = {
        "source_file":    str(file_path.as_posix()),
        "token_count":    token_count,
        "model_used":     fallback if used_fallback else primary,
        "fallback_used":  used_fallback,
        "entities":       result.get("entities", []),
        "relations":      result.get("relations", []) + result.get("edges", []),
    }
    if primary_error:
        record["primary_error"] = primary_error
    if fallback_error:
        record["fallback_error"] = fallback_error
    return record


# ── Progress display ───────────────────────────────────────────────────────────

def _elapsed_str(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def _unload_model(model_name: str, api_base: str) -> None:
    """Tell Ollama to evict a model from GPU/CPU memory immediately."""
    print(f"  Unloading '{model_name}' from memory...", end=" ", flush=True)
    try:
        payload = json.dumps({
            "model": model_name,
            "prompt": "",
            "keep_alive": 0,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{api_base}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15)
        print("done.")
    except Exception as exc:
        print(f"WARNING: could not unload ({exc})")


def _write_and_report(
    results: list,
    existing_results: list,
    total_planned: int,
    output_path,
    start_time: float,
    pid: int,
    aborted: bool,
    models_used: set,
    api_base: str,
) -> None:
    """
    Merge new results with any previously-processed results, write to disk,
    and print a final shutdown report.
    """
    all_results = existing_results + results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Stats for this run only
    run_entities    = sum(len(r.get("entities", [])) for r in results)
    run_relations   = sum(len(r.get("relations", [])) for r in results)
    used_fallback   = sum(1 for r in results if r.get("fallback_used"))
    errored         = sum(1 for r in results if "error" in r)
    not_reached     = total_planned - len(results)
    elapsed         = time.monotonic() - start_time

    # Corpus-wide totals (including previously-processed files)
    prev_count      = len(existing_results)
    total_done      = len(all_results)
    total_entities  = sum(len(r.get("entities", [])) for r in all_results)
    total_relations = sum(len(r.get("relations", [])) for r in all_results)

    by_model: dict = {}
    for r in results:
        m = r.get("model_used", "unknown")
        by_model[m] = by_model.get(m, 0) + 1

    status = "ABORTED -- Ctrl+C" if aborted else "DISPATCH COMPLETE"
    sep = "=" * 68

    print()
    print(sep)
    print(f"  {status}")
    print(sep)
    print(f"  PID:                    {pid}")
    print(f"  Run time:               {_elapsed_str(elapsed)}")
    print()
    print(f"  --- This run ---")
    print(f"  Files targeted:         {total_planned}")
    print(f"  Files completed:        {len(results)}", end="")
    if aborted:
        print(f"  ({not_reached} not reached)")
    else:
        print()
    print(f"  Fallback triggered:     {used_fallback} file(s)")
    print(f"  Errors:                 {errored} file(s)")
    if by_model:
        print(f"  Model usage:")
        for m, count in sorted(by_model.items()):
            print(f"    {m:<20} {count} file(s)")
    print()
    print(f"  --- Corpus total (including previous runs) ---")
    print(f"  Previously processed:   {prev_count} file(s)")
    print(f"  Total processed:        {total_done} file(s)")
    print(f"  Total entities:         {total_entities}")
    print(f"  Total relations:        {total_relations}")
    print(f"  Output saved:           {output_path}")
    if aborted:
        print(f"  Re-run without --force to continue from where you left off.")
    print()
    if results:
        for model_name in sorted(models_used):
            _unload_model(model_name, api_base)
    else:
        print(f"  No files processed -- models were not loaded, nothing to unload.")
    print(f"  PID {pid} exiting cleanly.")
    print(sep)


def _progress_line(done: int, total: int, recent_times: list) -> str:
    pct = done / total * 100
    if not recent_times:
        return f"  [{done}/{total}]  {pct:.0f}%"
    avg = sum(recent_times) / len(recent_times)
    eta_secs = avg * (total - done)
    h, rem = divmod(int(eta_secs), 3600)
    m, s = divmod(rem, 60)
    eta_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
    return f"  [{done}/{total}]  {pct:.0f}%  ~{avg:.1f}s/file  ETA {eta_str}"


# ── Directory scanning ─────────────────────────────────────────────────────────

def _load_existing(output_path: Path) -> tuple:
    """
    Load a previous output JSON to support resume.
    Returns (records_list, set_of_processed_posix_paths).
    Returns ([], set()) if the file doesn't exist or can't be parsed.
    """
    if not output_path.exists():
        return [], set()
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return [], set()
        paths = {r["source_file"] for r in data if "source_file" in r}
        return data, paths
    except Exception as exc:
        print(f"  WARNING: Could not read existing output ({exc}) -- starting fresh.")
        return [], set()


def scan_files(
    root: Path,
    extra_excludes: list,
    use_gitignore: bool = True,
    ignore_path: str = None,
    no_defaults: bool = False,
) -> list:
    """
    Walk root recursively, classify each file, skip excluded dirs and binary files.
    Returns list of (path, category) tuples, sorted by path.

    Exclusions are resolved via extract_config.build_ignore_spec which merges:
      DEFAULT_EXCLUDE_DIRS + all .gitignore files (scoped) + all .extractignore files + ignore_path + extra_excludes.
    """
    ignore_spec = build_ignore_spec(
        root,
        respect_gitignore=use_gitignore,
        extra_excludes=extra_excludes,
        ignore_path=ignore_path,
        no_defaults=no_defaults,
    )
    print(ignore_spec.summary())
    print()
    classified = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if ignore_spec.match(path):
            continue
        if is_binary(path):
            continue
        category = classify(path)
        if category == "skip":
            continue
        classified.append((path, category))

    return classified


# ── Preflight ──────────────────────────────────────────────────────────────────

def _preflight_ollama(api_base: str) -> None:
    import urllib.request
    sep = "=" * 68
    try:
        urllib.request.urlopen(f"{api_base}/api/tags", timeout=3)
    except Exception:
        print(f"""
{sep}
  PREFLIGHT FAILED — Ollama is not running
{sep}

  The dispatcher needs Ollama running to serve both models.

  How to start Ollama:
    1. Install (one-time): https://ollama.com/download
    2. Run: ollama serve
       (or open the Ollama desktop app)
    3. Re-run this script.

  API base expected at: {api_base}
  Override with: --api-base <url>
{sep}
""")
        sys.exit(1)


def _preflight_model(bare_name: str, api_base: str, install_hint: str) -> bool:
    """
    Check if a model is in Ollama's list. Returns True if found.
    Does NOT exit — caller decides whether to abort or warn.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        available = [m["name"].split(":")[0] for m in data.get("models", [])]
        norm = bare_name.replace("-", "")
        found = any(
            a == bare_name or a == norm or a.replace("-", "") == norm
            for a in available
        )
        if not found:
            available_str = ", ".join(available) if available else "(none)"
            print(f"  WARNING: model '{bare_name}' not found in Ollama.")
            print(f"           Available: {available_str}")
            print(f"           To install: {install_hint}")
        return found
    except Exception as exc:
        print(f"  WARNING: could not verify model '{bare_name}': {exc}")
        return True  # assume present; let the first extraction call surface the error


def preflight(model_prose: str, model_code_litellm: str, api_base: str) -> None:
    """Check Ollama is up and both models are available. Warn (not abort) on missing models."""
    _preflight_ollama(api_base)

    bare_prose = model_prose
    bare_code  = model_code_litellm.split("/", 1)[-1] if "/" in model_code_litellm else model_code_litellm

    prose_ok = _preflight_model(
        bare_prose, api_base,
        f"huggingface-cli download numind/NuExtract3-GGUF --include '*Q4_K_M*' "
        f"--local-dir D:/Models/gguf/nuextract3 && "
        f"ollama create {bare_prose} -f scripts/nuextract3-modelfile.txt"
    )
    code_ok = _preflight_model(
        bare_code, api_base,
        f"ollama pull {bare_code}"
    )

    if not prose_ok and not code_ok:
        print("\n  ERROR: neither model is available. Cannot proceed.")
        sys.exit(1)

    if not prose_ok:
        print(f"  INFO: prose model unavailable — prose files will use {bare_code} only.")
    if not code_ok:
        print(f"  INFO: code model unavailable — code/config files will use {bare_prose} only.")

    print()


# ── Dry-run report ─────────────────────────────────────────────────────────────

def dry_run_report(classified: list, model_prose: str, model_code: str, no_fallback: bool) -> None:
    """Print a routing plan grouped by category without running extraction."""
    from collections import Counter
    counts: Counter = Counter(cat for _, cat in classified)

    print()
    print("=" * 68)
    print("  DRY RUN -- Routing plan (no extraction will run)")
    print("=" * 68)
    print()

    routing = {
        "prose":   (model_prose, "phi4" if not no_fallback else None),
        "code":    ("phi4",       model_prose if not no_fallback else None),
        "config":  ("phi4",       model_prose if not no_fallback else None),
        "unknown": (model_prose,  "phi4" if not no_fallback else None),
    }

    for cat, (primary, fallback) in routing.items():
        n = counts.get(cat, 0)
        if n == 0:
            continue
        fb_str = f"  fallback -> {fallback}" if fallback else "  no fallback"
        print(f"  {cat:<10} {n:>4} file(s)  primary -> {primary}{fb_str}")

    print()
    print(f"  Total files to process: {len(classified)}")
    print()

    # Show first 20 files as a sample
    sample = classified[:20]
    if sample:
        print("  Sample (first 20 files):")
        for path, cat in sample:
            print(f"    [{cat:<8}]  {path}")
        if len(classified) > 20:
            print(f"    ... and {len(classified) - 20} more")
    print()
    print("  Re-run without --dry-run to start extraction.")
    print("=" * 68)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Unified KG extraction dispatcher — classifies files by type, "
            "routes to the best model, falls back on failure. GH #10 ref #8."
        )
    )
    parser.add_argument(
        "--dir", required=True,
        help="Root directory to scan (searched recursively)"
    )
    parser.add_argument(
        "--output-dir",
        default="r&d/1-find-offline-semantic-tool/responses/",
        help="Where to write dispatch-output.json"
    )
    parser.add_argument(
        "--exclude", nargs="*", default=[],
        metavar="DIR",
        help="Extra directory names to skip (added to built-in exclusion list)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show routing plan without running extraction"
    )
    parser.add_argument(
        "--no-fallback", action="store_true",
        help="Disable fallback: if primary model fails, record the error and continue"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all files even if they appear in a previous output (disables resume)"
    )
    parser.add_argument(
        "--no-gitignore", action="store_true",
        help="Do not read .gitignore when building the exclusion list"
    )
    parser.add_argument(
        "--ignore-path", default=None,
        metavar="FILE",
        help="Path to a custom ignore file (same format as .extractignore)"
    )
    parser.add_argument(
        "--no-defaults", action="store_true",
        help="Disable built-in default exclusions (node_modules, .venv, __pycache__, etc.)"
    )
    parser.add_argument(
        "--model-prose", default="nuextract3",
        help="Ollama model name for prose files (default: nuextract3)"
    )
    parser.add_argument(
        "--model-code", default="ollama_chat/phi4",
        help="LiteLLM model string for code/config files (default: ollama_chat/phi4)"
    )
    parser.add_argument(
        "--api-base", default="http://localhost:11434",
        help="Ollama API base URL (default: http://localhost:11434)"
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        sys.exit(f"ERROR: --dir not found: {root}")

    # Prepare output path early (needed for resume check before scanning)
    output_dir = Path(args.output_dir)
    output_path = output_dir / "dispatch-output.json"

    # Scan and classify
    print(f"Scanning {root} ...")
    use_gitignore = not args.no_gitignore
    classified = scan_files(
        root, args.exclude,
        use_gitignore=use_gitignore,
        ignore_path=args.ignore_path,
        no_defaults=args.no_defaults,
    )

    if not classified:
        sys.exit(
            "ERROR: No processable files found.\n"
            "Check --dir and --exclude, and verify the directory contains "
            "supported file types (.py, .md, .js, .yaml, etc.)"
        )

    if args.dry_run:
        dry_run_report(classified, args.model_prose, args.model_code, args.no_fallback)
        return

    # Resume: load any previously-processed results and skip those files
    existing_results, already_processed = _load_existing(output_path)
    if args.force:
        existing_results, already_processed = [], set()

    if already_processed:
        before = len(classified)
        classified = [(fp, cat) for fp, cat in classified
                      if str(fp.as_posix()) not in already_processed]
        skipped_resume = before - len(classified)
        if skipped_resume:
            print(f"  Resume: {skipped_resume} file(s) already processed, "
                  f"{len(classified)} remaining.")
            print(f"  (Use --force to reprocess everything.)")
            print()
        if not classified:
            print("  All files already processed. Nothing to do.")
            print(f"  Output: {output_path}")
            print(f"  Use --force to reprocess.")
            return

    # Preflight
    preflight(args.model_prose, args.model_code, args.api_base)

    # Routing helpers
    def _primary_for(cat: str) -> str:
        return "nuextract3" if cat in ("prose", "unknown") else "phi4"

    def _fallback_for(cat: str) -> str | None:
        if args.no_fallback:
            return None
        return "phi4" if cat in ("prose", "unknown") else "nuextract3"

    pid = os.getpid()
    start_time = time.monotonic()
    print(f"  PID {pid}  |  Stop cleanly: Ctrl+C  |  Force kill: taskkill /PID {pid} /F")
    print()

    # Extraction loop
    print(f"Starting extraction on {len(classified)} file(s).")
    print(f"  Prose model:  {args.model_prose}")
    print(f"  Code model:   {args.model_code}")
    print(f"  Fallback:     {'disabled' if args.no_fallback else 'enabled'}")
    print()

    # Track which models were actually called so we know what to unload
    models_invoked: set = set()

    aborted = False
    results = []
    recent_times: list = []

    try:
        for i, (fp, category) in enumerate(classified):
            primary  = _primary_for(category)
            fallback = _fallback_for(category)
            print(_progress_line(i, len(classified), recent_times))
            print(f"  [{category:<8}] {fp.name}  -> {primary}")

            t0 = time.monotonic()
            try:
                record = extract_file(
                    fp, primary, fallback,
                    args.model_prose, args.model_code,
                    args.api_base, args.no_fallback,
                )
                record["category"] = category
                models_invoked.add(record.get("model_used", primary))
            except Exception as exc:
                print(f"    ERROR: {exc}")
                record = {
                    "source_file": str(fp.as_posix()),
                    "category": category,
                    "error": str(exc),
                }

            elapsed = time.monotonic() - t0
            recent_times.append(elapsed)
            if len(recent_times) > 10:
                recent_times.pop(0)
            results.append(record)
    except KeyboardInterrupt:
        _stop_event.set()
        aborted = True
        print("\n\n  Ctrl+C received -- writing partial results and shutting down...")

    # Map model keys ("nuextract3" / "phi4") to actual Ollama model names
    model_key_to_name = {
        "nuextract3": args.model_prose,
        "phi4":       args.model_code.split("/", 1)[-1] if "/" in args.model_code else args.model_code,
    }
    models_to_unload = {model_key_to_name.get(k, k) for k in models_invoked}

    _write_and_report(
        results, existing_results, len(classified), output_path,
        start_time, pid, aborted, models_to_unload, args.api_base,
    )

    if aborted:
        sys.exit(130)


if __name__ == "__main__":
    main()
