# PROGRESS

## 2026-05-21 — API migration, docs overhaul, test suite, user guide refs #10

- Migrated all 3 pipeline scripts to new `extract_config.py` API (`build_ignore_spec`, `is_binary`, `IgnoreSpec.match`); added `--no-defaults` flag to all three
- Added `pathspec` as soft requirement to `requirements.txt` (fallback documented)
- Ran merge producing 1,875 nodes (33 fused), 1,917 edges from ralph graphify + repo nuextract output
- Rewrote README.md; added `docs/architecture.md`, `docs/scripts-reference.md`
- Built 119-unit test suite + integration stubs: `tests/conftest.py`, `test_extract_config.py`, `test_dispatch_classify.py`, `test_validate_graphify.py`, `test_merge_graphs.py`, `tests/integration/`; pytest.ini with integration marker
- Wrote `docs/guide.md` — 12-section, 895-line comprehensive user guide (install → interpret → troubleshoot)
- All committed and pushed to `issue-10-graph-utilisation`
- Open: pathspec deprecation warning (`gitwildmatch` → `gitignore`), stale nuextract-output.json (needs `--force` rerun), #10 not yet closed

## 2026-05-20 — Step 5 complete + nuextract3 pipeline + merge graph

- Filled comparison-template.md with actual extraction results (Steps 1–4)
- Downloaded numind/NuExtract3-GGUF Q4_K_M → registered as nuextract3:latest in Ollama
- Diagnosed nuextract3 looping: fixed with format=COMBINED_SCHEMA (Ollama structured output) + think=False
- Upgraded nuextract_pipeline.py: single-pass combined template, constrained decoding, no token cap
- Pipeline gate: 5/5 docs, 79 entities, 106 relations on test slice
- Built scripts/merge_graphs.py: merges Path A (graphify) + Path B (nuextract3) into unified graph
- Output: merged-graph.json (143 nodes, 8 fused, 153 edges), merged-graph.html (D3 force viz), merged-graph-summary.md
- User confirmed visualisation working and better than standalone graphify output
- Issues: #5 (nuextract pipeline), #7 (Step 5 compare+decide), #8 (parent), #9 (NuExtract research)

---

## 2026-05-20 — Steps 0,1,3,4 complete; all success gates passed (issue-8-semantic-kg-extraction)

### Steps 3 + 4 completed
- Step 3 (NuExtract docs): phi4 via chat API used as extractor — 5/5 docs, 88 entities, 51 relations
  NuExtract-v1.5 limitation found: silently returns empty template on first-person prose and complex markdown
  Fix applied: pipeline now supports chat models (phi4) via ollama.chat() alongside NuExtract generate()
  Additional fixes: markdown header stripping, first-person de-personalisation added to _normalise_text()
  Also fixed: NuExtract double-JSON response (echo + ```json fence) — _extract_json() handles this
- Step 4 (kg-gen): model name bug fixed (phi-4 → phi4, Ollama tag has no hyphen)
  Result: 10/10 files, 371 entities, 202 SPO triples
- Bug fixed in kggen default model — needs --model ollama_chat/phi4 or fix default in script
- Committed validator fixes: e986944 refs #3

### Remaining
- Step 5: fill comparison-template.md with results from Steps 1 and 4
- NuExtract limitation is a key finding for comparison: nuextract-16k can't handle real-world prose without preprocessing

---

## 2026-05-20 — Execution phase: Steps 0, 1 complete; Steps 3+4 in debug (issue-8-semantic-kg-extraction)

### Environment setup completed
- Migrated all Ollama models from C:\Users\kaanchan\.ollama\models → D:\Models\ollama (~32 GB)
- Set OLLAMA_MODELS=D:\Models\ollama as persistent user-level env var
- Pulled phi4 (9.1 GB) and gemma4:26b (17 GB) into Ollama at D:\Models\ollama
- Confirmed: 9 models total in Ollama (nuextract-16k, iodose/nuextract-v1.5, phi4, gemma4:26b, qwen variants)
- Note: Ollama tray app (ollama app.exe) must be killed and relaunched for env var to apply;
  workaround: start `ollama serve` from a shell that has OLLAMA_MODELS set

### Step 0 — PASS (refs #2)
- llama-server starts with Phi-4 14B Q4_K_M on GPU, port 8080
- /v1/models confirmed model ID: `phi-4-Q4_K_M.gguf`
- test-endpoint.ps1 returns SUCCESS on both /v1/models and /v1/chat/completions

### Step 1 — PASS (refs #3)
- graphify extraction on 10-file Ralph test slice (5 py + 5 md from C:\Users\kaanchan\AppData\Local\Temp\ralph-test-slice)
- Result: 43 nodes, 47 edges, 11 communities
- Bug found + fixed in validate_graphify_output.py: was reading "edges" key, graphify uses "links"
- Added contains + rationale_for to valid relation types (graphify uses these, spec did not list them)
- Committed: e986944 refs #3

### Steps 3+4 — IN PROGRESS
- Step 3 (NuExtract): pipeline runs without error, but returns 0 entities/0 relations for all 5 docs
  Direct model probe works (4 entities from synthetic text). Bug is in pipeline–model interaction.
  Next: direct test with actual doc content to see raw response.
- Step 4 (kg-gen): fails with "model 'phi-4' not found" — Ollama tag is phi4 (no hyphen).
  Fix: re-run with --model ollama_chat/phi4

---

## 2026-05-20 — Orchestrated script scaffolding for #8 (issue-8-semantic-kg-extraction branch)

- Created parent GH issue #8, linked sub-issues #2–#7 as children via comments + task list
- Created spec file: `r&d/1-find-offline-semantic-tool/8-spec-offline-semantic-kg-extraction-two-path-experiment.md`
- Committed all R&D work to master, pushed master and new branch `issue-8-semantic-kg-extraction`
- Orchestrator spawned 6 parallel agents in isolated worktrees (one per sub-issue)
- All 6 branches merged conflict-free into `issue-8-semantic-kg-extraction` in dependency order
- Scripts produced: start-llama-server.ps1, test-endpoint.ps1, run-graphify-llama.ps1,
  graphify-schema.json, validate_graphify_output.py, graphify.gbnf,
  start-llama-server-grammar.ps1, nuextract_pipeline.py, nuextract-modelfile.txt,
  kggen_pipeline.py, comparison-template.md
- Branch pushed to origin — ready for user to execute Step 0

---

## 2026-05-20 — Spec + GH issues for semantic KG extraction implementation

- Critically reviewed SYNTHESIS.md against three deep research reports (Claude, Gemini, DeepSeek)
- Flagged 8 issues: broken download URL, wrong llama-server flag usage, incorrect VRAM math, bad Ollama tag format, wrong env var scoping on Windows, unverifiable model (acervo-extractor-qwen3.5-9b)
- Resolved blocking unknown: graphify's `OLLAMA_BASE_URL` env var fully redirects to any OpenAI-compatible endpoint — no code patch needed
- Discovered graphify's actual JSON schema (simpler than synthesis claimed — no `rationale`, flat arrays, `hyperedges` always empty)
- Confirmed NuExtract-v1.5 Ollama tag: `iodose/nuextract-v1.5`; non-chat prompt format; temperature must be 0.0
- Confirmed kg-gen: `uv add kg-gen`, LiteLLM routing (`ollama_chat/modelname`), built-in two-pass, fixed SPO schema
- Wrote implementation spec to `.claude/pm/PENDING-TASK.md`
- Created GH issues #2–#7 covering all implementation steps
- Removed spurious empty `r/` folder from repo root

---

## 2026-05-19 — Repo setup

- Created `kaanchan/knowledge-graph-testing` on GitHub
- Initialized folder structure: `prompts/`, `scripts/`, `docs/`, `tests/`, `r&d/`, `.claude/pm/`, `.claude/tmp/`
- Opened GH issue #1 for offline semantic tool research
- Created `r&d/<#1>-find-offline-semantic-tool/` with research prompt

