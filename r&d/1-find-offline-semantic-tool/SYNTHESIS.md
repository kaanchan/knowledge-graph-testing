```yaml
---
synthesized_by: Gemini
synthesized_on: 2026-05-19
research_sources:
  - model: claude
    file: claude-drr-Offline-Semantic-Extraction.md
  - model: gemini
    file: gemini-drr-Offline-Knowledge-Graph-Extraction-Challenges.md
  - model: deepseek
    file: deepseek-drr-offline-semantic-extraction.md
---

```

# Synthesis — Offline Semantic Knowledge Graph Extraction

## Top 3 Solutions

Ranked by **implementability on the target system** — weighting VRAM constraints, native Windows 11 operation, empirical success with complex JSON schemas, and time-to-first-result.

---

### Solution 1 — Native `llama-server` with Strict JSON Schema and Phi-4 14B

**Why #1:** This directly addresses both the "hollow response" and the "timeout" failures without requiring code rewrites. By dropping the Ollama wrapper, you regain ~10% VRAM and 15–30% throughput. By enforcing the schema via `llama-server`'s native GBNF grammar engine, the model is mathematically prohibited from hallucinating text outside the required JSON structure.

**What it is:** Running the extraction through the raw `llama.cpp` server executable using Microsoft's Phi-4 14B model, passing the exact graphify JSON schema to the `--json-schema` argument.

**Evidence from research:** The Claude research notes that LearnOpenCV tested all sub-14B models on Fast-GraphRAG and found Phi-4 14B was the *only* model capable of this exact extraction task locally. Furthermore, JSONSchemaBench proves `llama.cpp`'s backend achieves 97% compliance and is actually *faster* (6.37ms TPOT) than unconstrained generation because the schema masks invalid token probabilities.

**Estimated VRAM footprint:** ~13 GB (9.5 GB for Q4_K_M weights + 3.5 GB for KV context cache).

**Estimated time per chunk:** ~30–60 seconds.

#### Reproduction steps

1. **Install / download**
```powershell
# Download the pre-compiled Windows binary for llama.cpp
Invoke-WebRequest -Uri "https://github.com/ggerganov/llama.cpp/releases/latest/download/llama-bxxxx-bin-win-cuda-cu12.2-x64.zip" -OutFile "llama-cpp.zip"
Expand-Archive -Path "llama-cpp.zip" -DestinationPath ".\llama-cpp"

# Download Phi-4 14B Q4_K_M from HuggingFace
Invoke-WebRequest -Uri "https://huggingface.co/bartowski/phi-4-GGUF/resolve/main/phi-4-Q4_K_M.gguf" -OutFile "D:\models\phi-4-Q4_K_M.gguf"

```


2. **Configure**
```powershell
# Create a schema.json file matching graphify's expected output
Set-Content -Path "schema.json" -Value '{
  "type": "object",
  "properties": {
    "nodes": {"type": "array", "items": {"type": "object"}},
    "edges": {"type": "array", "items": {"type": "object"}},
    "confidence": {"type": "number"},
    "provenance": {"type": "string", "enum": ["EXTRACTED", "INFERRED", "AMBIGUOUS"]},
    "rationale": {"type": "string"}
  },
  "required": ["nodes", "edges", "confidence", "provenance", "rationale"]
}'

```


3. **Run extraction**
```powershell
# Start the server in a separate terminal with the schema enforced
.\llama-cpp\llama-server.exe -m D:\models\phi-4-Q4_K_M.gguf --json-schema schema.json --n-gpu-layers 99 --ctx-size 16384 --port 8080

# In your main terminal, run graphify pointing to the local OpenAI-compatible endpoint
$env:OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
$env:OPENAI_API_KEY="sk-local"
uv run graphify --model "phi-4" --directory .

```


4. **Verify output**
```powershell
# Check the graphify output directory for populated semantic JSON files
Get-ChildItem -Path ".\graphify_output" -Filter "*.json" | Select-String -Pattern '"nodes": \['

```



**Known risks / gotchas:** Graphify's confidence/provenance schema is highly unusual for open-source LLMs. If Phi-4 struggles with the semantic logic of "AMBIGUOUS" edges despite structural compliance, you may get valid JSON that lacks deep conceptual links.
**Fallback if this fails:** Proceed to Solution 2 to keep the Ollama runtime but fix the VRAM spillover.

---

### Solution 2 — Ollama KV Cache Quantization with Mistral-Nemo-12B

**Why #2:** The 10-minute timeouts you experienced with `qwen2.5-coder:14b` were caused by the Key/Value (K/V) context cache expanding in standard F16 precision, pushing the total memory footprint past 16 GB and forcing the RTX 5080 to swap to slow system RAM. Quantizing the KV cache keeps the process strictly on the GPU.

**What it is:** Configuring Windows environment variables to force Ollama to compress its context window (KV Cache) to 8-bit, while utilizing a 12B model known for exceptional native instruction following.

**Evidence from research:** The Gemini research highlights that an F16 32k context cache requires ~6GB of VRAM, guaranteeing a spillover on a 16GB GPU running a 9GB model. Setting `OLLAMA_KV_CACHE_TYPE=q8_0` halves this overhead. Mistral-Nemo-12B is verified by multiple sources (Gemini, Claude) as highly resilient for JSON schema adherence compared to Qwen 7B.

**Estimated VRAM footprint:** ~11.2 GB (8.2 GB weights + 3.0 GB Q8_0 KV cache).

**Estimated time per chunk:** ~45–90 seconds.

#### Reproduction steps

1. **Install / download**
```powershell
# Pull the Mistral-Nemo model
ollama pull mistral-nemo:12b-instruct-2407-q5_K_M

```


2. **Configure**
```powershell
# Stop the running Ollama instance from the system tray, then configure the environment
[System.Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')

# Restart your terminal to apply user variables

```


3. **Run extraction**
```powershell
# Start Ollama service manually to ensure variables are picked up
ollama serve

# In a new terminal, run graphify
uv run graphify --model "mistral-nemo:12b-instruct-2407-q5_K_M" --directory .

```


4. **Verify output**
```powershell
# Monitor VRAM usage during generation to confirm it stays under 16GB
nvidia-smi -l 2

```



**Known risks / gotchas:** Ollama's local handling of `{"type": "json_schema"}` can occasionally conflict with function-calling priorities, sometimes leading to silent retry loops.
**Fallback if this fails:** Pivot to a multi-stage deterministic framework (Solution 3).

---

### Solution 3 — Cognee + BAML with Acervo-Extractor-9B

**Why #3:** Graphify's monolithic prompting strategy—asking an LLM to read code, find entities, establish relations, assign confidence, and output a massive JSON object in one shot—is a documented anti-pattern for local consumer hardware. This solution replaces graphify's semantic engine with a purpose-built offline framework.

**What it is:** Utilizing `Cognee` integrated with the `BAML` structured output DSL, powered by a 9B Qwen model explicitly fine-tuned for extracting knowledge graphs from technical documents.

**Evidence from research:** Gemini research demonstrates that BAML replaces brittle Pydantic parsing with resilient type coercion, allowing smaller models to generate looser text that is deterministically parsed into strict JSON. The `acervo-extractor-qwen3.5-9b` model is fine-tuned explicitly for this task, requiring minimal reasoning overhead. DeepSeek corroborates this architectural shift, recommending `NuExtract` as an alternative.

**Estimated VRAM footprint:** ~5.5 GB (Model) + ~2.0 GB (KV cache) = ~7.5 GB.

**Estimated time per chunk:** ~15–30 seconds.

#### Reproduction steps

1. **Install / download**
```powershell
uv pip install "cognee[baml]"
ollama pull hf.co/SandyVeliz/acervo-extractor-qwen3.5-9b:Q4_K_M

```


2. **Configure**
```powershell
$env:STRUCTURED_OUTPUT_FRAMEWORK="baml"
$env:LLM_PROVIDER="ollama"
$env:LLM_MODEL="hf.co/SandyVeliz/acervo-extractor-qwen3.5-9b:Q4_K_M"

```


3. **Run extraction**
```powershell
# Create an extraction script (extract_kg.py)
Set-Content -Path "extract_kg.py" -Value '
import asyncio
import cognee

async def main():
    await cognee.prune.system_data()
    await cognee.add(".\") # Add your current directory
    await cognee.cognify()

    nodes = await cognee.search.get_all_nodes()
    print(f"Extracted {len(nodes)} nodes successfully.")

asyncio.run(main())
'

uv run python extract_kg.py

```


4. **Verify output**
```powershell
# The script will print the total node count extracted and stored in the local LanceDB/NetworkX instance

```



**Known risks / gotchas:** This abandons the `graphify` ecosystem entirely. You will need to export the resulting graph from Cognee if you rely on downstream graphify visualization tools.
**Fallback if this fails:** Revert to deterministic AST-only extraction and manually map high-level documentation nodes.

---

## Discarded candidates

| Candidate | Source file | Reason excluded |
| --- | --- | --- |
| **Qwen2.5-32B / Command R 35B / Yi-34B** | DeepSeek | Exceeds 16GB VRAM limit; loading a 32B model with a 32k context cache will result in catastrophic system RAM swapping or requires destructive 3-bit quantization. |
| **Outlines (for complex schemas)** | Claude, Gemini | Claude cited JSONSchemaBench showing Outlines collapses to 6% compliance on highly nested/recursive schemas like graphify's. |
| **Codestral-22B** | Gemini | Base weights take ~13.2GB at Q4_K_M, leaving insufficient VRAM for the K/V cache required by document chunks. |
| **WSL2 / Docker vLLM** | Gemini | Introduces a 5-10% performance tax and virtualization overhead on Windows 11; native binaries (`llama-server`) are preferred. |
| **Microsoft GraphRAG (Local)** | Claude | Requires heavy prompt patching and code modification to produce non-empty graphs with sub-32B models. |

---

## Cross-source conflicts

**Conflict 1: The Viability of 32B Models on 16GB VRAM**

* **DeepSeek** suggested running heavily quantized 32B/34B models (Qwen2.5-32B, Yi-34B) on the RTX 5080.
* **Gemini and Claude** explicitly advised against this, noting that while the weights *might* squeeze into 13.7GB using extreme IQ3_XXS quantization, the required K/V cache for processing 169 Python files + docs will immediately trigger an Out-Of-Memory (OOM) error or system RAM swap.
* **Resolution:** Gemini and Claude are correct. DeepSeek's recommendation failed to account for the dynamic VRAM overhead of the context window during batch document processing.

**Conflict 2: The Efficacy of Outlines**

* **Gemini and DeepSeek** recommended Outlines as a top-tier constrained generation backend.
* **Claude** noted that while Outlines is popular, recent benchmarks (JSONSchemaBench) demonstrate it fails structurally on the specific complexity class of graphify's nested schema.
* **Resolution:** Claude's empirical benchmark data directly targeting the schema complexity at hand overrides the generalized recommendations. `llama.cpp`'s GBNF engine is the safer deployment for graphify.

---

## Open questions

* **Endpoint Routing Integration:** Does `graphify` strictly require an Ollama daemon connection, or can it seamlessly target the generic OpenAI-compatible `/v1` endpoint exposed by `llama-server.exe` without internal code modification?
* **Provenance Strictness:** Are the specific edge provenance labels (`EXTRACTED`, `INFERRED`, `AMBIGUOUS`) mandated by graphify strictly necessary for your downstream use case? If not, stripping them from the schema drastically reduces the logic burden on 14B models.