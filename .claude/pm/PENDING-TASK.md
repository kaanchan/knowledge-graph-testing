# PENDING TASK — Knowledge Graph: Full Corpus Run + Graph Utilisation

**Branch:** issue-8-semantic-kg-extraction
**Last commit:** 0841f9a
**Parent GH issue:** #8
**Status:** Step 5 closed (#7). Ready for next phase.

---

## Completed this branch (DO NOT REDO)
- Step 0–4: all extraction paths validated on 10-file test slice
- Step 5: comparison done, nuextract3 upgraded, merge pipeline built
- Merged graph verified by user (143 nodes, 8 fused, 153 edges)
- Key scripts: scripts/nuextract_pipeline.py, scripts/merge_graphs.py

---

## Next session — three tracks to open as GH issues

### Track 1: How to USE the graph to maximum benefit
Open a new GH issue for this. Questions to answer:
- How do we query the merged graph? (JSON traversal, graph DB like NetworkX/Neo4j, SPARQL?)
- How do we feed it to an AI agent? (as context window text, as structured retrieval, as RAG index?)
- What does a "graph-augmented prompt" look like for Ralph development tasks?
- Can another AI agent walk the graph to answer questions about the Ralph codebase?

### Track 2: Full corpus run
- Path A (graphify + Phi-4): 51 Python files in C:\Users\kaanchan\Projects\AI\ralph\
  llama-server must be running: .\scripts\start-llama-server.ps1
- Path B (nuextract3): 204 markdown files in C:\Users\kaanchan\Projects\AI\ralph\
  Ollama must be running: OLLAMA_MODELS=D:\Models\ollama already set
- Merge both outputs with scripts/merge_graphs.py
- Expected scale: ~3,500–5,500 nodes, ~4,500–8,500 edges

### Track 3: GPU optimisation (run extraction while GPU serves other workloads)
- Problem: nuextract3 + Ollama uses the RTX 3090 fully during extraction
- Options to investigate:
  a. Ollama OLLAMA_NUM_GPU=0 or partial GPU layers (--num-gpu N in Modelfile) to cap VRAM usage
  b. llama.cpp --n-gpu-layers N to split model across CPU+GPU, leaving headroom
  c. Batch extraction at night / low-priority process
  d. Quantise further (Q2_K ~1.9GB) to reduce VRAM footprint
- Goal: extraction pipeline runs at ~50% GPU so other inference (phi4, etc.) can run concurrently

---

## Resume instructions
1. Open GH issues for the three tracks above before writing any code
2. Decide which track to start first with user
3. Do NOT merge issue-8-semantic-kg-extraction to master until user confirms

**Branch:** issue-8-semantic-kg-extraction
**Last commit:** e986944 (fix: update validator to match graphify output format refs #3)
**Parent GH issue:** #8
**Sub-issues:** #2 (Step 0), #3 (Step 1), #4 (Step 2), #5 (Step 3), #6 (Step 4), #7 (Step 5)

---

## Current session state (2026-05-20) — Step 5 active

### Environment
- `OLLAMA_MODELS=D:\Models\ollama` set as user-level env var
- llama-server NOT running (not needed for Step 5)
- 10-file test slice: `C:\Users\kaanchan\AppData\Local\Temp\ralph-test-slice\`

### All steps complete
- [x] Step 0 — llama-server + test-endpoint: PASS (refs #2)
- [x] Step 1 — graphify extraction: PASS (43 nodes, 47 edges, 11 communities, refs #3)
- [x] Step 2 — SKIP (Step 1 passed, GBNF fallback not needed)
- [x] Step 3 — NuExtract pipeline: PASS via phi4 fallback (88 entities, 51 relations, refs #5)
      Key finding: NuExtract-v1.5 silently returns empty output on first-person prose + complex markdown
      Research: r&d/9-nuextract-v1.5-issues/ | GH #9
- [x] Step 4 — kg-gen SPO extraction: PASS (371 entities, 202 triples, 10/10 files, refs #6)

### NuExtract 3 download — DONE
- [x] Downloaded numind/NuExtract3-GGUF Q4_K_M (2.7 GB) → D:\Models\gguf\nuextract3\
- [x] Registered as `nuextract3:latest` in Ollama via Modelfile
- [x] Verified: appears in `ollama list`

### Step 5 — Compare and decide (GH #7) — DONE
- [x] comparison-template.md filled with actual results
- [x] nuextract3 downloaded, registered in Ollama, pipeline upgraded
- [x] merge_graphs.py built: graphify + nuextract3 → merged-graph.json/html/summary.md
- [x] Merged graph visualised and confirmed by user (143 nodes, 8 fused, 153 edges)
- [ ] Commit + close GH #7
Sub-tasks:
- [ ] Read Gemini NuExtract research findings (r&d/9-nuextract-v1.5-issues/responses/gemini-NuExtract-v1.5-Documentation-Extraction-Issues.md)
      → Summarize: actual limitations, v2 status, recommended offline alternatives for 16GB VRAM
- [ ] Fill in comparison-template.md with actual results from Steps 1 + 4
      Template: r&d/1-find-offline-semantic-tool/comparison-template.md
      Path A output: C:\Users\kaanchan\AppData\Local\Temp\ralph-test-slice\graphify-out\graph.json
      Path B kg-gen: r&d/1-find-offline-semantic-tool/responses/kggen-output-sample.json
      Path B NuExtract: r&d/1-find-offline-semantic-tool/responses/nuextract-output.json
- [ ] Record scale/no-scale decision in comparison-template.md
- [ ] Commit + close GH #7

---

## Resume instructions

1. Read Gemini findings subagent → summarize to user
2. Fill comparison-template.md with actual numbers
3. Make recommendation → user confirms
4. Commit, close #7, do NOT merge to master yet

---

## Constraints
- Do NOT merge to master until Step 5 complete and user confirms
- All commits reference issue numbers
- Test slice stays at C:\Users\kaanchan\AppData\Local\Temp\ralph-test-slice\
