# Spec — Offline Semantic KG Extraction: Two-Path Implementation Experiment

**GH Parent Issue:** #8 — https://github.com/kaanchan/knowledge-graph-testing/issues/8
**Branch:** `issue-8-semantic-kg-extraction`
**Spec created:** 2026-05-20
**Status:** Ready for implementation

---

## Context

graphify AST extraction succeeded (1,597 nodes / 1,608 edges). Semantic/LLM extraction
produced zero results with both qwen2.5-coder:7b and :14b via Ollama. Root cause: graphify's
monolithic one-shot prompt exceeds what consumer local models can do in a single pass.

**Key discovery from source inspection:**
- `OLLAMA_BASE_URL` env var fully redirects graphify to any OpenAI-compatible endpoint
- `GRAPHIFY_OLLAMA_NUM_CTX` overrides context window in the request body (no Modelfile needed)
- graphify's actual schema is simpler than synthesised: no `rationale`, flat node/edge arrays,
  `hyperedges` always empty — meaningfully easier for local models than previously assumed

---

## Agreed approach

Run two parallel experiment paths on the same 10-file test slice (5 Python + 5 markdown,
randomly selected from the Ralph codebase). Do NOT merge outputs — compare independently.

**Path A — graphify + llama-server + Phi-4 14B**
Point graphify at llama-server via OLLAMA_BASE_URL. Enforce schema via JSON schema mode
in response_format. Fallback to GBNF grammar if JSON schema mode produces invalid/empty output.

**Path B — NuExtract two-pass (docs) + kg-gen (full corpus)**
NuExtract-v1.5 restricted to the 22 markdown docs. kg-gen on the full corpus using
Phi-4 or Mistral-Nemo via Ollama. Both paths run independently. Compare outputs.

---

## Key decisions

- Output format: dual independent outputs (graphify format vs kg-gen SPO triples) — no merge yet
- Schema enforcement: JSON schema mode first → GBNF grammar fallback
- NuExtract scope: docs only initially; flag for re-evaluation after first real output review
- Success gate (STRONGEST): valid node IDs in `{stem}_{entity}` format, populated `confidence`
  enum (EXTRACTED/INFERRED/AMBIGUOUS), non-zero edges — not just "something appeared"
- Test slice: 5 Python files + 5 markdown files, randomly selected from Ralph codebase

---

## Hardware / environment

- GPU: NVIDIA RTX 5080, 16 GB VRAM
- RAM: 64 GB, OS: Windows 11
- Runtime: Ollama (latest), Python 3.11, uv package manager
- Models on disk: qwen2.5-coder:7b (4.7 GB), qwen2.5-coder:14b (9 GB)
- Existing AST output: 1,597 nodes / 1,608 edges (scaffold)

---

## graphify actual JSON schema

Source: `llm.py` `_EXTRACTION_SYSTEM`, lines 133–147

```json
{
  "nodes": [
    {
      "id": "stem_entity",
      "label": "Human Readable Name",
      "file_type": "code|document|paper|image|rationale|concept",
      "source_file": "relative/path",
      "source_location": null,
      "source_url": null,
      "captured_at": null,
      "author": null,
      "contributor": null
    }
  ],
  "edges": [
    {
      "source": "node_id",
      "target": "node_id",
      "relation": "calls|implements|references|cites|conceptually_related_to|shares_data_with|semantically_similar_to",
      "confidence": "EXTRACTED|INFERRED|AMBIGUOUS",
      "confidence_score": 1.0,
      "source_file": "relative/path",
      "source_location": null,
      "weight": 1.0
    }
  ],
  "hyperedges": [],
  "input_tokens": 0,
  "output_tokens": 0
}
```

**Node ID rules:** lowercase `[a-z0-9_]` only, format `{stem}_{entity}` where stem = filename
without extension (normalised), entity = symbol name (normalised).

**Confidence definitions:**
- `EXTRACTED` — relationship explicit in source (import, call, citation, reference)
- `INFERRED` — reasonable inference (shared data structure, implied dependency)
- `AMBIGUOUS` — uncertain, flag for review

---

## graphify env vars (from llm.py source)

```powershell
$env:OLLAMA_BASE_URL           = "http://127.0.0.1:8080/v1"   # redirects to llama-server
$env:OLLAMA_MODEL              = "<phi-4-stem>"                # confirm via /v1/models
$env:GRAPHIFY_OLLAMA_NUM_CTX   = "16384"                       # context window in request body
$env:GRAPHIFY_API_TIMEOUT      = "900"                         # 15 min (default 600s)
$env:GRAPHIFY_MAX_OUTPUT_TOKENS = "4096"
```

---

## Implementation steps (sub-issues)

### Step 0 — Validate graphify → llama-server routing (GH #2)

**Branch:** `issue-2-step0-llama-server`
**Files to produce:**
- `scripts/start-llama-server.ps1`
- `scripts/test-endpoint.ps1`

**Tasks:**
- [ ] Download Phi-4 14B Q4_K_M from `bartowski/phi-4-GGUF` on HuggingFace to `D:\models\`
- [ ] Download llama.cpp Windows CUDA binary from github.com/ggerganov/llama.cpp/releases
- [ ] Write `scripts/start-llama-server.ps1`:
  ```powershell
  # starts llama-server with GPU layers, 16K context, port 8080
  .\llama-server.exe -m "D:\models\phi-4-Q4_K_M.gguf" --n-gpu-layers 99 --ctx-size 16384 --port 8080
  ```
- [ ] Write `scripts/test-endpoint.ps1`:
  ```powershell
  # hits /v1/models and a minimal /v1/chat/completions to confirm live
  Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/models"
  ```
- [ ] Confirm OLLAMA_BASE_URL override routes graphify to llama-server
- [ ] Confirm Phi-4 model stem name via /v1/models response

**SUCCESS:** llama-server returns a valid chat completion with Phi-4.

---

### Step 1 — Path A: graphify via llama-server, JSON schema mode (GH #3)

**Branch:** `issue-3-step1-path-a`
**Depends on:** Step 0 (validated routing)
**Files to produce:**
- `scripts/run-graphify-llama.ps1`
- `scripts/graphify-schema.json`
- `scripts/validate_graphify_output.py`

**Tasks:**
- [ ] Write `scripts/graphify-schema.json` — graphify's exact schema (see above)
- [ ] Write `scripts/run-graphify-llama.ps1` — sets all env vars, runs graphify on test slice
- [ ] Confirm llama-server accepts `response_format` with the schema in the request body
- [ ] Randomly select 5 Python + 5 markdown from Ralph codebase as test slice
- [ ] Run on test slice
- [ ] Write `scripts/validate_graphify_output.py`:
  - Check all node IDs match regex `^[a-z0-9_]+$`
  - Check `confidence` field is one of EXTRACTED/INFERRED/AMBIGUOUS
  - Check edge count > 0 per file processed
  - Flag nodes with empty `label`

**SUCCESS gate:** ≥1 edge per file, all node IDs valid, confidence enum populated.
If gate not met → proceed to Step 2.

---

### Step 2 — Path A fallback: GBNF grammar enforcement (GH #4)

**Branch:** `issue-4-step2-gbnf`
**Depends on:** Step 1 (only if Step 1 fails the gate)
**Files to produce:**
- `scripts/graphify.gbnf`
- Update to `scripts/run-graphify-llama.ps1`

**Tasks:**
- [ ] Use llama.cpp `json-schema-to-grammar.py` to compile graphify-schema.json → graphify.gbnf
- [ ] Pass grammar via `grammar` field in llama-server chat completions request body
- [ ] Determine if graphify supports passing `grammar` via extra_body (check llm.py source)
      If not: write a thin FastAPI proxy between graphify and llama-server
- [ ] Re-run same test slice
- [ ] Re-run validate_graphify_output.py

**SUCCESS gate:** Same as Step 1.

---

### Step 3 — Path B: NuExtract two-pass on markdown docs (GH #5)

**Branch:** `issue-5-step3-nuextract`
**Independent of Steps 0–2 (uses Ollama directly)**
**Files to produce:**
- `scripts/nuextract_pipeline.py`
- `scripts/nuextract-modelfile.txt`

**Tasks:**
- [ ] `ollama pull iodose/nuextract-v1.5` (NOT `ollama pull nuextract` — that is v1.0)
- [ ] Write `scripts/nuextract-modelfile.txt` with `PARAMETER num_ctx 16384`
- [ ] Write `scripts/nuextract_pipeline.py`:
  - Non-chat prompt format (required):
    ```
    <|input|>\n### Template:\n{json_template}\n### Text:\n{input_text}\n\n<|output|>
    ```
  - Pass 1 template: `{"entities": [{"name": "", "type": ""}]}`
  - Pass 2 template: `{"relations": [{"subject": "", "predicate": "", "object": ""}]}`
  - Pass 2 augmented text: prepend entity names list before source text
  - `options={"temperature": 0.0}` in every ollama.generate() call
  - Sliding window: 4,000 tokens / 128-token overlap for docs > 10K tokens
  - Output per doc: `{source_file, entities: [...], relations: [...]}`
- [ ] Run on all 22 markdown docs in Ralph codebase
- [ ] FLAG FOR REVIEW: pause after output to assess NuExtract on Python files

**SUCCESS gate:** ≥1 entity + ≥1 relation per doc, no hallucinated entity names.

---

### Step 4 — Path B: kg-gen on test corpus (GH #6)

**Branch:** `issue-6-step4-kggen`
**Independent of Steps 1–3 (uses Ollama directly)**
**Files to produce:**
- `scripts/kggen_pipeline.py`

**Tasks:**
- [ ] `uv add kg-gen` in test venv; run `pip check` to verify no DSPy conflicts
- [ ] Write `scripts/kggen_pipeline.py`:
  ```python
  from kg_gen import KGGen
  kg = KGGen(
      model="ollama_chat/phi-4",   # LiteLLM format — Ollama /api/chat
      temperature=0.0,
      api_base="http://localhost:11434"   # Ollama directly, not llama-server
  )
  # Per-file loop, manual chunking at ~3K tokens
  # Export: {file, entities: [...], edges: [...], relations: [...]}
  ```
- [ ] Run on same 5 Python + 5 markdown test slice (for direct comparison with Step 1)
- [ ] Export to `r&d/1-find-offline-semantic-tool/responses/kggen-output-sample.json`

**SUCCESS gate:** ≥1 SPO triple per file, subjects/objects are real code symbols or concepts.

---

### Step 5 — Compare and decide (GH #7)

**Branch:** `issue-7-step5-compare`
**Depends on:** Steps 1/2 + Steps 3/4
**Files to produce:**
- `r&d/1-find-offline-semantic-tool/comparison-template.md`

**Tasks:**
- [ ] Side-by-side review of Path A and Path B outputs on the same 10 test files
- [ ] Answer per path: meaningful semantic connections? correct entity names? correct relation types?
- [ ] Decide: scale to full corpus? which path(s)?
- [ ] Document decision in `r&d/1-find-offline-semantic-tool/responses/comparison-notes.md`
- [ ] Update `.claude/pm/TODO.md` with next steps
- [ ] Close #1 if a working path is confirmed

**SUCCESS gate:** Written decision with reasoning documented.

---

## Dependency graph and merge order

```
master
  └── issue-8-semantic-kg-extraction (parent branch)
        ├── issue-2-step0-llama-server   ─┐ Phase 1 (parallel)
        ├── issue-5-step3-nuextract      ─┘
        ├── issue-6-step4-kggen          ─┐ Phase 2 (parallel, after Step 0 merged)
        ├── issue-3-step1-path-a         ─┘
        ├── issue-4-step2-gbnf           (Phase 3, conditional on Step 1 failing)
        └── issue-7-step5-compare        (Phase 4, after all above)
```

**Merge sequence into `issue-8`:**
1. `issue-2-step0-llama-server` (no deps)
2. `issue-5-step3-nuextract` (no deps, parallel with above)
3. `issue-6-step4-kggen` (no deps, parallel with above)
4. `issue-3-step1-path-a` (after Step 0 merged)
5. `issue-4-step2-gbnf` (conditional, after Step 1 merged)
6. `issue-7-step5-compare` (after all above)

---

## Constraints

- Do NOT modify graphify source — env var override is sufficient
- All commands run on Windows 11 in PowerShell or Git Bash
- Models must fit in 16 GB VRAM including KV cache
- No merging of Path A and Path B outputs until quality is validated

## Deferred decisions

- Whether to merge graphify and kg-gen outputs into a single graph (deferred until Step 5)
- Whether NuExtract should be extended to Python files (deferred until Step 3 output review)
- Whether to scale Mistral-Nemo as fallback model if Phi-4 underperforms

## Open questions

- Which specific files from the Ralph codebase form the 10-file test slice?
  (random selection — Step 1 agent to select at execution time)
- Does Phi-4's gguf model stem name match what llama-server reports as the model ID?
  (Confirm in Step 0 via /v1/models endpoint)
