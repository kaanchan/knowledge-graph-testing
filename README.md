# knowledge-graph-testing

An experimental pipeline for extracting offline knowledge graphs from codebases using local AI models — no API keys, no cloud, runs entirely on your GPU.

Two complementary extraction paths are combined into a single merged graph:

- **Path A** — graphify + Phi-4 via llama.cpp: AST-based code structure extraction
- **Path B** — NuExtract3 + kg-gen/Phi-4 via Ollama: semantic entity/relation extraction from prose and code
- **Merge** — `merge_graphs.py` fuses both into a single JSON + interactive HTML visualisation

---

## Hardware requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU VRAM | 10 GB (NuExtract3 only) | 16 GB (both models simultaneously) |
| GPU | RTX 3080 / RX 6800 XT | RTX 3090 / RTX 4080 |
| RAM | 16 GB | 32 GB |
| Disk | 15 GB free | 30 GB free |

Tested on: Windows 11, RTX 3090 24 GB, CUDA 12.x.

---

## Prerequisites

### 1. Python environment

```powershell
pip install uv
uv sync
```

`pathspec` is strongly recommended for full `.gitignore` glob support:
```powershell
uv add pathspec
```

### 2. Ollama (for Path B and dispatch)

Download and install from https://ollama.com/download, then:
```powershell
ollama serve
```

### 3. NuExtract3 model (~2.7 GB, Path B)

```powershell
huggingface-cli download numind/NuExtract3-GGUF --include "*Q4_K_M*" --local-dir D:/Models/gguf/nuextract3
ollama create nuextract3 -f scripts/nuextract3-modelfile.txt
ollama list   # confirm nuextract3:latest appears
```

### 4. Phi-4 via Ollama (~9 GB, Path B kg-gen)

```powershell
ollama pull phi4
```

### 5. llama.cpp + Phi-4 GGUF (Path A only)

Download the latest CUDA 12 Windows binary from https://github.com/ggerganov/llama.cpp/releases.
Extract so `llama-server.exe` lives at `C:\Users\<you>\bin\llama.cpp\llama-server.exe`.

Download `phi-4-Q4_K_M.gguf` from https://huggingface.co/bartowski/phi-4-GGUF
and save to `D:\Models\gguf\phi-4-Q4_K_M.gguf`.

---

## Quickstart

### Option A — NuExtract3 on markdown only (fastest, Ollama only)

```powershell
ollama serve

uv run python scripts/nuextract_pipeline.py --docs-dir "C:\path\to\docs"

# Output: r&d\1-find-offline-semantic-tool\responses\nuextract-output.json
```

### Option B — Full two-path pipeline + merge

```powershell
# Terminal 1
.\scripts\start-llama-server.ps1

# Terminal 2
ollama serve

# Terminal 3 — run in sequence
.\scripts\run-graphify-llama.ps1 -Directory "C:\path\to\codebase"
uv run python scripts/validate_graphify_output.py --input graphify-out\graph.json

uv run python scripts/nuextract_pipeline.py --docs-dir "C:\path\to\docs"

uv run python scripts/merge_graphs.py `
  --graphify-json graphify-out\graph.json `
  --nuextract-json "r&d\1-find-offline-semantic-tool\responses\nuextract-output.json" `
  --output-dir "r&d\1-find-offline-semantic-tool\responses\"

start "r&d\1-find-offline-semantic-tool\responses\merged-graph.html"
```

### Option C — Unified dispatcher (auto-routes all file types)

```powershell
# Preview routing without running extraction
uv run python scripts/dispatch_pipeline.py --dir "C:\path\to\codebase" --dry-run

# Full run
uv run python scripts/dispatch_pipeline.py --dir "C:\path\to\codebase" --output-dir out\
```

---

## Scripts reference

See [docs/scripts-reference.md](docs/scripts-reference.md) for full flag documentation.

| Script | Purpose |
|---|---|
| `scripts/dispatch_pipeline.py` | Unified dispatcher: classifies files, routes to best model, fallback on failure |
| `scripts/nuextract_pipeline.py` | Path B: NuExtract3 entity/relation extraction on markdown |
| `scripts/kggen_pipeline.py` | Path B: kg-gen SPO triple extraction via Phi-4 |
| `scripts/merge_graphs.py` | Merge graphify + nuextract outputs into unified graph |
| `scripts/extract_config.py` | Shared ignore/scan configuration (imported by all pipelines) |
| `scripts/validate_graphify_output.py` | Validate graphify JSON against success gate |
| `scripts/start-llama-server.ps1` | Start llama.cpp server with Phi-4 on GPU |
| `scripts/start-llama-server-grammar.ps1` | GBNF grammar-constrained variant (Step 2 fallback) |
| `scripts/run-graphify-llama.ps1` | Run graphify extraction against running llama-server |
| `scripts/test-endpoint.ps1` | Verify llama-server is live and generating text |

---

## Output format

### nuextract-output.json / kggen-output-sample.json

List of per-file records:
```json
[
  {
    "source_file": "path/to/file.md",
    "token_count": 1243,
    "chunks_processed": 1,
    "entities": [{"name": "TraceManager", "type": "Class"}],
    "relations": [{"subject": "TraceManager", "predicate": "logs to", "object": "runlog.py"}]
  }
]
```

Resume is automatic: re-running skips already-processed files. Use `--force` to reprocess everything.

### merged-graph.json

```json
{
  "meta": {"node_count": 1875, "edge_count": 1917, "sources": ["graphify", "nuextract3"]},
  "nodes": [{"id": "src_main_py", "label": "main.py", "type": "code", "source": "graphify"}],
  "edges": [{"source": "src_main_py", "target": "src_router_py", "relation": "calls"}]
}
```

`merged-graph.html` — interactive force-directed graph, opens in any browser, no server needed.
`merged-graph-summary.md` — human and AI-readable summary: most-connected nodes, fused nodes, sample relations.

---

## File exclusions

All pipelines share a common ignore system (`extract_config.py`):

| Source | Always active? | Notes |
|---|---|---|
| Built-in defaults | Yes (use `--no-defaults` to opt out) | `.git`, `.venv`, `node_modules`, `__pycache__`, `dist`, `.claude`, `responses`, etc. |
| `.gitignore` | Yes (use `--no-gitignore` to skip) | Every `.gitignore` under the scan root, each scoped to its directory |
| `.extractignore` | Always | Same format as `.gitignore`, place anywhere in the tree |
| `--exclude DIR` | When passed | Extra directory names |
| `--ignore-path FILE` | When passed | Custom ignore file |

Binary files (null-byte heuristic, same as git) are always skipped before any model call.
Install `pathspec` for full glob/wildcard/negation support in `.*ignore` files.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for design rationale and data flow.

---

## Research notes

`r&d/` contains the experiment log from the initial tool selection phase:

- `r&d/1-find-offline-semantic-tool/` — comparative research: graphify vs kg-gen vs NuExtract, spec, synthesis, AI responses
- `r&d/9-nuextract-v1.5-issues/` — investigation of NuExtract-v1.5 failures on first-person prose (led to NuExtract3 upgrade)

---

## Known limitations

- **No staleness metadata** — graph nodes carry no timestamps. Re-run with `--force` to refresh stale output.
- **Binary files** — PDFs, images, DOCX require pre-processing (OCR/parsing). These pipelines are plain-text only; graphify plugins handle binary formats.
- **Satellite nodes** — entities from documentation with no matching code entity produce isolated nodes. Low fusion rate (33/1875 in the current run) reflects the two paths seeing different aspects of the codebase — this is expected.
- **NuExtract3 on short code files** — can loop on low-content input. `dispatch_pipeline.py` routes code to Phi-4/kg-gen automatically.
- **GPU contention** — NuExtract3 + Phi-4 simultaneously needs ~13 GB VRAM. Run sequentially on smaller cards, or set `--model-prose` and `--model-code` to the same model.
