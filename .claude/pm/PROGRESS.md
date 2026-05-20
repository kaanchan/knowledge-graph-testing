# PROGRESS

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
