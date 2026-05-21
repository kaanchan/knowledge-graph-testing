# Architecture

## Why two paths?

A codebase has two kinds of knowledge:

1. **Structural** — what calls what, what imports what, class hierarchies, file layout. This is unambiguous and can be read directly from the AST without any natural language understanding.
2. **Semantic** — what things *mean*, how concepts relate, what the documentation says, design intent. This requires reading prose and understanding context.

No single model does both well. graphify uses AST parsing for the structural layer (high precision, no hallucinations). NuExtract3 / kg-gen reads text for the semantic layer (captures meaning the AST cannot see). Merging the two gives a graph with both dimensions.

---

## Data flow

```
Codebase
   |
   |-- Path A (code structure) --------------------------> graphify-out/graph.json
   |   graphify + Phi-4 via llama.cpp (port 8080)
   |   AST extraction -> nodes (files, classes, functions)
   |   + edges (calls, imports, contains)
   |   + confidence enum (EXTRACTED | INFERRED | AMBIGUOUS)
   |
   |-- Path B (semantic) --------------------------------> nuextract-output.json
   |   NuExtract3 via Ollama                               kggen-output-sample.json
   |   or kg-gen + Phi-4 via Ollama
   |   Entity/relation extraction from prose and code
   |   -> entities [{name, type}]
   |   -> relations [{subject, predicate, object}]
   |
   v
merge_graphs.py
   |   Loads both outputs
   |   Fuzzy-matches entity names to find fused nodes
   |   (same concept extracted by both paths -> single node, source="merged")
   v
merged-graph.json + merged-graph.html + merged-graph-summary.md
```

---

## Path A — graphify + llama.cpp

**What it does:** graphify walks a directory, parses each source file's AST, and sends structured prompts to Phi-4 to extract a typed graph. The output is a list of nodes (files, classes, functions, rationale strings) and edges (calls, implements, contains, etc.) with a confidence field.

**Why llama.cpp instead of Ollama:** graphify was designed for the OpenAI-compatible REST API. llama-server exposes exactly that API at port 8080. Ollama uses a different protocol by default. graphify is pointed at llama-server via `OLLAMA_BASE_URL=http://127.0.0.1:8080/v1`.

**Why Phi-4:** 14B parameters, strong at code reasoning, 16K context window. Fits in ~9 GB VRAM at Q4_K_M quantisation.

**GBNF grammar (Step 2 fallback):** If Phi-4 produces malformed JSON, a GBNF grammar can be injected per-request in the `grammar` field of the chat completion body. The server start is identical — grammar is a request-level constraint, not a server-level one.

**Validate:** `scripts/validate_graphify_output.py` checks the success gate:
- All node IDs match `^[a-z0-9_]+$`
- Every edge has a valid `confidence` enum value
- Edge count > 0

---

## Path B — NuExtract3 + kg-gen

### NuExtract3 (prose/markdown)

NuExtract3 is a 4B parameter model (Qwen3.5-4B base, fine-tuned by NuMind) specialised for structured extraction. It uses a mandatory prompt format:

```
<|input|>
### Template:
{"entities": [...], "relations": [...]}
### Text:
<document text>

<|output|>
```

Ollama's `format=` parameter (constrained decoding) ensures the output is always valid JSON matching the schema, even if the model would otherwise produce incomplete output.

**Why think=False:** NuExtract3 is built on a Qwen3 reasoning model that defaults to chain-of-thought. `think=False` suppresses the reasoning scratchpad and returns only the extraction result.

**Sliding window:** Documents larger than 4,000 tokens are split into overlapping chunks (128-token overlap) to avoid context truncation.

**NuExtract-v1.5 issues (historical):** The predecessor model silently returned empty output on first-person prose ("I have implemented...") and markdown with `###` headers (which collided with the prompt structure's `### Template:` delimiter). NuExtract3 does not have these issues. See `r&d/9-nuextract-v1.5-issues/` for the full investigation.

### kg-gen (code/config files)

kg-gen uses DSPy internally and calls Phi-4 via LiteLLM (`ollama_chat/phi4`) to extract Subject → Predicate → Object triples. It is better suited to code and config files than NuExtract3, which is optimised for natural language prose.

---

## Unified dispatcher

`dispatch_pipeline.py` combines both Path B extractors into a single tool that:

1. **Classifies** every file by extension into: `prose`, `code`, `config`, `skip`, or `unknown`
2. **Routes** prose to NuExtract3 and code/config to Phi-4/kg-gen as primary models
3. **Falls back** to the other model if the primary returns empty output or raises an error
4. **Resumes** automatically — already-processed files are skipped unless `--force` is given
5. **Unloads** both models from GPU memory cleanly on completion or Ctrl+C

File classification covers 70+ extensions across all major language ecosystems (Python, JS/TS, JVM, C family, .NET, systems languages, scripting, query, configuration formats).

---

## Merge strategy

`merge_graphs.py` loads both graph formats and applies fuzzy entity matching to find nodes that appear in both:

- A graphify node's `id` is derived from its file path + symbol name (e.g. `src_main_py`)
- A nuextract node's `id` is slugified from the entity name (e.g. `main_py`)
- If a nuextract entity name matches a graphify node label (case-insensitive, after stripping punctuation), they are fused into a single node with `source="merged"`

Unfused nodes from each path remain as separate nodes, giving the "satellite" clusters visible in the HTML visualisation — isolated documentation concepts or code symbols that only one extractor captured.

---

## Ignore system

All three pipeline scripts share `extract_config.py`. The ignore system runs as a **pre-scan pass** before any files are walked, building an `IgnoreSpec` object that answers `spec.match(path) -> bool` for any path.

Two layers, applied in order:

1. **Directory-name set** (fast, no I/O) — if any ancestor directory of a file matches an excluded name, the entire subtree is skipped. This catches `node_modules`, `.venv`, etc. with a single set lookup.

2. **Pathspec glob rules** (when `pathspec` is installed) — each `.*ignore` file found under the scan root is parsed into a `(base_dir, PathSpec)` pair. Paths are tested relative to `base_dir`, so a `.gitignore` in `src/` only affects `src/**` — identical to git's own behaviour.

Without `pathspec`, only bare directory names in `.*ignore` files are honoured; glob patterns, negation (`!`), and anchored patterns are ignored.

---

## Interrupt safety

`ollama.chat()` and `httpx` socket reads block Python's GIL, preventing `KeyboardInterrupt` from firing on Windows during a long model call. The fix in all three pipelines:

```python
def _run_with_interrupt(fn, *args, **kwargs):
    # runs fn in a daemon thread, polls every 100ms
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    while t.is_alive():
        if _stop_event.is_set():
            raise KeyboardInterrupt
        t.join(timeout=0.1)
```

On Ctrl+C: the main thread catches `KeyboardInterrupt`, sets `_stop_event`, writes partial results to disk, unloads the model from GPU memory (`keep_alive: 0` via Ollama's `/api/generate`), and exits with code 130 (the standard POSIX exit code for SIGINT).

The PID is printed at startup so the process can always be killed from a second terminal:
```
taskkill /PID 51724 /F
```
