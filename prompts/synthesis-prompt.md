# Synthesis Prompt — Offline Semantic Knowledge Graph Extraction

> Paste this prompt verbatim into a capable model (Claude Opus, Gemini 1.5 Pro, GPT-4o, etc.) **after** all research responses have been placed in the `responses/` folder alongside this file. The model should be given access to read all files in that folder.

---

## Your task

You are synthesizing multiple deep research responses into a single authoritative implementation guide. The research responses are in the same folder as this prompt, one file per research agent. Each filename encodes the model that produced it (e.g. `gemini-deep-research.md`, `perplexity.md`, `chatgpt.md`).

Read every file in the `responses/` folder. Then produce a file called `synthesis.md` in the same folder, structured exactly as specified below.

---

## Target system (non-negotiable constraints for implementability rating)

- **GPU:** NVIDIA RTX 5080, 16 GB VRAM
- **RAM:** 64 GB
- **OS:** Windows 11
- **Storage:** NVMe SSD; model weights on a separate drive
- **Runtime:** Ollama (latest), Python 3.11, uv package manager
- **Existing models on disk:** `qwen2.5-coder:7b` (4.7 GB), `qwen2.5-coder:14b` (9 GB)
- **Network:** Internet available for one-time downloads; inference must run fully offline

**Failed approaches (do not recommend these):**
- `qwen2.5-coder:14b` via graphify Ollama backend — follows schema but times out (>10 min/chunk)
- `qwen2.5-coder:7b` via graphify Ollama backend — fast but produces hollow responses; graphify warns model too small for JSON instruction following
- Passing `num_ctx` via API `extra_body` — unreliable; Ollama reloads at 8192

---

## Problem context

graphify (`graphifyy` pip package) sends ~169 Python files + ~22 markdown docs to a local LLM and expects a single complex JSON response per chunk: typed nodes, typed edges, confidence scores, edge provenance (EXTRACTED/INFERRED/AMBIGUOUS), hyperedges, and rationale. AST extraction succeeded (1,597 nodes / 1,608 edges), but semantic/doc extraction produced zero results. The core bottleneck: local models either cannot follow the schema reliably or are too slow to generate the output within reasonable timeouts on consumer hardware.

---

## Output specification — synthesis.md

Produce `synthesis.md` with exactly this structure:

```
---
synthesized_by: <model name and version that is running this prompt>
synthesized_on: <today's date, ISO 8601>
research_sources:
  - model: <model name derived from filename>
    file: <filename>
  - model: <model name derived from filename>
    file: <filename>
  # one entry per file found in responses/
---

# Synthesis — Offline Semantic Knowledge Graph Extraction

## Top 3 Solutions

Ranked by **implementability on the target system** — weight these criteria in order:
1. Fits in 16 GB VRAM (hard requirement)
2. Runs on Windows 11 with Ollama or a compatible local runtime
3. Evidence of real-world success at similar scale (code + doc corpora)
4. Minimal new dependencies beyond what is already installed
5. Time-to-first-result (prefer approaches that yield partial output quickly)

---

### Solution 1 — <short descriptive title>

**Why #1:** <2–3 sentences explaining why this ranks highest on implementability for this specific system>

**What it is:** <concise description of the tool/model/approach>

**Evidence from research:** <summarise what the research agents found — cite specific models, GitHub repos, forum threads, or benchmarks they mentioned. Note which research file(s) surfaced this.>

**Estimated VRAM footprint:** <model size + overhead>

**Estimated time per chunk:** <if reported>

#### Reproduction steps

> Copy-paste ready. Every command must be complete and runnable on Windows 11 in PowerShell or a Git Bash terminal. No placeholders.

1. **Install / download**
   ```
   <exact command>
   ```

2. **Configure**
   ```
   <exact command or file content>
   ```

3. **Run extraction**
   ```
   <exact command>
   ```

4. **Verify output**
   ```
   <exact command or check>
   ```

**Known risks / gotchas:** <specific failure modes to watch for, informed by research findings>

**Fallback if this fails:** <one sentence>

---

### Solution 2 — <short descriptive title>

[Same structure as Solution 1]

---

### Solution 3 — <short descriptive title>

[Same structure as Solution 1]

---

## Discarded candidates

List every other approach mentioned across all research files that did NOT make the top 3, with a one-line reason for exclusion (e.g. "requires 24 GB VRAM", "Windows support unverified", "no evidence of schema-conformant output").

| Candidate | Source file | Reason excluded |
|-----------|-------------|-----------------|
| ...       | ...         | ...             |

---

## Cross-source conflicts

If research agents disagreed on a factual claim (e.g. whether a model fits in 16 GB, whether a tool supports Windows), note the conflict here and state which claim is more credible and why.

---

## Open questions

List anything the research did not resolve that would materially affect which solution to try first. Keep it to genuine unknowns, not general curiosity.
```

---

## Rules for producing synthesis.md

- Do not recommend anything that requires more than 16 GB VRAM without an explicit note that it exceeds the hardware limit.
- Do not recommend the failed approaches listed above.
- All commands in reproduction steps must be complete and literal — no `<your-path-here>` style placeholders. Use the paths and model names from the target system spec above.
- If a research file is vague about a step, say so explicitly rather than inventing a command.
- If multiple research files agree on the same solution, treat that convergence as a positive signal for ranking.
- Prioritize solutions with constrained/guided generation (Outlines, llama.cpp grammar, SGLang, LM Format Enforcer) over raw prompting approaches, as the research prompt specifically asked about them.
- The synthesis.md must be self-contained — a developer who has never read the research files should be able to pick up synthesis.md and implement Solution 1 without needing any other document.
