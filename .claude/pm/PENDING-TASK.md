# PENDING TASK — Offline Semantic KG Extraction: Implementation

**Branch:** master
**Last commit:** 78317919d6bbba5099b9f7b905ef01a55be907f2
**Last GH issue:** #1
**Parent GH issue:** #8
**Sub-issues:** #2 (Step 0), #3 (Step 1), #4 (Step 2), #5 (Step 3), #6 (Step 4), #7 (Step 5)

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

Run two parallel experiment paths on the same 10-file test slice (5 Python + 5 markdown from
the Ralph codebase). Do NOT merge outputs — compare independently.

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
- Test slice: 5 Python files + 5 markdown files from the Ralph codebase

---

## Sub-tasks

### Step 0 — Validate graphify → llama-server routing (GH #2)
- [ ] Download Phi-4 14B Q4_K_M from `bartowski/phi-4-GGUF` on HuggingFace to D:\models\
- [ ] Download llama.cpp Windows CUDA binary from github.com/ggerganov/llama.cpp/releases
- [ ] Write `scripts/start-llama-server.ps1` — starts llama-server with correct flags
- [ ] Write `scripts/test-endpoint.ps1` — curls /v1/models and /v1/chat/completions to confirm live
- [ ] Set OLLAMA_BASE_URL=http://127.0.0.1:8080/v1 and run graphify --backend ollama
- [ ] SUCCESS: llama-server returns a valid chat completion response with Phi-4

### Step 1 — Path A: graphify via llama-server, JSON schema mode (GH #3)
- [ ] Write `scripts/run-graphify-llama.ps1` — sets all env vars and runs graphify on test slice
      Required env vars:
        OLLAMA_BASE_URL=http://127.0.0.1:8080/v1
        OLLAMA_MODEL=phi-4
        GRAPHIFY_OLLAMA_NUM_CTX=16384
        GRAPHIFY_API_TIMEOUT=900
        GRAPHIFY_MAX_OUTPUT_TOKENS=4096
- [ ] Copy graphify's exact _EXTRACTION_SYSTEM schema to `scripts/graphify-schema.json`
- [ ] Confirm llama-server accepts response_format with that schema in the request body
- [ ] Run on 5 Python + 5 markdown test files
- [ ] Write `scripts/validate-graphify-output.py` — checks node ID format, confidence enum, edge count
- [ ] SUCCESS: ≥1 edge per file, all node IDs match `[a-z0-9_]+`, confidence enum populated

### Step 2 — Path A fallback: GBNF grammar enforcement (GH #4, only if Step 1 fails)
- [ ] Compile GBNF grammar from graphify's flat schema
- [ ] Pass grammar via request body `grammar` field in llama-server chat completions request
- [ ] Re-run same test slice with grammar active
- [ ] SUCCESS: same gate as Step 1

### Step 3 — Path B: NuExtract two-pass on markdown docs (GH #5)
- [ ] `ollama pull iodose/nuextract-v1.5`
- [ ] Create custom Modelfile with `PARAMETER num_ctx 16384`, reload in Ollama
- [ ] Write `scripts/nuextract_pipeline.py`:
      - Pass 1: entity extraction, template {"entities": [{"name": "", "type": ""}]}
      - Pass 2: SPO relationship extraction using Pass 1 entity list as grounding context
      - temperature=0.0 in every call explicitly
      - Sliding window: 4,000 tokens / 128-token overlap for docs > 10K tokens
      - Output: JSON file per source doc with entities + relations
- [ ] Run on all 22 markdown docs in the Ralph codebase
- [ ] FLAG FOR REVIEW: pause after output to assess NuExtract on Python files
- [ ] SUCCESS: ≥1 entity + ≥1 relation per doc, no hallucinated entity names

### Step 4 — Path B: kg-gen on test corpus (GH #6)
- [ ] `uv add kg-gen`; run `pip check` to catch DSPy version conflicts before proceeding
- [ ] Write `scripts/kggen_pipeline.py`:
      - KGGen(model="ollama_chat/phi-4", temperature=0.0, api_base="http://localhost:11434")
      - Per-file chunk loop; manual text splitting for files > ~3K tokens
      - Aggregate entities/edges/relations sets across all chunks per file
      - Export to JSON: {file, entities: [...], edges: [...], relations: [...]}
- [ ] Run on same 5 Python + 5 markdown test slice (for direct comparison with Step 1)
- [ ] SUCCESS: ≥1 SPO triple per file, subjects/objects are real code symbols or doc concepts

### Step 5 — Compare and decide (GH #7)
- [ ] Side-by-side review of Path A and Path B outputs on the same 10 test files
- [ ] Assess: which produced more meaningful semantic connections?
- [ ] Assess: which output format is more useful downstream?
- [ ] Decide whether to scale to full corpus and which path(s) to use
- [ ] Update TODO.md with next steps

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
- Does Phi-4's gguf model stem name match what llama-server reports as the model ID?
  (Confirm in Step 0 via /v1/models endpoint)
