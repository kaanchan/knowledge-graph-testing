"""
kggen_pipeline.py — Path B: kg-gen SPO triple extraction on test corpus.

PREREQUISITES:
    # In your test venv:
    uv add kg-gen

    # Verify no DSPy version conflicts (kg-gen depends on DSPy internally):
    pip check
    # If conflicts found, resolve before running this script.
    # Common conflict: kg-gen may pin dspy-ai to a specific version; check output carefully.

    # Ollama must be running with Phi-4:
    ollama pull phi4   # or whichever phi-4 variant is available
    ollama serve       # runs on http://localhost:11434 (default)

USAGE:
    python scripts/kggen_pipeline.py \\
        --test-slice-dir <path-to-10-file-test-slice-dir> \\
        --output-dir r&d/1-find-offline-semantic-tool/responses/

    Or specify individual files:
    python scripts/kggen_pipeline.py \\
        --files path/to/file1.py path/to/file2.md ... \\
        --output-dir r&d/1-find-offline-semantic-tool/responses/

NOTES:
    - Uses LiteLLM format: model="ollama_chat/phi-4"
      This targets Ollama /api/chat — NOT llama-server.
    - api_base="http://localhost:11434" (Ollama default port)
    - Manual chunking at ~3,000 tokens per chunk for large files.
    - All chunks per file are aggregated into a single output record.
    - Output: r&d/1-find-offline-semantic-tool/responses/kggen-output-sample.json
    - Run on the SAME 5 Python + 5 markdown test slice used in Step 1 for comparison.

GH issue: #6 (ref #8)
"""

import json
import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

# pip check reminder — run before first use:
# pip check
# If DSPy conflicts are present, see README or kg-gen documentation.

try:
    from kg_gen import KGGen
except ImportError:
    sys.exit(
        "ERROR: 'kg-gen' not installed.\n"
        "Run: uv add kg-gen\n"
        "Then: pip check   (verify no DSPy conflicts)"
    )

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    def count_tokens(text: str) -> int:
        # Rough estimate: 1 token ≈ 0.75 words
        return int(len(text.split()) / 0.75)

# ── Preflight checks ──────────────────────────────────────────────────────────

def _ollama_not_running_msg(api_base: str) -> str:
    sep = "=" * 68
    return f"""
{sep}
  PREFLIGHT FAILED — Ollama is not running
{sep}

  What is Ollama?
    Ollama is a free, local AI model server. It runs language models
    entirely on your own machine — no internet connection or API key
    is required after the initial download. This script uses Ollama
    to run Phi-4, the reasoning model that extracts knowledge graph
    triples (subject → predicate → object) from your source files.

  How to start Ollama:
    1. Install Ollama (one-time, free):
         https://ollama.com/download
    2. Start the server in a terminal:
         ollama serve
       Or open the Ollama desktop app — it starts the server automatically.
    3. Confirm it is running:
         curl {api_base}/api/tags
       You should see a JSON object listing available models.
    4. Re-run this script.

  What Ollama provides once running:
    - Runs AI models fully offline on your GPU or CPU
    - Manages model downloads, versions, and memory automatically
    - Exposes a local REST API at {api_base}
      (nothing leaves your machine)

  Hardware requirements for this pipeline:
    Phi-4 Q4_K_M  ~9 GB VRAM  (used by this script)
    If you have less VRAM, use a smaller model:
      --model ollama_chat/phi3    (~4 GB VRAM)
      --model ollama_chat/llama3  (~5 GB VRAM)

  To stop Ollama later:
    Press Ctrl+C in the terminal where you ran 'ollama serve'.
    Or: File → Quit in the desktop app.

  To uninstall Ollama:
    Windows: Settings → Apps → Ollama → Uninstall
    macOS:   Move Ollama.app to Trash, then: rm -rf ~/.ollama
{sep}
"""


def _model_not_found_msg(bare_model: str, available: list) -> str:
    sep = "=" * 68
    available_str = "\n    ".join(available) if available else "(none pulled yet)"
    return f"""
{sep}
  PREFLIGHT FAILED — Model '{bare_model}' is not in Ollama
{sep}

  What is Phi-4?
    Phi-4 is Microsoft's 14-billion parameter reasoning model. In this
    pipeline it reads source files (Python, Markdown, etc.) and extracts
    Subject → Predicate → Object triples — the edges of your knowledge
    graph. It is strong at understanding code structure and documentation.

    Phi-4 runs fully offline via Ollama once downloaded.

  How to set it up (one-time, ~9 GB download):

    Step 1 — Pull the model (Ollama handles the download automatically):
      ollama pull phi4

    Step 2 — Confirm it appears:
      ollama list
      (you should see phi4:latest)

    Step 3 — Re-run this script.

  Why is this taking ~9 GB?
    Phi-4 is a 14B-parameter model quantised to 4 bits (Q4_K_M).
    Larger models produce higher-quality extractions. If 9 GB VRAM is
    not available, try a smaller alternative:
      ollama pull phi3           # ~4 GB VRAM
      ollama pull llama3         # ~5 GB VRAM
    Then pass --model ollama_chat/phi3 (or llama3) when running.

  Tweaking the model:
    --model ollama_chat/<name>  use any model pulled in Ollama
    --api-base <url>            point to a different Ollama instance
    Temperature is fixed at 0.0 for deterministic extraction.

  To remove the model later:
    ollama rm phi4
    (Ollama manages the weights — no manual file deletion needed)

  Models currently available in your Ollama:
    {available_str}
{sep}
"""


def _elapsed_str(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


def _unload_model(model_name: str, api_base: str) -> None:
    """Tell Ollama to evict the model from GPU/CPU memory immediately."""
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
    total_planned: int,
    output_path,
    start_time: float,
    pid: int,
    aborted: bool,
    model_name: str,
    api_base: str,
) -> None:
    """Write output (partial or full) and print a final shutdown report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    total_entities  = sum(len(r.get("entities",  [])) for r in results)
    total_edges     = sum(len(r.get("edges",     [])) for r in results)
    total_relations = sum(len(r.get("relations", [])) for r in results)
    files_with_triples = sum(1 for r in results if r.get("edges") or r.get("relations"))
    skipped = total_planned - len(results)
    elapsed = time.monotonic() - start_time

    status = "ABORTED -- Ctrl+C" if aborted else "EXTRACTION COMPLETE"
    sep = "=" * 64

    print()
    print(sep)
    print(f"  {status}")
    print(sep)
    print(f"  PID:                    {pid}")
    print(f"  Total time:             {_elapsed_str(elapsed)}")
    print(f"  Files planned:          {total_planned}")
    print(f"  Files completed:        {len(results)}", end="")
    if aborted:
        print(f"  ({skipped} not processed)")
    else:
        print()
    print(f"  Files with SPO triples: {files_with_triples} / {len(results)}")
    print(f"  Entities found:         {total_entities}")
    print(f"  Edges/triples found:    {total_edges + total_relations}")
    print(f"  Output saved:           {output_path}")
    if aborted:
        print(f"  NOTE: Partial output -- re-run to continue (skipped files not saved).")
    print()
    if results:
        _unload_model(model_name, api_base)
    else:
        print(f"  No files processed -- model was not loaded, nothing to unload.")
    print(f"  PID {pid} exiting cleanly.")
    print(sep)


def _progress_line(done: int, total: int, recent_times: list) -> str:
    """Return a one-line progress string with percentage, avg speed, and ETA."""
    pct = done / total * 100
    if not recent_times:
        return f"  [{done}/{total}]  {pct:.0f}%"
    avg = sum(recent_times) / len(recent_times)
    eta_secs = avg * (total - done)
    h, rem = divmod(int(eta_secs), 3600)
    m, s = divmod(rem, 60)
    eta_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
    return f"  [{done}/{total}]  {pct:.0f}%  ~{avg:.1f}s/file  ETA {eta_str}"


def preflight_check(litellm_model: str, api_base: str = "http://localhost:11434") -> None:
    """Verify Ollama is reachable and the required model is pulled. Exit with guidance if not."""
    import urllib.request
    import urllib.error

    # Strip LiteLLM provider prefix to get the bare Ollama model name
    # e.g. "ollama_chat/phi-4" → "phi-4", "ollama/phi4" → "phi4"
    bare_model = litellm_model.split("/", 1)[-1] if "/" in litellm_model else litellm_model

    # 1 — Daemon check
    try:
        urllib.request.urlopen(f"{api_base}/api/tags", timeout=3)
    except Exception:
        print(_ollama_not_running_msg(api_base))
        sys.exit(1)

    # 2 — Model availability check
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        # Tags endpoint returns names like "phi4:latest" — strip the tag
        available = [m["name"].split(":")[0] for m in data.get("models", [])]
        # Accept "phi-4" matching "phi4" and vice versa (Ollama normalises hyphens)
        normalised_target = bare_model.replace("-", "")
        if not any(
            a == bare_model
            or a == normalised_target
            or a.replace("-", "") == normalised_target
            for a in available
        ):
            print(_model_not_found_msg(bare_model, available))
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"WARNING: Could not verify model list: {exc}\n  Proceeding anyway.")


# ── Constants ─────────────────────────────────────────────────────────────────

OLLAMA_MODEL    = "ollama_chat/phi-4"   # LiteLLM format targeting Ollama /api/chat
OLLAMA_API_BASE = "http://localhost:11434"
CHUNK_TOKENS    = 3_000                  # max tokens per chunk for large files

# Supported file extensions for the test corpus
SUPPORTED_EXTENSIONS = {".py", ".md", ".txt", ".rst"}

# Fixed output path per spec §Step 4
OUTPUT_FILENAME = "kggen-output-sample.json"


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, max_tokens: int = CHUNK_TOKENS) -> list[str]:
    """Split text into chunks of at most max_tokens (non-overlapping for kg-gen)."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start
        running = 0
        while end < len(words) and running < max_tokens:
            running = count_tokens(" ".join(words[start:end + 1]))
            end += 1
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end
    return chunks


# ── Per-file extraction ───────────────────────────────────────────────────────

def extract_file(kg: KGGen, file_path: str) -> dict:
    """Run kg-gen on a single file, chunking if necessary. Aggregates all chunks."""
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    token_count = count_tokens(text)

    print(f"  Processing: {file_path} (~{token_count} tokens)")

    if token_count <= CHUNK_TOKENS:
        chunks = [text]
    else:
        chunks = chunk_text(text, CHUNK_TOKENS)
        print(f"    -> {len(chunks)} chunk(s) at ~{CHUNK_TOKENS} tokens each")

    all_entities: list = []
    all_edges:    list = []
    all_relations: list = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    Chunk {i + 1}/{len(chunks)}")

        try:
            result = kg.generate(input_data=chunk)
            # kg-gen returns an object with .entities, .edges, .relations attributes
            # depending on version — handle both dict and object forms
            if isinstance(result, dict):
                chunk_entities  = result.get("entities", [])
                chunk_edges     = result.get("edges", [])
                chunk_relations = result.get("relations", [])
            else:
                chunk_entities  = getattr(result, "entities",  []) or []
                chunk_edges     = getattr(result, "edges",     []) or []
                chunk_relations = getattr(result, "relations", []) or []

            all_entities.extend(chunk_entities)
            all_edges.extend(chunk_edges)
            all_relations.extend(chunk_relations)

        except Exception as exc:
            print(f"    WARNING: chunk {i + 1} failed: {exc}")

    return {
        "source_file":     str(Path(file_path).as_posix()),
        "token_count":     token_count,
        "chunks_processed": len(chunks),
        "entities":        all_entities,
        "edges":           all_edges,
        "relations":       all_relations,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="kg-gen SPO triple extraction on test corpus (Path B, Step 4, GH #6 ref #8)"
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--test-slice-dir",
        help="Directory containing the 10-file test slice (walks for .py and .md)"
    )
    source_group.add_argument(
        "--files",
        nargs="+",
        help="Explicit list of file paths to process"
    )

    parser.add_argument(
        "--output-dir",
        default="r&d/1-find-offline-semantic-tool/responses/",
        help="Directory to write kggen-output-sample.json"
    )
    parser.add_argument(
        "--model",
        default=OLLAMA_MODEL,
        help=f"LiteLLM model string (default: {OLLAMA_MODEL})"
    )
    parser.add_argument(
        "--api-base",
        default=OLLAMA_API_BASE,
        help=f"Ollama API base URL (default: {OLLAMA_API_BASE})"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all files even if already present in the output (disables resume)"
    )
    args = parser.parse_args()

    pid = os.getpid()
    start_time = time.monotonic()
    print(f"  PID {pid}  |  Stop cleanly: Ctrl+C  |  Force kill: taskkill /PID {pid} /F")
    print()

    preflight_check(args.model, args.api_base)

    # Collect files
    if args.files:
        file_list = [Path(f) for f in args.files]
    else:
        slice_dir = Path(args.test_slice_dir)
        if not slice_dir.exists():
            sys.exit(f"ERROR: --test-slice-dir not found: {slice_dir}")
        file_list = sorted(
            f for f in slice_dir.rglob("*")
            if f.suffix in SUPPORTED_EXTENSIONS
        )

    if not file_list:
        sys.exit("ERROR: No files found to process.")

    print(f"kg-gen pipeline — Step 4 Path B")
    print(f"Model:    {args.model}")
    print(f"API base: {args.api_base}")
    print(f"Files:    {len(file_list)}")
    print()

    # Initialise kg-gen
    # NOTE: pip check before first run to verify no DSPy version conflicts.
    kg = KGGen(
        model=args.model,         # LiteLLM format: ollama_chat/phi-4 → Ollama /api/chat
        temperature=0.0,
        api_base=args.api_base,   # Ollama directly — NOT llama-server
    )

    # Prepare output path early so partial results can always be saved
    output_dir = Path(args.output_dir)
    output_path = output_dir / OUTPUT_FILENAME

    # Strip LiteLLM prefix to get the bare Ollama model name for unloading
    bare_model = args.model.split("/", 1)[-1] if "/" in args.model else args.model

    # Resume: skip files already in the output unless --force
    existing_results: list = []
    if output_path.exists() and not args.force:
        try:
            existing_results = json.loads(output_path.read_text(encoding="utf-8"))
            already_done = {r["source_file"] for r in existing_results if "source_file" in r}
            before = len(file_list)
            file_list = [fp for fp in file_list if str(fp.as_posix()) not in already_done]
            skipped = before - len(file_list)
            if skipped:
                print(f"  Resume: {skipped} file(s) already processed, {len(file_list)} remaining.")
                print(f"  (Use --force to reprocess everything.)")
                print()
        except Exception:
            existing_results = []

    if not file_list:
        print("  All files already processed. Nothing to do.")
        print(f"  Output: {output_path}")
        return

    aborted = False
    results = []
    recent_times: list = []  # rolling window of last 10 file durations
    try:
        for i, fp in enumerate(file_list):
            print(_progress_line(i, len(file_list), recent_times))
            t0 = time.monotonic()
            try:
                record = extract_file(kg, str(fp))
            except Exception as exc:
                print(f"  ERROR: {exc}")
                record = {"source_file": str(fp.as_posix()), "error": str(exc)}
            elapsed = time.monotonic() - t0
            recent_times.append(elapsed)
            if len(recent_times) > 10:
                recent_times.pop(0)
            results.append(record)
    except KeyboardInterrupt:
        aborted = True
        print("\n\n  Ctrl+C received -- writing partial results and shutting down...")

    _write_and_report(
        existing_results + results, len(file_list), output_path,
        start_time, pid, aborted, bare_model, args.api_base,
    )

    if not aborted:
        print()
        print("SUCCESS GATE: >= 1 SPO triple per file, subjects/objects are real code symbols or concepts.")
        print("Compare this output with Step 1 graphify output on the same 10 files.")

    if aborted:
        sys.exit(130)


if __name__ == "__main__":
    main()
