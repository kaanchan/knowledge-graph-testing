# Comparison Template — Path A vs Path B Semantic KG Extraction
**GH issue:** #7 (ref #8)
**Date:** [fill in]
**Test slice:** 5 Python files + 5 markdown files from Ralph codebase (same set for both paths)

---

## 1. Test Slice Files

| # | File Path | Type |
|---|-----------|------|
| 1 | [fill in] | Python |
| 2 | [fill in] | Python |
| 3 | [fill in] | Python |
| 4 | [fill in] | Python |
| 5 | [fill in] | Python |
| 6 | [fill in] | Markdown |
| 7 | [fill in] | Markdown |
| 8 | [fill in] | Markdown |
| 9 | [fill in] | Markdown |
| 10 | [fill in] | Markdown |

---

## 2. Path A Results — graphify + llama-server + Phi-4 14B

**Method used:** `run-graphify-llama.ps1`
**Schema enforcement:** JSON schema mode / GBNF fallback (circle one)
**Output file:** [fill in path to graphify output JSON]

### 2a. Quantitative summary

| Metric | Value |
|--------|-------|
| Total nodes extracted | [fill in] |
| Total edges extracted | [fill in] |
| Files with ≥1 edge | [fill in] / 10 |
| Node IDs passing regex `^[a-z0-9_]+$` | [fill in] / [total] |
| Edges with valid confidence enum | [fill in] / [total] |
| validate_graphify_output.py result | PASS / FAIL |

### 2b. Quality assessment

**Meaningful semantic connections?** (Y / N / Partial)
[fill in — example: did it capture "function X calls function Y" correctly?]

**Correct entity names?** (Y / N / Partial)
[fill in — example: do node IDs and labels match actual code symbols?]

**Correct relation types?** (Y / N / Partial)
[fill in — example: are `calls` vs `implements` used appropriately?]

**Notable issues or anomalies:**
[fill in — example: hallucinated nodes, empty labels, wrong file_type assignments]

### 2c. Sample output (paste 1-3 representative edges)

```json
[fill in — paste example edges from the output JSON here]
```

---

## 3. Path B Results — NuExtract + kg-gen

### 3a. NuExtract (Step 3) — markdown docs only

**Output file:** `r&d/1-find-offline-semantic-tool/responses/nuextract-output.json`

| Metric | Value |
|--------|-------|
| Docs processed | [fill in] |
| Docs with ≥1 entity | [fill in] |
| Docs with ≥1 relation | [fill in] |
| Total entities | [fill in] |
| Total relations | [fill in] |

**Meaningful semantic connections?** (Y / N / Partial)
[fill in]

**Correct entity names?** (Y / N / Partial)
[fill in]

**Notable issues:**
[fill in]

### 3b. kg-gen (Step 4) — same 10-file test slice

**Output file:** `r&d/1-find-offline-semantic-tool/responses/kggen-output-sample.json`

| Metric | Value |
|--------|-------|
| Files processed | [fill in] |
| Files with ≥1 SPO triple | [fill in] / 10 |
| Total entities | [fill in] |
| Total edges/triples | [fill in] |

**Meaningful semantic connections?** (Y / N / Partial)
[fill in]

**Correct entity names?** (Y / N / Partial)
[fill in]

**Subjects/objects are real code symbols or concepts?** (Y / N / Partial)
[fill in]

**Notable issues:**
[fill in]

### 3c. Sample output (paste 1-3 representative triples)

```json
[fill in — paste example SPO triples from kggen-output-sample.json here]
```

---

## 4. Side-by-Side Comparison

| Dimension | Path A (graphify + Phi-4) | Path B NuExtract | Path B kg-gen |
|-----------|--------------------------|------------------|---------------|
| Entities found (on 10-file slice) | [fill in] | [fill in] | [fill in] |
| Edges/triples found | [fill in] | [fill in] | [fill in] |
| Node ID format compliance | [fill in] | N/A | N/A |
| Confidence enum populated | [fill in] | N/A | N/A |
| Entity name accuracy | [fill in] | [fill in] | [fill in] |
| Relation type accuracy | [fill in] | [fill in] | [fill in] |
| Hallucinations observed | [fill in] | [fill in] | [fill in] |
| Latency (approx per file) | [fill in] | [fill in] | [fill in] |
| Schema enforcement needed | Y (GBNF) / N | N/A | N/A |
| Compatibility with graphify format | Native | Needs transform | Needs transform |

---

## 5. Decision

### 5a. Which path(s) produced valid output?

- [ ] Path A (graphify + Phi-4) — met success gate
- [ ] Path B NuExtract — met success gate
- [ ] Path B kg-gen — met success gate
- [ ] Neither path met the gate — next steps: [fill in]

### 5b. Recommendation for scaling to full corpus

**Scale which path(s)?**
[fill in — e.g. "Path A only", "Path B kg-gen only", "both in parallel", "neither — revisit model choice"]

**Reasoning:**
[fill in — 2-5 bullet points summarising why]

### 5c. Deferred decisions to resolve now

| Decision | Resolution |
|----------|------------|
| Merge Path A and Path B outputs into single graph? | [fill in] |
| Extend NuExtract to Python files? | [fill in] |
| Use Mistral-Nemo as fallback if Phi-4 underperforms? | [fill in] |

---

## 6. Next Steps

- [ ] [fill in]
- [ ] [fill in]
- [ ] [fill in]

**Close GH #1** (R&D: find offline semantic tool) if a working path is confirmed: Y / N
**Reasoning:** [fill in]

---

*Template written for GH #7 ref #8. Fill in all [fill in] fields after running Steps 1–4.*
