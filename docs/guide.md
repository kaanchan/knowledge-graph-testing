# User Guide

A step-by-step walkthrough of the full pipeline lifecycle — from a blank machine to an interpreted, interactive knowledge graph.

---

## Table of contents

1. [Fresh installation](#1-fresh-installation)
2. [Verifying your setup](#2-verifying-your-setup)
3. [Your first run](#3-your-first-run)
4. [Subsequent runs](#4-subsequent-runs)
5. [Controlling what gets scanned](#5-controlling-what-gets-scanned)
6. [Cleaning and resetting](#6-cleaning-and-resetting)
7. [Creating the graph (graphify — Path A)](#7-creating-the-graph-graphify--path-a)
8. [Merging graphs](#8-merging-graphs)
9. [Interpreting the output](#9-interpreting-the-output)
10. [Troubleshooting](#10-troubleshooting)
11. [Model selection guide](#11-model-selection-guide)
12. [.extractignore cookbook](#12-extractignore-cookbook)

---

## 1. Fresh installation

### 1.1 System check

Before installing anything, confirm your hardware:

```powershell
# GPU and VRAM
nvidia-smi

# Python version (3.10+ required)
python --version

# Free disk space (need ~15 GB minimum)
Get-PSDrive C | Select-Object Used, Free
```

You need at least one of:
- **NuExtract3** path: 10 GB VRAM, ~5 GB disk
- **Full pipeline**: 16 GB VRAM, ~20 GB disk (NuExtract3 + Phi-4 + llama.cpp)

### 1.2 Python environment

Install `uv` (fast Python package manager):

```powershell
pip install uv
```

Clone the repo and install dependencies:

```powershell
git clone https://github.com/kaanchan/knowledge-graph-testing.git
cd knowledge-graph-testing
uv sync
```

Install `pathspec` for full `.gitignore` glob support (strongly recommended):

```powershell
uv add pathspec
```

Without `pathspec`, only bare directory names in `.*ignore` files are honoured — glob patterns like `*.min.js` and negations like `!important.md` are silently ignored.

### 1.3 Install Ollama

Ollama runs NuExtract3 and Phi-4 locally. Download and install from:
**https://ollama.com/download**

Start the server (leave this terminal open):

```powershell
ollama serve
```

Confirm it is running:

```powershell
curl http://localhost:11434/api/tags
# Should return JSON with a "models" list
```

### 1.4 Download NuExtract3 (~2.7 GB)

NuExtract3 handles prose and markdown extraction.

```powershell
# Step 1: install Hugging Face CLI if you don't have it
pip install huggingface_hub

# Step 2: download the Q4_K_M quantised weights (~2.7 GB)
huggingface-cli download numind/NuExtract3-GGUF `
  --include "*Q4_K_M*" `
  --local-dir D:/Models/gguf/nuextract3

# Step 3: register it with Ollama
ollama create nuextract3 -f scripts/nuextract3-modelfile.txt

# Step 4: confirm
ollama list
# nuextract3:latest should appear
```

**Why Q4_K_M?** It is 4-bit compressed — fits in ~4 GB VRAM and runs at practical speed for batch processing. A Q2_K variant (~1.9 GB) is in the same Hugging Face repo if you have less VRAM.

**To remove later:**
```powershell
ollama rm nuextract3
Remove-Item D:\Models\gguf\nuextract3\* -Recurse
```

### 1.5 Download Phi-4 via Ollama (~9 GB)

Phi-4 handles code and config file extraction via kg-gen.

```powershell
ollama pull phi4
# This downloads ~9 GB — leave it running
```

**To remove later:**
```powershell
ollama rm phi4
```

### 1.6 Install llama.cpp (Path A / graphify only)

Skip this if you only plan to use Path B (NuExtract3 + kg-gen).

**Download llama-server.exe:**
1. Go to https://github.com/ggerganov/llama.cpp/releases
2. Download the latest `llama-b...-win-cuda12-x64.zip`
3. Extract so that `llama-server.exe` is at:
   `C:\Users\<you>\bin\llama.cpp\llama-server.exe`

**Download Phi-4 GGUF for llama.cpp:**
1. Go to https://huggingface.co/bartowski/phi-4-GGUF
2. Download `phi-4-Q4_K_M.gguf`
3. Save to `D:\Models\gguf\phi-4-Q4_K_M.gguf`

---

## 2. Verifying your setup

Before your first real run, check that every component responds.

### 2.1 Verify Ollama and models

```powershell
# Is Ollama running?
curl http://localhost:11434/api/tags

# List available models
ollama list
```

Expected output (your list will vary):
```
NAME                ID              SIZE    MODIFIED
nuextract3:latest   abc123...       2.7 GB  2 hours ago
phi4:latest         def456...       9.1 GB  1 day ago
```

### 2.2 Verify Python dependencies

```powershell
uv run python -c "import ollama, tiktoken, kg_gen, pathspec; print('All OK')"
```

If a package is missing, install it:
```powershell
uv add <package-name>
```

### 2.3 Verify llama-server (Path A only)

```powershell
# Terminal 1 — start the server
.\scripts\start-llama-server.ps1

# Terminal 2 — verify it responds
.\scripts\test-endpoint.ps1
```

Expected output includes `SUCCESS: Server is up` and the model ID to use.

### 2.4 Run the unit tests

```powershell
uv run pytest
```

All 119 tests should pass. If any fail, your Python environment has a dependency conflict.

---

## 3. Your first run

### 3.1 Always start with a dry run

The dry run shows you exactly what will be processed and how it will be routed — no extraction happens, no GPU is used.

```powershell
uv run python scripts/dispatch_pipeline.py --dir "C:\path\to\your\codebase" --dry-run
```

Example output:
```
Scanning C:\Projects\myapp ...
  Excluded dir names (28): .claude, .env, .git, ...
  Ignore files applied (2):
    [.gitignore]  C:\Projects\myapp\.gitignore

================================================================
  DRY RUN -- Routing plan (no extraction will run)
================================================================

  prose       12 file(s)  primary -> nuextract3  fallback -> phi4
  code        47 file(s)  primary -> phi4        fallback -> nuextract3
  config       8 file(s)  primary -> phi4        fallback -> nuextract3

  Total files to process: 67

  Sample (first 20 files):
    [prose   ]  docs/overview.md
    [code    ]  src/main.py
    [config  ]  pyproject.toml
    ...
```

Read the dry-run output carefully:
- **Excluded dir names** — the built-in defaults being applied. If a directory you expected to see is missing, it's probably in this list. Use `--no-defaults` to disable.
- **Ignore files applied** — which `.gitignore` / `.extractignore` files were found and are active.
- **Routing plan** — confirm prose goes to nuextract3 and code goes to phi4. If something is mis-categorised, check its extension in `scripts/dispatch_pipeline.py` → `FILE_ROUTING`.
- **Sample files** — scan the list for anything that shouldn't be there.

### 3.2 Run the extraction

Once the dry run looks right:

```powershell
uv run python scripts/dispatch_pipeline.py `
  --dir "C:\path\to\your\codebase" `
  --output-dir "out\"
```

What you will see:
```
  PID 51724  |  Stop cleanly: Ctrl+C  |  Force kill: taskkill /PID 51724 /F

  Excluded dir names (28): ...
  Ignore files applied (2): ...

Starting extraction on 67 file(s).
  Prose model:  nuextract3
  Code model:   ollama_chat/phi4
  Fallback:     enabled

  [0/67]  0%
  [prose   ] overview.md  -> nuextract3
  [1/67]  1%  ~12.3s/file  ETA 13m 42s
  [code    ] main.py  -> phi4
  ...
```

**While it is running:**
- The PID is printed so you can monitor or kill from another terminal
- Each file shows its category and which model was used
- ETA updates using a rolling 10-file window (early estimates are rough; they stabilise after ~10 files)
- If a file triggers the fallback model, it prints `-> primary gave empty output, trying fallback`

**To stop cleanly:** press Ctrl+C. The script writes partial results to disk and unloads the model from GPU memory before exiting. You can resume later from where it stopped.

### 3.3 Understanding the startup summary

Every pipeline prints an ignore summary before scanning:

```
  Excluded dir names (28): .claude, .env, .git, .hg, .idea, .mypy_cache ... (+20 more)
  Ignore files applied (3):
    [.gitignore]    C:\Projects\myapp\.gitignore
    [.gitignore]    C:\Projects\myapp\src\.gitignore
    [.extractignore] C:\Projects\myapp\.extractignore
```

This is your confirmation that the ignore system loaded correctly. If you expected a `.gitignore` to be respected and it doesn't appear here, verify the file path and that `--no-gitignore` is not set.

---

## 4. Subsequent runs

### 4.1 Resume (default behaviour)

If you stop a run mid-way (Ctrl+C, power cut, crash), simply re-run the same command. Already-processed files are detected by their `source_file` path in the existing output JSON and skipped automatically:

```
  Resume: 43 file(s) already processed, 24 remaining.
  (Use --force to reprocess everything.)
```

### 4.2 Force reprocess

To ignore existing output and reprocess everything:

```powershell
uv run python scripts/dispatch_pipeline.py --dir "C:\path\to\codebase" --force
```

Use `--force` when:
- You have updated the codebase significantly since the last run
- You changed the model (`--model-prose` / `--model-code`)
- You suspect the previous run produced low-quality output (check with `--dry-run` first to confirm the file list is correct)

### 4.3 Target a specific subdirectory

You don't have to run on the entire codebase. Point `--dir` at any subdirectory:

```powershell
# Only extract from the docs/ folder
uv run python scripts/nuextract_pipeline.py --docs-dir "C:\myapp\docs"

# Only extract from the src/ folder
uv run python scripts/dispatch_pipeline.py --dir "C:\myapp\src"
```

Results from different directories accumulate in the same output file (resume logic merges them), so you can build up the graph incrementally.

### 4.4 Run on a single file (kggen only)

```powershell
uv run python scripts/kggen_pipeline.py --files "C:\myapp\src\main.py" "C:\myapp\src\router.py"
```

Useful for spot-checking a specific file or re-extracting a file that was previously processed badly.

---

## 5. Controlling what gets scanned

### 5.1 The ignore system — summary

Four sources of exclusion, applied in order:

| Source | CLI flag | Active by default |
|---|---|---|
| Built-in defaults (`.git`, `.venv`, `node_modules`, etc.) | `--no-defaults` to disable | Yes |
| Every `.gitignore` under scan root | `--no-gitignore` to disable | Yes |
| Every `.extractignore` under scan root | always active | Yes |
| Custom file | `--ignore-path <file>` | No |
| Extra dir names | `--exclude DIR ...` | No |

### 5.2 Quick exclusions with --exclude

Add directory names on the fly without editing any file:

```powershell
# Skip the tests/ and fixtures/ directories
uv run python scripts/dispatch_pipeline.py --dir . --exclude tests fixtures
```

`--exclude` adds to the built-in defaults — it does not replace them.

### 5.3 .extractignore — persistent exclusions

Place a `.extractignore` file at the repo root or any subdirectory. It uses identical syntax to `.gitignore`:

```gitignore
# Skip scratch work
scratch/
temp_*/

# Skip generated docs
docs/generated/

# Skip a specific noisy file
src/legacy_monolith.py

# Glob: skip all SQL migration files
migrations/*.sql

# But keep schema.sql
!migrations/schema.sql
```

`.extractignore` files in subdirectories apply only to that subtree (with `pathspec` installed). Without `pathspec`, they apply globally as bare directory names only — install `pathspec` for full glob support.

### 5.4 Disabling built-in defaults

The built-in default exclusion list (`.git`, `.venv`, `node_modules`, `__pycache__`, etc.) exists because these directories almost never contain useful knowledge graph content. But there are edge cases where you want to include them:

```powershell
# Include .venv so you can graph your dependency relationships
uv run python scripts/dispatch_pipeline.py --dir . --no-defaults --exclude .git __pycache__

# Re-add specific exclusions after disabling defaults
uv run python scripts/dispatch_pipeline.py --dir . --no-defaults --exclude .git node_modules dist build
```

### 5.5 Disabling .gitignore

The pipeline respects your `.gitignore` by default. If you want to extract from files that git ignores (e.g. generated files in `dist/` that you want to graph):

```powershell
uv run python scripts/dispatch_pipeline.py --dir . --no-gitignore
```

### 5.6 Custom ignore file

Point to any file with gitignore-format rules:

```powershell
uv run python scripts/dispatch_pipeline.py --dir . --ignore-path "C:\configs\kg-exclusions.txt"
```

The custom file is treated as if it were a `.extractignore` at the scan root.

---

## 6. Cleaning and resetting

There is no `make clean` command. Cleaning is manual and deliberate — to prevent accidental data loss.

### 6.1 Reset extraction output (reprocess from scratch)

The simplest approach — `--force` discards in-memory knowledge of previously processed files and overwrites the output JSON:

```powershell
uv run python scripts/dispatch_pipeline.py --dir . --force
```

### 6.2 Delete output files completely

If you want a truly blank slate:

```powershell
# Remove all extraction outputs
Remove-Item "out\dispatch-output.json" -ErrorAction SilentlyContinue
Remove-Item "r&d\1-find-offline-semantic-tool\responses\nuextract-output.json" -ErrorAction SilentlyContinue
Remove-Item "r&d\1-find-offline-semantic-tool\responses\kggen-output-sample.json" -ErrorAction SilentlyContinue

# Remove the merged graph
Remove-Item "r&d\1-find-offline-semantic-tool\responses\merged-graph.*" -ErrorAction SilentlyContinue
```

After deleting, the next run starts fresh with no resume state.

### 6.3 Unload models from GPU memory

Extraction scripts unload models automatically on clean exit or Ctrl+C. If a script crashed hard (power loss, `taskkill /F`) and a model is still occupying VRAM, unload it manually:

```powershell
# Unload nuextract3
Invoke-RestMethod -Method POST -Uri "http://localhost:11434/api/generate" `
  -ContentType "application/json" `
  -Body '{"model":"nuextract3","prompt":"","keep_alive":0,"stream":false}'

# Unload phi4
Invoke-RestMethod -Method POST -Uri "http://localhost:11434/api/generate" `
  -ContentType "application/json" `
  -Body '{"model":"phi4","prompt":"","keep_alive":0,"stream":false}'
```

Or simply restart Ollama — it will release all VRAM on shutdown.

### 6.4 Stale output records

The output JSON has no timestamps. If you process a file, then change that file significantly, the old record persists in the JSON until you use `--force`. To identify stale records:

```powershell
# Show files in the output JSON whose source path no longer exists
uv run python -c "
import json, pathlib
data = json.load(open('out/dispatch-output.json', encoding='utf-8'))
for r in data:
    p = pathlib.Path(r.get('source_file',''))
    if not p.exists():
        print('STALE:', r['source_file'])
"
```

---

## 7. Creating the graph (graphify — Path A)

Path A extracts code structure — functions, classes, imports, call relationships — directly from the AST. It produces higher-precision edges than prose extraction because it reads the code, not prose about the code.

### 7.1 Start llama-server

```powershell
# Terminal 1 — leave this running
.\scripts\start-llama-server.ps1
```

Default parameters:
- Model: `D:\Models\gguf\phi-4-Q4_K_M.gguf`
- GPU layers: 99 (all on GPU)
- Context: 16,384 tokens
- Port: 8080

Override any of these:
```powershell
.\scripts\start-llama-server.ps1 -CtxSize 8192 -Port 8081 -GpuLayers 40
```

Use fewer GPU layers (`-GpuLayers 20`) to leave VRAM headroom for other workloads.

### 7.2 Confirm the server is live

```powershell
# Terminal 2
.\scripts\test-endpoint.ps1
```

Note the **Model ID** printed — it may differ from `phi-4` (Ollama normalises names). You need this for the next step.

### 7.3 Run graphify extraction

```powershell
.\scripts\run-graphify-llama.ps1 -Directory "C:\path\to\codebase"
```

graphify walks every source file, parses the AST, and asks Phi-4 to extract a typed graph. This is slow (seconds per file) but produces precise, hallucination-free structural edges.

Output is written to `graphify-out\graph.json` in the **target directory** (not the current directory):
```
C:\path\to\codebase\graphify-out\graph.json
```

### 7.4 Validate the output

```powershell
uv run python scripts/validate_graphify_output.py --input "C:\path\to\codebase\graphify-out\graph.json"
```

Success gate:
- All node IDs match `^[a-z0-9_]+$`
- Every edge has `confidence` in `{EXTRACTED, INFERRED, AMBIGUOUS}`
- At least one edge exists

If validation fails with `GBNF grammar fallback` errors, the model produced malformed JSON on some files. See `scripts/start-llama-server-grammar.ps1` for the grammar-constrained fallback.

---

## 8. Merging graphs

Merging combines the structural precision of graphify (Path A) with the semantic richness of NuExtract3/kg-gen (Path B) into a single unified graph.

### 8.1 Prerequisites

You need two input files:
1. `graph.json` from graphify (Path A)
2. `nuextract-output.json` or `dispatch-output.json` from Path B

Both can come from the same codebase or different ones (e.g. graphify on source code + nuextract on the docs folder).

### 8.2 Run the merge

```powershell
uv run python scripts/merge_graphs.py `
  --graphify-json "C:\path\to\codebase\graphify-out\graph.json" `
  --nuextract-json "out\dispatch-output.json" `
  --output-dir "out\"
```

Output:
```
Loading graphify output...
  1597 nodes, 1608 edges
Loading nuextract3 output...
  316 entities, 309 relations
Merging...
  Result: 1875 nodes (33 fused), 1917 edges
```

Three files are written to `--output-dir`:
- `merged-graph.json` — machine-readable unified graph
- `merged-graph.html` — interactive browser visualisation
- `merged-graph-summary.md` — human and AI-readable summary

### 8.3 Open the visualisation

```powershell
start "out\merged-graph.html"
```

No server needed — it is a self-contained HTML file using D3.js loaded from a CDN. Works offline if you have the CDN cached; requires internet on first open.

### 8.4 What the merge does

For each entity extracted by NuExtract3, the merger checks whether a graphify node already represents the same concept:

- If the entity name slugifies to match a graphify node ID (exact or substring), the two are **fused** — the graphify node gains semantic metadata (`label_semantic`, `entity_type`) and its `source` becomes `"merged"`.
- If there is no match, the entity is added as a new `"nuextract3"` node.

Fused nodes (green in the visualisation) are the most valuable — they have both structural edges (what the code does) and semantic edges (what the documentation says about it).

### 8.5 Re-merging after a new extraction run

If you run nuextract again on more files and want to update the graph:

```powershell
# Re-run extraction (resume will only process new files)
uv run python scripts/dispatch_pipeline.py --dir . --output-dir out\

# Re-merge with the updated output
uv run python scripts/merge_graphs.py `
  --graphify-json "C:\path\to\codebase\graphify-out\graph.json" `
  --nuextract-json "out\dispatch-output.json" `
  --output-dir "out\"
```

The merged graph is always recomputed from scratch from both inputs — there is no incremental merge.

---

## 9. Interpreting the output

### 9.1 The interactive graph (merged-graph.html)

**Controls:**
- Scroll to zoom in/out
- Click and drag the background to pan
- Click and drag a node to reposition it (the physics simulation holds the rest)
- Hover a node to see its label, type, source, file, and connection count

**Node colours:**
- Blue — graphify node (code structure: file, class, function, import)
- Orange — nuextract3 node (semantic concept from prose)
- Green — merged node (same concept found by both paths)

**Node size:** proportional to degree (number of connections). Large nodes are architectural hubs — they are the most connected concepts in the codebase.

**Edge colours:**
- Blue edge — code structure relationship (calls, imports, contains, implements)
- Orange edge — semantic relationship (depends on, uses, describes, rationale for)

**What to look for:**
- **Dense core** — the main connected component. This is where your codebase's primary logic lives.
- **Satellite clusters** — small disconnected groups. These are either undocumented subsystems or concepts mentioned only in documentation with no corresponding code symbol.
- **Green (merged) nodes** — concepts that have both code presence and documentation. These are your best-understood components.
- **High-degree orange nodes** — semantic concepts referenced frequently in docs. If they have no code counterpart (not green), they may represent features that are documented but not yet implemented, or documentation that uses different naming than the code.

### 9.2 The summary file (merged-graph-summary.md)

`merged-graph-summary.md` is designed to be pasted into an AI context window. It contains:

- **Overview counts** — total nodes and edges, broken down by source and layer
- **Fused nodes** — the green nodes with their label and entity type. These are the concepts most worth examining.
- **Most connected nodes** — the architectural hubs. These are the best starting points for understanding the codebase.
- **Sample relations** — 15 semantic relations from nuextract3 and 15 structural relations from graphify, showing the flavour of what was extracted.
- **Full node table** — every node with ID, label, type, source, and source file.

### 9.3 The raw JSON (merged-graph.json)

The JSON is straightforward to query with Python:

```python
import json

graph = json.load(open("out/merged-graph.json", encoding="utf-8"))

# All fused (green) nodes
merged = [n for n in graph["nodes"] if n["source"] == "merged"]
print(f"Fused nodes: {len(merged)}")

# Most connected nodes
from collections import Counter
degree = Counter()
for e in graph["edges"]:
    degree[e["source"]] += 1
    degree[e["target"]] += 1

top10 = degree.most_common(10)
node_labels = {n["id"]: n["label"] for n in graph["nodes"]}
for node_id, count in top10:
    print(f"  {count:3d}  {node_labels.get(node_id, node_id)}")

# All semantic edges involving a specific concept
target = "dataloader"
related = [e for e in graph["edges"]
           if e["layer"] == "semantic"
           and (e["source"] == target or e["target"] == target)]
for e in related:
    print(f"  {e['source']} --[{e['relation']}]--> {e['target']}")
```

### 9.4 Using the graph as AI context

`merged-graph-summary.md` is the most useful form for feeding to a language model. Paste it into your prompt with a question:

```
Given the following knowledge graph summary of the codebase:

<paste merged-graph-summary.md content here>

Q: What are the main architectural components and how do they relate?
Q: Which files are most critical (highest connectivity)?
Q: Are there any concepts documented but not present in code?
```

For a targeted query, filter the JSON first and paste only the relevant subgraph — smaller context means faster, cheaper, and often more accurate responses.

### 9.5 What low fusion rate means

The current run shows 33 fused nodes out of 1,875 total — a 1.8% fusion rate. This is expected and not a problem. It reflects that:

- graphify node IDs are derived from file paths + symbol names (`src_main_py`, `src_router_handle_request`)
- nuextract3 entity names are free-form natural language (`Router`, `handle request()`, `the main module`)
- Exact string matching after slugification catches obvious overlaps; fuzzy semantic matching (e.g. embedding similarity) would catch more but is not yet implemented

A low fusion rate means the two layers are largely complementary — they see different things about the same codebase, which is exactly the point of having two paths.

---

## 10. Troubleshooting

### "Ollama is not running"

```
PREFLIGHT FAILED — Ollama is not running
```

Start Ollama: `ollama serve` (leave the terminal open), or open the Ollama desktop app.

### "Model 'nuextract3' is not in Ollama"

```
PREFLIGHT FAILED — Model 'nuextract3' is not in Ollama
```

Run the setup steps from [Section 1.4](#14-download-nuextract3-27-gb). Verify with `ollama list`.

### Script hung after Ctrl+C

The extraction scripts run model calls in a background thread and poll every 100ms. If the script appears frozen after Ctrl+C, wait up to 2 seconds for the current model call to finish, then the shutdown report will print.

If it is truly stuck, use the PID printed at startup:
```powershell
taskkill /PID <pid> /F
```

Then unload models manually (see [Section 6.3](#63-unload-models-from-gpu-memory)).

### Out of VRAM

```
RuntimeError: CUDA out of memory
```

Options:
- Run NuExtract3 and Phi-4 sequentially, not simultaneously
- Use the Q2_K variant of NuExtract3 (~1.9 GB VRAM): download from the same HuggingFace repo
- Reduce llama-server GPU layers: `.\scripts\start-llama-server.ps1 -GpuLayers 20`
- Use `--model-prose nuextract3 --model-code nuextract3` to consolidate to one model

### "pathspec not installed" warning

```
INFO: 'pathspec' not installed.
      Glob patterns in .*ignore files will be ignored.
```

This is a warning, not an error. The pipeline continues with directory-name matching only. Install pathspec to enable full glob support:
```powershell
uv add pathspec
```

### NuExtract3 returns empty entities

This can happen on very short files (< 50 tokens). The dispatch pipeline automatically falls back to Phi-4 in this case. If you see `-> primary gave empty output, trying fallback` frequently, your corpus may have many short files — consider using `--model-prose phi4` to skip NuExtract3 entirely.

### graphify validation fails (node ID regex)

```
FAIL  src/MyClass.py  (2 nodes, 0 edges)
  ERROR: Node[0] id='MyClass': FAILS regex ^[a-z0-9_]+$
```

graphify normalises node IDs to snake_case. If IDs contain uppercase or hyphens, the model is not following the schema correctly. Try the GBNF grammar fallback: `.\scripts\start-llama-server-grammar.ps1 -TestOnly` (with server already running).

---

## 11. Model selection guide

| Use case | Recommended model | Why |
|---|---|---|
| Prose / markdown / docs | nuextract3 | Fine-tuned for structured extraction from natural language. Compact (2.7 GB), fast. |
| Python / JS / Go / code | phi4 via kg-gen | Phi-4 is a reasoning model — better at understanding code structure and logic. |
| Config files (YAML, TOML, JSON) | phi4 via kg-gen | Config files are structured data; phi4 extracts keys and relationships accurately. |
| Limited VRAM (< 6 GB) | nuextract3 (Q2_K) + phi4 sequential | Run one at a time; dispatch handles the routing automatically. |
| Highest quality | phi4 for everything | Larger model, better quality across all file types. Slower and uses more VRAM. |
| Fastest throughput | nuextract3 for everything | Smaller model, fast per-file. Lower quality on code but sufficient for relationship mapping. |

Override the default routing:
```powershell
# Use phi4 for everything (highest quality)
uv run python scripts/dispatch_pipeline.py --dir . `
  --model-prose ollama_chat/phi4 `
  --model-code ollama_chat/phi4

# Use nuextract3 for everything (fastest)
uv run python scripts/dispatch_pipeline.py --dir . `
  --model-prose nuextract3 `
  --model-code nuextract3 `
  --no-fallback
```

---

## 12. .extractignore cookbook

Place `.extractignore` files anywhere in your tree. Each applies to its own directory and below (with `pathspec` installed).

### Skip a directory everywhere it appears

```gitignore
node_modules
vendor
third_party
```

### Skip generated files

```gitignore
# Generated migrations
migrations/

# Compiled protobufs
*_pb2.py
*_pb2_grpc.py

# Minified assets
*.min.js
*.min.css
```

### Skip large data files

```gitignore
*.csv
*.parquet
*.feather
data/
datasets/
```

### Skip test fixtures but keep test code

```gitignore
# Skip fixture data
tests/fixtures/
tests/data/

# But keep the test files themselves
# (don't list tests/ — that would skip all tests)
```

### Include something the .gitignore excludes

If your `.gitignore` excludes `dist/` but you want to graph your compiled output:

```gitignore
# In .extractignore — this has no effect on .gitignore exclusions
# Use --no-gitignore on the CLI instead:
#   python scripts/dispatch_pipeline.py --dir . --no-gitignore
```

The `.extractignore` cannot *include* what `.gitignore` excludes — it can only add further exclusions. To override `.gitignore`, use `--no-gitignore` at the CLI.

### Project-specific example (.extractignore at repo root)

```gitignore
# Development scratch
scratch/
spike/
wip/

# Local environment overrides
*.local.yaml
*.local.env

# Large binary assets
assets/videos/
assets/fonts/

# Auto-generated API clients
src/generated/

# Legacy code being phased out (too noisy for the graph)
src/legacy/
```
