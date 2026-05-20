# PENDING TASK — Offline Semantic KG Extraction: Execution

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
