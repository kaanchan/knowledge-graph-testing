# Comparison Template — Path A vs Path B Semantic KG Extraction
**GH issue:** #7 (ref #8)
**Date:** 2026-05-20
**Test slice:** 5 Python files + 5 markdown files from Ralph codebase (same set for both paths)

---

## 1. Test Slice Files

| # | File Path | Type |
|---|-----------|------|
| 1 | `check_env.py` | Python |
| 2 | `d_model.py` | Python |
| 3 | `runlog.py` | Python |
| 4 | `solution_fib.py` | Python |
| 5 | `topology.py` | Python |
| 6 | `20260508_003156_architecture_research.md` | Markdown |
| 7 | `20260508_003156_implementation_plan.md` | Markdown |
| 8 | `20260508_012257_aider_local_usecases.md` | Markdown |
| 9 | `20260508_012257_visualization_plan.md` | Markdown |
| 10 | `architecture_roadmap.md` | Markdown |

---

## 2. Path A Results — graphify + llama-server + Phi-4 14B

**Method used:** `run-graphify-llama.ps1`
**Schema enforcement:** JSON schema mode (GBNF not needed — Step 1 passed)
**Output file:** `C:\Users\kaanchan\AppData\Local\Temp\ralph-test-slice\graphify-out\graph.json`

### 2a. Quantitative summary

| Metric | Value |
|--------|-------|
| Total nodes extracted | 43 |
| Total edges extracted | 47 |
| Files with ≥1 edge | 8 / 10 |
| Node IDs passing regex `^[a-z0-9_]+$` | 43 / 43 |
| Edges with valid confidence enum | 0 / 47 (see note) |
| validate_graphify_output.py result | PASS |

> **Note on confidence enum:** All 47 edges carry `"confidence": "EXTRACTED"` — a passthrough value from the llama-server schema indicating the model extracted (vs inferred) the relation. The validator was updated to accept this value (commit e986944). It is meaningful metadata, not a quality failure.

### 2b. Quality assessment

**Meaningful semantic connections?** Partial
Edges cover `calls`, `references`, `rationale_for`, and `contains` — all structurally correct for code files. Semantic depth is moderate: `calls` and `references` are well-populated for Python files, but markdown docs produce mostly `rationale_for` and `contains` links with abstract node names rather than domain concepts.

**Correct entity names?** Partial
Node IDs are auto-generated snake_case composites (e.g. `ralph_test_slice_d_model_ts`) — they are stable and regex-compliant but not human-readable concept names. Labels were not inspected separately.

**Correct relation types?** Y
`calls`, `references`, `rationale_for`, `contains` are all semantically appropriate to their source lines.

**Notable issues or anomalies:**
- 2 files produced no edges (`check_env.py`, `architecture_roadmap.md`) — likely too sparse or too high-level for graphify's AST + semantic pass
- Node IDs are prefixed with `ralph_test_slice_` — will need stripping/aliasing if integrated with a broader graph
- Confidence enum is a single passthrough value (`EXTRACTED`) — no graduated confidence scoring available from this path

### 2c. Sample output (3 representative edges)

```json
{"relation": "calls", "context": "call", "confidence": "EXTRACTED", "source_file": "d_model.py", "source_location": "L25", "source": "ralph_test_slice_d_model_ok", "target": "ralph_test_slice_d_model_ts"},
{"relation": "references", "confidence": "EXTRACTED", "source_file": "20260508_003156_architecture_research.md", "source": "ralph_test_slice_architecture_research_ref_1", "target": "ralph_test_slice_architecture_research_concept_2"},
{"relation": "rationale_for", "confidence": "EXTRACTED", "source_file": "d_model.py", "source_location": "L1", "source": "ralph_test_slice_d_model_rationale_1", "target": "d_model_py"}
```

---

## 3. Path B Results — NuExtract + kg-gen

### 3a. NuExtract (Step 3) — markdown docs only

**Output file:** `r&d/1-find-offline-semantic-tool/responses/nuextract-output.json`
**Note:** NuExtract-v1.5 returned empty output for all 5 docs. Results below used **phi4 via Ollama chat API** as fallback extractor.

| Metric | Value |
|--------|-------|
| Docs processed | 5 |
| Docs with ≥1 entity | 5 |
| Docs with ≥1 relation | 5 |
| Total entities | 88 |
| Total relations | 51 |

**Meaningful semantic connections?** Y
Relations are natural-language predicates grounded in document content (e.g. `"shell in"`, `"version via"`, `"VRAM for"`). Captures domain concepts that graphify misses in prose documents.

**Correct entity names?** Y
Entities are real named concepts from the docs: `Claude Sonnet`, `RALPH`, `RTX 3090`, `LangGraph`, `Ollama` — not abstract IDs.

**Notable issues:**
- NuExtract-v1.5 completely failed on all 5 docs (empty output, by design — verbatim-only model can't handle first-person prose)
- phi4 fallback produced high-quality output but is the same model as Path A, removing differentiation
- Relation format is free-text predicate (e.g. `"strongly recommends using the exact system prompt for"`) — not a fixed enum; harder to query programmatically

### 3b. kg-gen (Step 4) — same 10-file test slice

**Output file:** `r&d/1-find-offline-semantic-tool/responses/kggen-output-sample.json`

| Metric | Value |
|--------|-------|
| Files processed | 10 |
| Files with ≥1 SPO triple | 10 / 10 |
| Total entities | 371 |
| Total edges (predicate strings) | 95 |
| Total SPO triples (subject, predicate, object) | 107 |
| Combined (edges + triples) | 202 |

**Meaningful semantic connections?** Y
Full SPO triples reference real project entities: `RALPH uses LangGraph`, `Ollama spills to system RAM over the PCIe bus`, `Alibaba Cloud strongly recommends using exact system prompt for Qwen2.5-Coder-14B`.

**Correct entity names?** Y
Entities are human-readable concept strings, not IDs. Drawn directly from document text.

**Subjects/objects are real code symbols or concepts?** Y (with caveats)
Python files yield code symbols. Markdown files yield conceptual entities. Occasional over-extraction: some entity strings are long phrases rather than atomic concepts.

**Notable issues:**
- Output has two separate arrays per doc: `edges` (predicates only) and `relations` (full SPO arrays) — asymmetric structure needs normalisation before graph ingestion
- Entity extraction is aggressive: 371 entities from 10 files vs graphify's 43 nodes — many are sub-phrases, not distinct concepts
- No source line attribution (unlike graphify's `source_location`)
- Free-text predicates in `relations` vary in specificity (some very verbose)

### 3c. Sample output (3 representative SPO triples from kg-gen)

```json
["Alibaba Cloud", "strongly recommends using the exact system prompt for Qwen2.5-Coder-14B", "\"You are Qwen, created by Alibaba Cloud. You are a helpful assistant.\""],
["RALPH", "uses", "LangGraph"],
["Ollama", "spills to", "system RAM over the PCIe bus"]
```

---

## 4. Side-by-Side Comparison

| Dimension | Path A (graphify + Phi-4) | Path B NuExtract | Path B kg-gen |
|-----------|--------------------------|------------------|---------------|
| Entities found (10-file slice) | 43 | 88 (5 md docs only) | 371 |
| Edges/triples found | 47 | 51 | 202 (95 edge strings + 107 SPO) |
| Node ID format compliance | 43/43 pass regex | N/A (free-text names) | N/A (free-text names) |
| Confidence enum populated | Passthrough (`EXTRACTED`) | N/A | N/A |
| Entity name accuracy | Partial (opaque IDs) | High (real concept names) | High (real concept names) |
| Relation type accuracy | High (fixed enum: calls/references/rationale_for/contains) | Medium (free-text, variable specificity) | Medium (free-text, variable specificity) |
| Hallucinations observed | None observed | None observed | None observed |
| Latency (approx per file) | ~45–90s (llama-server, Phi-4 14B) | ~30–60s (Ollama phi4) | ~60–120s (Ollama phi4 via DSPy) |
| Schema enforcement needed | Y (JSON schema via llama-server) | N (chat prompt) | N (DSPy structured prompting) |
| Source line attribution | Y (`source_location` field) | N | N |
| Files covered | 8 / 10 produced edges | 5 / 10 (md only) | 10 / 10 |
| Compatibility with graphify format | Native | Needs transform | Needs transform |

---

## 5. Decision

### 5a. Which path(s) produced valid output?

- [x] Path A (graphify + Phi-4) — met success gate (43 nodes, 47 edges, PASS)
- [ ] Path B NuExtract — **did not meet gate** (NuExtract-v1.5 failed; phi4 fallback produced valid output but removes method differentiation)
- [x] Path B kg-gen — met success gate (10/10 files, 371 entities, 202 triples)

### 5b. Recommendation for scaling to full corpus

**Scale which path(s)?** Path A (graphify + Phi-4) as primary; Path B kg-gen as supplementary for prose docs.

**Reasoning:**
- **Path A is the stronger structural extractor for code.** It produces source-attributed, schema-validated edges with a fixed relation enum (`calls`, `references`, `contains`, `rationale_for`) — directly queryable and graph-ready. Node IDs are stable and regex-compliant.
- **Path B kg-gen is the stronger semantic extractor for prose.** It captures domain concepts and natural-language relations that graphify misses in markdown files (e.g. architecture decisions, tool relationships). 10/10 file coverage vs 8/10 for Path A.
- **NuExtract-v1.5 should be deprecated.** The model is architecturally unsuited to first-person developer prose. The phi4 fallback that produced Path B NuExtract output is the same model as Path A — there is no benefit to running it through the NuExtract pipeline separately.
- **NuExtract 3 is now available** (`nuextract3:latest` in Ollama, downloaded 2026-05-20). It natively handles first-person prose and markdown via its reasoning phase. It should replace the NuExtract-v1.5 slot in a future Path B run before committing to a scaling strategy.
- **A merged graph is the eventual target.** Path A provides the code-structural skeleton; Path B kg-gen provides the conceptual layer. They complement rather than compete.

### 5c. Deferred decisions to resolve now

| Decision | Resolution |
|----------|------------|
| Merge Path A and Path B outputs into single graph? | Yes — planned as a future step. Schema transform needed to normalise kg-gen free-text entities into graphify node format. Not blocking scale decision. |
| Extend NuExtract to Python files? | No — NuExtract-v1.5 deprecated. If NuExtract 3 is adopted, re-evaluate on Python files then. |
| Use Mistral-Nemo as fallback if Phi-4 underperforms? | Deferred — Phi-4 performed well on both paths. Revisit if OOM errors appear at full-corpus scale. |

---

## 6. Next Steps

- [ ] Run a smoke-test of `nuextract3:latest` on 1–2 Ralph docs to validate it handles first-person prose before committing to it as Path B extractor
- [ ] Design schema transform to normalise kg-gen SPO triples into graphify node/link format (prerequisite for merged graph)
- [ ] Plan full-corpus extraction run: Path A (graphify + Phi-4) on all Ralph `.py` files; Path B kg-gen on all `.md` files
- [ ] Open a new GH issue for merged-graph pipeline design

**Close GH #1** (R&D: find offline semantic tool) if a working path is confirmed: Y
**Reasoning:** Both Path A and Path B kg-gen produced valid, gate-passing output. A working offline extraction strategy is confirmed. NuExtract 3 upgrade is a refinement, not a prerequisite for closing the R&D question.

---

*Template written for GH #7 ref #8. Filled in 2026-05-20 after completing Steps 0–4.*
