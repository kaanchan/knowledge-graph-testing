# Scripts Reference

All Python scripts live in `scripts/`. Run them with `uv run python scripts/<name>.py`.
All PowerShell scripts live in `scripts/`. Run them with `.\scripts\<name>.ps1`.

---

## dispatch_pipeline.py

Unified dispatcher. Classifies every file in a directory by type, routes it to the best model, and falls back to the alternative model if the primary returns empty output or raises an error.

```
uv run python scripts/dispatch_pipeline.py --dir <path> [options]
```

| Flag | Default | Description |
|---|---|---|
| `--dir` | required | Root directory to scan (recursive) |
| `--output-dir` | `r&d/.../responses/` | Where to write `dispatch-output.json` |
| `--dry-run` | off | Show routing plan without running extraction |
| `--model-prose` | `nuextract3` | Ollama model for prose files |
| `--model-code` | `ollama_chat/phi4` | LiteLLM model string for code/config files |
| `--api-base` | `http://localhost:11434` | Ollama API base URL |
| `--no-fallback` | off | If primary fails, record error and continue (no fallback) |
| `--force` | off | Reprocess files already in the output (other records preserved) |
| `--clean` | off | Delete the output file entirely before running (prompts for confirmation) |
| `--yes` | off | Skip confirmation prompt when used with `--clean` |
| `--exclude DIR ...` | none | Extra directory names to skip |
| `--no-gitignore` | off | Do not read `.gitignore` files |
| `--no-defaults` | off | Disable built-in default exclusions |
| `--ignore-path FILE` | none | Path to a custom ignore file |

**File routing:**

| Category | Extensions (sample) | Primary model | Fallback |
|---|---|---|---|
| prose | `.md .txt .rst .adoc .tex` | nuextract3 | phi4 |
| code | `.py .js .ts .go .rs .java .sh .ps1 .sql` | phi4 | nuextract3 |
| config | `.yaml .toml .json .ini .env .xml` | phi4 | nuextract3 |
| skip | `.png .pdf .zip .exe .pyc .lock .gguf` | — | — |
| unknown | anything else | nuextract3 | phi4 |

---

## nuextract_pipeline.py

NuExtract3 two-pass extraction on markdown documents.

```
uv run python scripts/nuextract_pipeline.py --docs-dir <path> [options]
```

| Flag | Default | Description |
|---|---|---|
| `--docs-dir` | required | Directory containing markdown files (recursive `*.md`) |
| `--output-dir` | `r&d/.../responses/` | Where to write `nuextract-output.json` |
| `--model` | `nuextract3` | Ollama model name |
| `--api-base` | `http://localhost:11434` | Ollama API base URL |
| `--force` | off | Reprocess files already in the output (other records preserved) |
| `--clean` | off | Delete the output file entirely before running (prompts for confirmation) |
| `--yes` | off | Skip confirmation prompt when used with `--clean` |
| `--exclude DIR ...` | none | Extra directory names to skip |
| `--no-gitignore` | off | Do not read `.gitignore` files |
| `--no-defaults` | off | Disable built-in default exclusions |
| `--ignore-path FILE` | none | Custom ignore file |

**Notes:**
- Sliding window: 4,000 tokens per chunk, 128-token overlap for large documents
- `repeat_penalty=1.3` is required for NuExtract3 to prevent looping on short input
- `think=False` suppresses Qwen3 chain-of-thought (extraction only)
- Resume is automatic: already-processed files are detected by `source_file` match in existing output

---

## kggen_pipeline.py

kg-gen SPO triple extraction using Phi-4 via LiteLLM/Ollama.

```
uv run python scripts/kggen_pipeline.py --test-slice-dir <path> [options]
# or
uv run python scripts/kggen_pipeline.py --files file1.py file2.md ... [options]
```

| Flag | Default | Description |
|---|---|---|
| `--test-slice-dir` | required* | Directory to walk for supported files |
| `--files` | required* | Explicit list of files to process |
| `--output-dir` | `r&d/.../responses/` | Where to write `kggen-output-sample.json` |
| `--model` | `ollama_chat/phi-4` | LiteLLM model string |
| `--api-base` | `http://localhost:11434` | Ollama API base URL |
| `--force` | off | Reprocess files already in the output (other records preserved) |
| `--clean` | off | Delete the output file entirely before running (prompts for confirmation) |
| `--yes` | off | Skip confirmation prompt when used with `--clean` |
| `--exclude DIR ...` | none | Extra directory names to skip |
| `--no-gitignore` | off | Do not read `.gitignore` files |
| `--no-defaults` | off | Disable built-in default exclusions |
| `--ignore-path FILE` | none | Custom ignore file |

*`--test-slice-dir` and `--files` are mutually exclusive; one is required.

**Supported extensions:** `.py .md .txt .rst`

---

## merge_graphs.py

Merge graphify JSON output with nuextract3 JSON output into a unified graph.

```
uv run python scripts/merge_graphs.py --graphify-json <path> --nuextract-json <path> [--output-dir <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--graphify-json` | required | Path to graphify `graph.json` |
| `--nuextract-json` | required | Path to `nuextract-output.json` |
| `--output-dir` | `r&d/.../responses/` | Where to write merged outputs |
| `--clean` | off | Delete all three output files before running (prompts for confirmation) |
| `--yes` | off | Skip confirmation prompt when used with `--clean` |

**Outputs:**
- `merged-graph.json` — unified graph (nodes + edges + meta)
- `merged-graph.html` — interactive PyVis force-directed visualisation
- `merged-graph-summary.md` — human/AI-readable summary

---

## extract_config.py

Shared ignore/scan configuration module. Not run directly — imported by all three pipeline scripts.

**Public API:**
- `build_ignore_spec(root, respect_gitignore=True, extra_excludes=None, ignore_path=None, no_defaults=False) -> IgnoreSpec`
- `is_binary(path, sample_size=8192) -> bool`
- `clean_output(paths, yes=False) -> bool` — delete one or more output files; prompts unless `yes=True`
- `DEFAULT_EXCLUDE_DIRS: frozenset` — the built-in exclusion list

**`IgnoreSpec` methods:**
- `.match(path) -> bool` — True if path should be excluded
- `.summary() -> str` — human-readable description of active ignore sources

---

## validate_graphify_output.py

Validate graphify JSON output against the Step 1 success gate.

```
uv run python scripts/validate_graphify_output.py --input <path-to-graph.json>
```

**Success gate:**
- All node IDs match `^[a-z0-9_]+$`
- Every edge has `confidence` in `{EXTRACTED, INFERRED, AMBIGUOUS}`
- Edge count > 0

Exits with code 0 on pass, 1 on failure.

---

## start-llama-server.ps1

Start llama.cpp server with Phi-4 14B Q4_K_M on GPU.

```powershell
.\scripts\start-llama-server.ps1 [-ModelPath <path>] [-ServerExe <path>] [-GpuLayers <n>] [-CtxSize <n>] [-Port <n>]
```

| Parameter | Default | Description |
|---|---|---|
| `-ModelPath` | `D:\Models\gguf\phi-4-Q4_K_M.gguf` | Path to GGUF weights |
| `-ServerExe` | `C:\Users\...\bin\llama.cpp\llama-server.exe` | Path to llama-server.exe |
| `-GpuLayers` | `99` | GPU layers (99 = all layers on GPU) |
| `-CtxSize` | `16384` | Context window size in tokens |
| `-Port` | `8080` | TCP port to listen on |

Leave the terminal open — server runs in the foreground. Run `test-endpoint.ps1` in a second terminal to verify.

---

## start-llama-server-grammar.ps1

GBNF grammar-constrained variant. Server startup is **identical** to `start-llama-server.ps1` — grammar is injected per-request, not at server startup. Use `-TestOnly` to test grammar against an already-running server.

```powershell
.\scripts\start-llama-server-grammar.ps1 [-TestOnly]
```

---

## run-graphify-llama.ps1

Run graphify extraction against the running llama-server.

```powershell
.\scripts\run-graphify-llama.ps1 -Directory <path> [options]
```

| Parameter | Default | Description |
|---|---|---|
| `-Directory` | required | Path to codebase to extract |
| `-OllamaBaseUrl` | `http://127.0.0.1:8080/v1` | llama-server base URL |
| `-OllamaModel` | `phi-4` | Model ID (confirm with `test-endpoint.ps1`) |
| `-GraphifyOllamaNumCtx` | `16384` | Context size for graphify |
| `-GraphifyApiTimeout` | `900` | Per-request timeout in seconds |
| `-GraphifyMaxOutputTokens` | `4096` | Max output tokens per request |

**Important:** Run `test-endpoint.ps1` first to confirm the model ID reported by the server, then set `-OllamaModel` to match.

---

## test-endpoint.ps1

Verify llama-server is live and generating text. Prints the model ID to use as `-OllamaModel`.

```powershell
.\scripts\test-endpoint.ps1 [-BaseUrl <url>]
```

Runs two checks: `GET /v1/models` (server health) and `POST /v1/chat/completions` (generation).
