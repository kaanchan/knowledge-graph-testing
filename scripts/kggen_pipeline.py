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
import sys
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
            result = kg.generate(text=chunk)
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
    args = parser.parse_args()

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

    results = []
    for i, fp in enumerate(file_list):
        print(f"[{i + 1}/{len(file_list)}]")
        try:
            record = extract_file(kg, str(fp))
        except Exception as exc:
            print(f"  ERROR: {exc}")
            record = {"source_file": str(fp.as_posix()), "error": str(exc)}
        results.append(record)

    # Write output to fixed path per spec
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / OUTPUT_FILENAME
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Summary
    total_entities  = sum(len(r.get("entities",  [])) for r in results)
    total_edges     = sum(len(r.get("edges",     [])) for r in results)
    total_relations = sum(len(r.get("relations", [])) for r in results)
    files_with_triples = sum(
        1 for r in results
        if r.get("edges") or r.get("relations")
    )

    print()
    print("=" * 60)
    print("EXTRACTION COMPLETE")
    print(f"  Files processed:            {len(results)}")
    print(f"  Files with SPO triples:     {files_with_triples} / {len(results)}")
    print(f"  Total entities found:       {total_entities}")
    print(f"  Total edges/triples found:  {total_edges + total_relations}")
    print(f"  Output written to:          {output_path}")
    print()
    print("SUCCESS GATE: >= 1 SPO triple per file, subjects/objects are real code symbols or concepts.")
    print("Compare this output with Step 1 graphify output on the same 10 files.")
    print("=" * 60)


if __name__ == "__main__":
    main()
