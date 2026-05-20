"""
nuextract_pipeline.py — Path B: NuExtract two-pass extraction on markdown docs.

PREREQUISITES:
    pip install ollama tiktoken

    Pull the model (do NOT use 'nuextract' — that is v1.0, limited to 2K context):
        ollama pull iodose/nuextract-v1.5

    Create a custom Modelfile to extend context to 16K:
        ollama create nuextract-16k -f scripts/nuextract-modelfile.txt

USAGE:
    python scripts/nuextract_pipeline.py --docs-dir <path-to-ralph-docs> --output-dir r&d/1-find-offline-semantic-tool/responses/

    Example:
        python scripts/nuextract_pipeline.py \\
            --docs-dir "C:/Projects/ralph/docs" \\
            --output-dir "r&d/1-find-offline-semantic-tool/responses/"

NOTES:
    - temperature=0.0 is set explicitly on EVERY ollama.generate() call.
      Ollama default is 0.7 which causes hallucinations with extraction models.
    - Sliding window: 4,000 tokens / 128-token overlap for docs > 10K tokens.
    - Output per doc: {source_file, entities: [...], relations: [...]}
    - FLAG FOR REVIEW: After running on markdown, pause and assess quality before
      extending to Python files (scope decision deferred per spec §Step 3).

GH issue: #5 (ref #8)
"""

import json
import argparse
import glob
import os
import sys
from pathlib import Path

try:
    import ollama
except ImportError:
    sys.exit("ERROR: 'ollama' package not installed. Run: pip install ollama")

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    # Fallback: rough word-based estimate (1 token ≈ 0.75 words)
    def count_tokens(text: str) -> int:
        return int(len(text.split()) / 0.75)

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_NAME      = "nuextract-16k"   # created via nuextract-modelfile.txt
WINDOW_TOKENS   = 4_000             # max tokens per sliding window chunk
OVERLAP_TOKENS  = 128               # overlap between adjacent chunks

# NuExtract MANDATORY prompt format (non-chat — do NOT use chat messages API)
PROMPT_TEMPLATE = "<|input|>\n### Template:\n{json_template}\n### Text:\n{input_text}\n\n<|output|>"

# Pass 1: entity extraction
ENTITY_TEMPLATE = json.dumps({"entities": [{"name": "", "type": ""}]}, indent=2)

# Pass 2: relation extraction (augmented with entity names prepended to text)
RELATION_TEMPLATE = json.dumps({"relations": [{"subject": "", "predicate": "", "object": ""}]}, indent=2)


# ── Sliding window chunking ───────────────────────────────────────────────────

def chunk_text(text: str, window: int = WINDOW_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[str]:
    """Split text into overlapping chunks by token count."""
    words = text.split()
    chunks = []
    # Rough char-level split: build chunks until token budget is met
    start = 0
    while start < len(words):
        end = start
        running = 0
        while end < len(words) and running < window:
            running = count_tokens(" ".join(words[start:end + 1]))
            end += 1
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        # Step back by overlap tokens worth of words
        overlap_words = int(overlap / count_tokens(" ".join(words[start:end])) * (end - start))
        overlap_words = max(1, overlap_words)
        start = end - overlap_words
    return chunks


# ── NuExtract call ────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Extract the best JSON object from nuextract-16k output.

    NuExtract-v1.5 emits two blocks: an empty template echo followed by the real
    output in a ```json fence. We prefer the fenced block; fall back to scanning
    for the last well-formed JSON object if no fence is present.
    """
    # Prefer content inside ```json ... ``` (real output follows the echo)
    fence_idx = raw.find("```json")
    if fence_idx != -1:
        after = raw[fence_idx + 7:]
        close = after.find("```")
        candidate = after[:close].strip() if close != -1 else after.strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # No fence — try each `{...}` block using raw_decode (first complete object)
    decoder = json.JSONDecoder()
    pos = 0
    last_obj = None
    while pos < len(raw):
        start = raw.find("{", pos)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw, start)
            last_obj = obj   # keep last successfully-parsed object (richest)
            pos = end
        except json.JSONDecodeError:
            pos = start + 1
    if last_obj is not None:
        return last_obj

    return {"_parse_error": raw}


def _is_chat_model(model_name: str) -> bool:
    """Return True for instruction-following chat models (phi4, llama, mistral…)."""
    chat_prefixes = ("phi4", "phi-4", "llama", "mistral", "qwen", "gemma")
    return any(model_name.lower().startswith(p) for p in chat_prefixes)


def nuextract_call(template: str, text: str) -> dict:
    """
    Call the extraction model with the appropriate API.

    - nuextract-* models: use ollama.generate() with the mandatory non-chat prompt format.
    - Chat models (phi4, llama, …): use ollama.chat() with an instruction prompt.
      This path handles first-person prose and complex markdown that nuextract cannot.
    """
    if _is_chat_model(MODEL_NAME):
        instruction = (
            f"Extract named entities from the text below. "
            f"Return ONLY valid JSON matching this schema (no explanation):\n"
            f"{template}\n\nText:\n{text}"
        )
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": instruction}],
            options={"temperature": 0.0},
        )
        raw = response["message"]["content"].strip()
    else:
        prompt = PROMPT_TEMPLATE.format(json_template=template, input_text=text)
        response = ollama.generate(
            model=MODEL_NAME,
            prompt=prompt,
            options={"temperature": 0.0},   # CRITICAL — Ollama default 0.7 causes hallucinations
        )
        raw = response["response"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json(raw)


# ── Per-document extraction ───────────────────────────────────────────────────

def _normalise_text(text: str) -> str:
    """
    Prepare markdown doc text for NuExtract.

    Two transforms are applied:
    1. Strip ATX markdown headers — NuExtract's prompt uses '### Template:' /
       '### Text:' as structural delimiters; markdown '#' headers in the body
       cause the model to misread the prompt structure and emit an empty echo.
    2. De-personalise first-person phrases → third-person. NuExtract was trained
       on Wikipedia/academic prose and silently returns empty templates when the
       text is written in first person ("I have implemented...").
    """
    import re

    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    replacements = [
        (r"\bI have\b", "The author has"),
        (r"\bI've\b",   "The author has"),
        (r"\bI am\b",   "The system is"),
        (r"\bI'm\b",    "The system is"),
        (r"\bI created\b",     "The author created"),
        (r"\bI built\b",       "The author built"),
        (r"\bI implemented\b", "The author implemented"),
        (r"\bI introduced\b",  "The author introduced"),
        (r"\bI added\b",       "The author added"),
        (r"\bI made\b",        "The author made"),
        (r"\bI wrote\b",       "The author wrote"),
        (r"\bI use\b",         "The system uses"),
        (r"\bI used\b",        "The system used"),
        (r"\bI can\b",         "The system can"),
        (r"\bmy\b",            "the"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def extract_document(file_path: str) -> dict:
    """Run two-pass NuExtract extraction on a single document."""
    raw_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    text = _normalise_text(raw_text)
    token_count = count_tokens(text)

    print(f"  Processing: {file_path} (~{token_count} tokens)")

    # Decide whether to use sliding window
    if token_count <= WINDOW_TOKENS:
        chunks = [text]
    else:
        print(f"    -> Sliding window: {WINDOW_TOKENS} tok / {OVERLAP_TOKENS} overlap")
        chunks = chunk_text(text)

    all_entities: list[dict] = []
    all_relations: list[dict] = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    Chunk {i + 1}/{len(chunks)}")

        # ── Pass 1: entity extraction ──────────────────────────────────────
        pass1_result = nuextract_call(ENTITY_TEMPLATE, chunk)
        chunk_entities = pass1_result.get("entities", [])
        # Filter out empty/malformed entities
        chunk_entities = [e for e in chunk_entities if isinstance(e, dict) and e.get("name")]
        all_entities.extend(chunk_entities)

        # ── Pass 2: relation extraction (entities prepended to text) ───────
        entity_names = [e["name"] for e in chunk_entities]
        if entity_names:
            augmented_text = "Entities found: " + ", ".join(entity_names) + "\n\n" + chunk
        else:
            augmented_text = chunk

        pass2_result = nuextract_call(RELATION_TEMPLATE, augmented_text)
        chunk_relations = pass2_result.get("relations", [])
        # Filter out empty/malformed relations
        chunk_relations = [
            r for r in chunk_relations
            if isinstance(r, dict) and r.get("subject") and r.get("predicate") and r.get("object")
        ]
        all_relations.extend(chunk_relations)

    # Deduplicate entities by name (case-insensitive)
    seen_entities: set[str] = set()
    unique_entities = []
    for e in all_entities:
        key = e["name"].lower()
        if key not in seen_entities:
            seen_entities.add(key)
            unique_entities.append(e)

    return {
        "source_file": str(Path(file_path).as_posix()),
        "token_count": token_count,
        "chunks_processed": len(chunks),
        "entities": unique_entities,
        "relations": all_relations,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global MODEL_NAME  # allows --model arg to override the module-level default
    parser = argparse.ArgumentParser(
        description="NuExtract two-pass extraction on markdown docs (Path B, Step 3, GH #5 ref #8)"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="Directory containing markdown files (searched recursively for *.md)"
    )
    parser.add_argument(
        "--output-dir",
        default="r&d/1-find-offline-semantic-tool/responses/",
        help="Directory to write nuextract-output.json"
    )
    parser.add_argument(
        "--model",
        default=MODEL_NAME,
        help=f"Ollama model name (default: {MODEL_NAME})"
    )
    args = parser.parse_args()
    MODEL_NAME = args.model

    # Discover markdown files
    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        sys.exit(f"ERROR: docs directory not found: {docs_dir}")

    md_files = sorted(docs_dir.rglob("*.md"))
    if not md_files:
        sys.exit(f"ERROR: No .md files found under: {docs_dir}")

    print(f"Found {len(md_files)} markdown file(s) under {docs_dir}")
    print(f"Model: {MODEL_NAME}")
    print()

    # Run extraction
    results = []
    for i, fp in enumerate(md_files):
        print(f"[{i + 1}/{len(md_files)}]")
        try:
            record = extract_document(str(fp))
        except Exception as exc:
            print(f"    ERROR: {exc}")
            record = {"source_file": str(fp.as_posix()), "error": str(exc)}
        results.append(record)

    # Write output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "nuextract-output.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Summary
    total_entities  = sum(len(r.get("entities", [])) for r in results)
    total_relations = sum(len(r.get("relations", [])) for r in results)
    docs_with_output = sum(
        1 for r in results
        if r.get("entities") and r.get("relations")
    )

    print()
    print("=" * 60)
    print("EXTRACTION COMPLETE")
    print(f"  Docs processed:       {len(results)}")
    print(f"  Docs with output:     {docs_with_output} / {len(results)}")
    print(f"  Total entities found: {total_entities}")
    print(f"  Total relations found:{total_relations}")
    print(f"  Output written to:    {output_path}")
    print()
    print("FLAG FOR REVIEW: Inspect output before deciding whether to extend to Python files.")
    print("SUCCESS GATE: >= 1 entity + >= 1 relation per doc, no hallucinated entity names.")
    print("=" * 60)


if __name__ == "__main__":
    main()
