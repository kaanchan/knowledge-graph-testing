"""
nuextract_pipeline.py — Path B: NuExtract two-pass extraction on markdown docs.

PREREQUISITES:
    pip install ollama tiktoken

    Default model: nuextract3 (Qwen3.5-4B, registered in Ollama via Modelfile)
        hf download numind/NuExtract3-GGUF --include '*Q4_K_M*' --local-dir D:/Models/gguf/nuextract3
        ollama create nuextract3 -f scripts/nuextract3-modelfile.txt  (FROM D:/Models/gguf/nuextract3/NuExtract3-Q4_K_M.gguf)

    Legacy fallback: iodose/nuextract-v1.5 (DEPRECATED — fails on first-person prose)

USAGE:
    python scripts/nuextract_pipeline.py --docs-dir <path-to-ralph-docs> --output-dir r&d/1-find-offline-semantic-tool/responses/

    Example:
        python scripts/nuextract_pipeline.py \\
            --docs-dir "C:/Projects/ralph/docs" \\
            --output-dir "r&d/1-find-offline-semantic-tool/responses/"

NOTES:
    - temperature=0.0 on every call; repeat_penalty=1.3 for nuextract3 to prevent looping.
    - nuextract3 uses ollama.chat() + think=False (Qwen3 reasoning model — suppresses chain-of-thought).
    - Sliding window: 4,000 tokens / 128-token overlap for docs > 10K tokens.
    - Output per doc: {source_file, entities: [...], relations: [...]}
    - MARKDOWN ONLY: nuextract3 extracts poorly from Python/code files (loops on low-content input).
      Use graphify + Phi-4 (Path A) for code files.

GH issue: #5 (ref #8)
"""

import json
import argparse
import glob
import logging
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path


# ── Logging ───────────────────────────────────────────────────────────────────

class _CLIFormatter(logging.Formatter):
    """Clean formatter: no prefix for INFO, level label for WARN+, [debug] for DEBUG."""
    _PREFIXES = {
        logging.DEBUG:    "  [debug] ",
        logging.INFO:     "  ",
        logging.WARNING:  "  WARNING: ",
        logging.ERROR:    "  ERROR: ",
        logging.CRITICAL: "  FATAL: ",
    }
    def format(self, record):
        return self._PREFIXES.get(record.levelno, "  ") + record.getMessage()


log = logging.getLogger("nuextract")


def _setup_logging(level: int, log_file: str = None) -> None:
    log.setLevel(level)
    fmt = _CLIFormatter()
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(fmt)
    log.addHandler(h)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)

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

# ── Ctrl+C / interrupt support ────────────────────────────────────────────────
# ollama.chat() blocks on a socket read and prevents KeyboardInterrupt from
# firing. Running each call in a daemon thread and polling every 100ms keeps
# the main thread free to receive signals at all times.

_stop_event = threading.Event()


def _run_with_interrupt(fn, *args, **kwargs):
    """
    Run fn(*args, **kwargs) in a daemon thread.
    Polls every 100ms so the main thread can receive KeyboardInterrupt.
    Raises KeyboardInterrupt immediately if _stop_event is set.
    Re-raises any exception from the worker thread.
    """
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


# ── Shared scan configuration ──────────────────────────────────────────────────
from extract_config import build_ignore_spec, is_binary, clean_output


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
    to run the NuExtract3 extraction model locally.

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
    NuExtract3 Q4_K_M  ~4 GB VRAM  (used by this script)
    Phi-4 Q4_K_M       ~9 GB VRAM  (used by kggen_pipeline.py / Path A)

  To stop Ollama later:
    Press Ctrl+C in the terminal where you ran 'ollama serve'.
    Or: File → Quit in the desktop app.

  To uninstall Ollama:
    Windows: Settings → Apps → Ollama → Uninstall
    macOS:   Move Ollama.app to Trash, then: rm -rf ~/.ollama
{sep}
"""


def _model_not_found_msg(model_name: str, available: list) -> str:
    sep = "=" * 68
    available_str = "\n    ".join(available) if available else "(none pulled yet)"
    return f"""
{sep}
  PREFLIGHT FAILED — Model '{model_name}' is not in Ollama
{sep}

  What is NuExtract3?
    NuExtract3 is a compact (2.7 GB) AI model specialised for extracting
    structured facts from text. Given a document, it identifies:
      - Entities: named concepts, systems, people, components
      - Relations: how those entities connect (e.g. "X depends on Y")
    These become the nodes and edges of your knowledge graph.

    It is based on Qwen3.5-4B and works entirely offline once downloaded.

  How to set it up (one-time, ~2.7 GB download):

    Step 1 — Install the Hugging Face CLI (if not already):
      pip install huggingface_hub

    Step 2 — Download the model weights:
      huggingface-cli download numind/NuExtract3-GGUF \\
        --include "*Q4_K_M*" \\
        --local-dir D:/Models/gguf/nuextract3

    Step 3 — Register the model with Ollama:
      ollama create nuextract3 -f scripts/nuextract3-modelfile.txt

    Step 4 — Confirm it appears:
      ollama list
      (you should see nuextract3:latest)

    Step 5 — Re-run this script.

  Why Q4_K_M?
    This is a 4-bit compressed version. It fits in ~4 GB VRAM and runs
    at a practical speed for batch document processing. If you have less
    VRAM available, Q2_K (~1.9 GB) is also in the same Hugging Face repo.

  Tweaking the model:
    Pass --model <name> to use a different Ollama model, e.g.:
      python scripts/nuextract_pipeline.py --model phi4 --docs-dir ...
    Chat models (phi4, llama, mistral) will use a different prompt path.

  To remove the model later:
    ollama rm nuextract3
    # then delete the weights if you want the disk space back:
    # del "D:\\Models\\gguf\\nuextract3\\*.gguf"

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
    log.info(f"Unloading '{model_name}' from memory...")
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
        log.info("  Unload complete.")
    except Exception as exc:
        log.warning(f"could not unload model: {exc}")


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
    total_relations = sum(len(r.get("relations", [])) for r in results)
    docs_with_output = sum(1 for r in results if r.get("entities") and r.get("relations"))
    skipped = total_planned - len(results)
    elapsed = time.monotonic() - start_time

    status = "ABORTED -- Ctrl+C" if aborted else "EXTRACTION COMPLETE"
    sep = "=" * 64

    log.info("")
    log.info(sep)
    log.info(status)
    log.info(sep)
    log.info(f"PID:              {pid}")
    log.info(f"Total time:       {_elapsed_str(elapsed)}")
    log.info(f"Files planned:    {total_planned}")
    completed_line = f"Files completed:  {len(results)}"
    if aborted:
        completed_line += f"  ({skipped} not processed)"
    log.info(completed_line)
    empty_files = [r["source_file"] for r in results
                   if not r.get("entities") and not r.get("relations")]
    log.info(f"Model:            {model_name}")
    log.info(f"  With output:    {docs_with_output} / {len(results)} files")
    if empty_files:
        log.info(f"  Empty output:   {len(empty_files)} file(s) — prose-poor content (tables,")
        log.info(f"                  reference docs). Re-run via dispatch_pipeline.py for")
        log.info(f"                  automatic Phi-4 fallback on these files.")
        for f in empty_files:
            log.info(f"                    {f}")
    log.info(f"Entities found:   {total_entities}")
    log.info(f"Relations found:  {total_relations}")
    log.info(f"Output saved:     {output_path}")
    if aborted:
        log.info("NOTE: Partial output -- re-run to continue (skipped files not saved).")
    log.info("")
    log.debug(json.dumps({
        "event": "extraction_complete",
        "elapsed_s": round(elapsed, 2),
        "model": model_name,
        "files_completed": len(results),
        "files_planned": total_planned,
        "files_with_output": docs_with_output,
        "files_empty": len(empty_files),
        "entities": total_entities,
        "relations": total_relations,
        "aborted": aborted,
    }))
    if results:
        _unload_model(model_name, api_base)
    else:
        log.info("No files processed -- model was not loaded, nothing to unload.")
    log.info(f"PID {pid} exiting cleanly.")
    log.info(sep)


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


def preflight_check(model_name: str, api_base: str = "http://localhost:11434") -> None:
    """Verify Ollama is reachable and the required model is pulled. Exit with guidance if not."""
    import urllib.request
    import urllib.error

    # 1 — Daemon check
    try:
        urllib.request.urlopen(f"{api_base}/api/tags", timeout=3)
    except Exception:
        log.error(_ollama_not_running_msg(api_base))
        sys.exit(1)

    # 2 — Model availability check
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        # Tags endpoint returns names like "nuextract3:latest" — strip the tag
        available = [m["name"].split(":")[0] for m in data.get("models", [])]
        if not any(a == model_name or a.startswith(model_name) for a in available):
            log.error(_model_not_found_msg(model_name, available))
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        log.warning(f"Could not verify model list: {exc} — proceeding anyway")


# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_NAME      = "nuextract3"      # Qwen3.5-4B, registered via Modelfile — see PREREQUISITES
WINDOW_TOKENS   = 4_000             # max tokens per sliding window chunk
OVERLAP_TOKENS  = 128               # overlap between adjacent chunks

# NuExtract MANDATORY prompt format
PROMPT_TEMPLATE = "<|input|>\n### Template:\n{json_template}\n### Text:\n{input_text}\n\n<|output|>"

# nuextract3: single-pass combined template shown to the model in the prompt
COMBINED_TEMPLATE = json.dumps({
    "entities": [{"name": "", "type": ""}],
    "relations": [{"subject": "", "predicate": "", "object": ""}],
}, indent=2)

# nuextract3: JSON Schema passed to Ollama format= for constrained decoding.
# This forces valid, complete JSON output without needing a num_predict cap.
COMBINED_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                },
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

# Legacy two-pass templates (nuextract-16k / phi4 fallback paths)
ENTITY_TEMPLATE   = json.dumps({"entities": [{"name": "", "type": ""}]}, indent=2)
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


def _is_nuextract3(model_name: str) -> bool:
    """Return True for nuextract3 — uses chat API + NuExtract prompt format + think=False."""
    return model_name.lower().startswith("nuextract3")


def _warmup_model(model_name: str) -> None:
    """Send a minimal request to load the model into VRAM before the main loop."""
    log.info(f"Warming up {model_name} (loading into VRAM)...")
    t0 = time.monotonic()
    try:
        _run_with_interrupt(
            ollama.chat,
            model=model_name,
            messages=[{"role": "user", "content": "."}],
            think=False,
            options={"temperature": 0.0, "num_predict": 1},
        )
        elapsed = time.monotonic() - t0
        log.info(f"Model ready ({elapsed:.1f}s)")
        log.debug(f"Warmup latency: {elapsed:.2f}s")
    except Exception as exc:
        log.warning(f"warmup failed ({exc}) — continuing anyway")
    log.info("")


def _is_chat_model(model_name: str) -> bool:
    """Return True for instruction-following chat models (phi4, llama, mistral…)."""
    chat_prefixes = ("phi4", "phi-4", "llama", "mistral", "qwen", "gemma")
    return any(model_name.lower().startswith(p) for p in chat_prefixes)


def nuextract_call(template: str, text: str) -> dict:
    """
    Call the extraction model with the appropriate API.

    - nuextract3: ollama.chat() with NuExtract <|input|> prompt + think=False + repeat_penalty.
      repeat_penalty=1.3 is required — without it, nuextract3 loops on low-content input.
    - Chat models (phi4, llama, …): ollama.chat() with plain instruction prompt.
    - nuextract-16k / legacy: ollama.generate() with mandatory non-chat prompt format.
    """
    if _is_nuextract3(MODEL_NAME):
        prompt = PROMPT_TEMPLATE.format(json_template=template, input_text=text)
        response = _run_with_interrupt(
            ollama.chat,
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            format=COMBINED_SCHEMA,     # constrained decoding — engine closes JSON correctly
            options={"temperature": 0.0},
        )
        raw = response["message"]["content"].strip()
    elif _is_chat_model(MODEL_NAME):
        instruction = (
            f"Extract named entities from the text below. "
            f"Return ONLY valid JSON matching this schema (no explanation):\n"
            f"{template}\n\nText:\n{text}"
        )
        response = _run_with_interrupt(
            ollama.chat,
            model=MODEL_NAME,
            messages=[{"role": "user", "content": instruction}],
            options={"temperature": 0.0},
        )
        raw = response["message"]["content"].strip()
    else:
        prompt = PROMPT_TEMPLATE.format(json_template=template, input_text=text)
        response = _run_with_interrupt(
            ollama.generate,
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
    # nuextract3 handles first-person prose and markdown headers natively;
    # _normalise_text rewriting is only needed for legacy nuextract-v1.5.
    text = raw_text if _is_nuextract3(MODEL_NAME) else _normalise_text(raw_text)
    token_count = count_tokens(text)

    log.info(f"Processing: {file_path} (~{token_count} tokens)")
    log.debug(f"Token count: {token_count} | file: {file_path}")

    # Decide whether to use sliding window
    if token_count <= WINDOW_TOKENS:
        chunks = [text]
    else:
        log.info(f"  Sliding window: {WINDOW_TOKENS} tok / {OVERLAP_TOKENS} overlap")
        log.debug(f"Chunking: {len(chunk_text(text))} chunks estimated")
        chunks = chunk_text(text)

    all_entities: list[dict] = []
    all_relations: list[dict] = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            log.info(f"  Chunk {i + 1}/{len(chunks)}")
            log.debug(f"Chunk {i+1}/{len(chunks)}: ~{count_tokens(chunk)} tokens")

        chunk_t0 = time.monotonic()
        if _is_nuextract3(MODEL_NAME):
            # ── Single-pass: entities + relations in one call ──────────────
            result = nuextract_call(COMBINED_TEMPLATE, chunk)
            chunk_entities = [e for e in result.get("entities", []) if isinstance(e, dict) and e.get("name")]
            chunk_relations = [
                r for r in result.get("relations", [])
                if isinstance(r, dict) and r.get("subject") and r.get("predicate") and r.get("object")
            ]
            all_entities.extend(chunk_entities)
            all_relations.extend(chunk_relations)
        else:
            # ── Two-pass: entity extraction then relation extraction ────────
            pass1_result = nuextract_call(ENTITY_TEMPLATE, chunk)
            chunk_entities = [e for e in pass1_result.get("entities", []) if isinstance(e, dict) and e.get("name")]
            all_entities.extend(chunk_entities)

            entity_names = [e["name"] for e in chunk_entities]
            augmented_text = ("Entities found: " + ", ".join(entity_names) + "\n\n" + chunk) if entity_names else chunk
            pass2_result = nuextract_call(RELATION_TEMPLATE, augmented_text)
            chunk_relations = [
                r for r in pass2_result.get("relations", [])
                if isinstance(r, dict) and r.get("subject") and r.get("predicate") and r.get("object")
            ]
            all_relations.extend(chunk_relations)
        chunk_elapsed = time.monotonic() - chunk_t0
        log.debug(
            f"Chunk {i+1}/{len(chunks)} done: {len(chunk_entities)}e "
            f"{len(chunk_relations)}r in {chunk_elapsed:.1f}s"
        )

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
    parser.add_argument(
        "--api-base",
        default="http://localhost:11434",
        help="Ollama API base URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess files that already appear in the output (preserves other records)"
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Delete the output file entirely before running (prompts for confirmation)"
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompt when used with --clean"
    )
    parser.add_argument(
        "--exclude", nargs="*", default=[],
        metavar="DIR",
        help="Extra directory names to skip (e.g. --exclude tests fixtures)"
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
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "--quiet", action="store_true",
        help="Suppress INFO output — show warnings and errors only"
    )
    log_group.add_argument(
        "--verbose", action="store_true",
        help="Show DEBUG output: per-chunk timing, token counts, structured completion stats"
    )
    parser.add_argument(
        "--log", default=None, metavar="FILE",
        help="Write log output to FILE in addition to stderr"
    )
    args = parser.parse_args()
    MODEL_NAME = args.model

    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    _setup_logging(level, args.log)

    pid = os.getpid()
    start_time = time.monotonic()
    log.info(f"PID {pid}  |  Stop cleanly: Ctrl+C  |  Force kill: taskkill /PID {pid} /F")
    log.info("")

    preflight_check(MODEL_NAME, args.api_base)

    # Discover markdown files
    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        sys.exit(f"ERROR: docs directory not found: {docs_dir}")

    ignore_spec = build_ignore_spec(
        docs_dir,
        respect_gitignore=not args.no_gitignore,
        extra_excludes=args.exclude,
        ignore_path=args.ignore_path,
        no_defaults=args.no_defaults,
    )
    log.info(ignore_spec.summary())
    log.info("")
    md_files = sorted(
        fp for fp in docs_dir.rglob("*.md")
        if not ignore_spec.match(fp) and not is_binary(fp)
    )
    if not md_files:
        sys.exit(f"ERROR: No .md files found under: {docs_dir}")

    log.info(f"Found {len(md_files)} markdown file(s) under {docs_dir}")
    log.info(f"Model: {MODEL_NAME}")
    log.info("")

    # Prepare output path early so partial results can always be saved
    output_dir = Path(args.output_dir)
    output_path = output_dir / "nuextract-output.json"

    # Clean: wipe output before starting if requested
    if args.clean:
        if not clean_output(output_path, yes=args.yes):
            return

    # Resume: skip files already in the output unless --force
    existing_results: list = []
    if output_path.exists() and not args.force:
        try:
            existing_results = json.loads(output_path.read_text(encoding="utf-8"))
            already_done = {r["source_file"] for r in existing_results if "source_file" in r}
            before = len(md_files)
            md_files = [fp for fp in md_files if str(fp.as_posix()) not in already_done]
            skipped = before - len(md_files)
            if skipped:
                log.info(f"Resume: {skipped} file(s) already processed, {len(md_files)} remaining.")
                log.info("(Use --force to reprocess everything.)")
                log.info("")
        except Exception:
            existing_results = []

    if not md_files:
        log.info("All files already processed. Nothing to do.")
        log.info(f"Output: {output_path}")
        return

    _warmup_model(MODEL_NAME)

    # Run extraction
    aborted = False
    results = []
    recent_times: list = []  # rolling window of last 10 file durations
    try:
        for i, fp in enumerate(md_files):
            log.info(_progress_line(i, len(md_files), recent_times))
            t0 = time.monotonic()
            try:
                record = extract_document(str(fp))
            except Exception as exc:
                log.error(str(exc))
                record = {"source_file": str(fp.as_posix()), "error": str(exc)}
            elapsed = time.monotonic() - t0
            recent_times.append(elapsed)
            if len(recent_times) > 10:
                recent_times.pop(0)
            results.append(record)
            log.debug(
                f"{fp.name}: {elapsed:.1f}s | "
                f"{record.get('token_count', 0)} tok | "
                f"{len(record.get('entities', []))}e "
                f"{len(record.get('relations', []))}r"
            )
    except KeyboardInterrupt:
        _stop_event.set()
        aborted = True
        log.warning("Ctrl+C received -- writing partial results and shutting down...")

    _write_and_report(
        existing_results + results, len(md_files), output_path,
        start_time, pid, aborted, MODEL_NAME, args.api_base,
    )

    if not aborted:
        log.info("")
        log.info("FLAG FOR REVIEW: Inspect output before deciding whether to extend to Python files.")
        log.info("SUCCESS GATE: >= 1 entity + >= 1 relation per doc, no hallucinated entity names.")

    if aborted:
        sys.exit(130)  # standard exit code for Ctrl+C (128 + SIGINT=2)


if __name__ == "__main__":
    main()
