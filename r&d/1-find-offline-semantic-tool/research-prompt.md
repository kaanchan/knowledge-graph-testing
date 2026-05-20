# Research Prompt — Offline Semantic Knowledge Graph Extraction

> Use this prompt verbatim with deep research AI tools (Perplexity Deep Research, Gemini Deep Research, etc.)

---

I'm trying to perform **offline semantic extraction from a code/document corpus** to build a knowledge graph — specifically extracting named entities, relationships, and structured JSON output from ~22 markdown/text documents and ~169 Python files. I am using a tool called **graphify** (pip package `graphifyy`) which was designed primarily for cloud LLM backends (Claude, Gemini, OpenAI) but also supports an Ollama backend for local inference.

**Hardware:**
- GPU: NVIDIA RTX 5080, 16GB VRAM
- RAM: 64GB
- OS: Windows 11
- Storage: NVMe SSD, models stored on separate drive

**Software stack:**
- Ollama (latest) for local LLM serving
- Models available locally: `qwen2.5-coder:7b` (4.7GB), `qwen2.5-coder:14b` (9GB)
- graphify via `uv tool install graphifyy --with openai`
- Python 3.11, uv package manager

**What graphify's semantic extraction does:**
It sends chunks of files to an LLM with a complex system prompt asking for structured JSON output containing nodes (entities) and edges (relationships) conforming to a strict schema. Each chunk is up to N tokens of file content. It uses the OpenAI-compatible API (`/v1/chat/completions`).

**What we tried and what happened:**

1. **Default run with `qwen2.5-coder:14b`** — Failed immediately: Ollama's default `num_ctx=8192` truncated prompts of 12,000–19,000 tokens silently.

2. **Fixed context window to 32,768** — Created a custom Ollama Modelfile with `PARAMETER num_ctx 32768` baked in (because passing `num_ctx` via API `extra_body` was unreliable — Ollama would reload the model at 8192 whenever a client connected without specifying it). With `--token-budget 12000` and `--max-concurrency 1`, the model received chunks correctly but timed out after 10 minutes generating the JSON output. The model was generating tokens but too slowly to finish.

3. **Switched to `qwen2.5-coder:7b`** — Faster generation (GPU pegged at 92–96% vs 20–40% for 14B), but produced "hollow responses" — generating tokens (sometimes 4,000+) without producing any valid nodes/edges JSON. graphify explicitly warned: *"model too small for JSON instruction following."*

4. **Both models failed** — 7B can't follow the schema reliably; 14B follows it but times out generating the output. AST extraction succeeded (graphify's deterministic code parser — free, offline, no LLM), giving us 1,597 nodes/1,608 edges of code structure. But zero semantic/doc nodes.

**The core problem:**
graphify's extraction prompt is complex — it defines a detailed JSON schema with typed nodes, typed edges, confidence scores, edge provenance (EXTRACTED/INFERRED/AMBIGUOUS), hyperedges, and rationale attributes. Small local models can't reliably follow it. Large enough models to follow it are too slow to generate the output within reasonable timeouts on consumer hardware.

**What I'm looking for:**
Tested, community-verified, open-source solutions that have **actually solved offline semantic extraction from large mixed corpora** (code + docs) on consumer hardware (16GB VRAM). Specifically:

1. Are there **alternative local models** (any architecture/family, must fit in 16GB VRAM) known to reliably produce structured JSON output from complex prompts? Models fine-tuned specifically for structured output or JSON schema following?

2. Are there **alternative tools** beyond graphify that do semantic knowledge graph extraction offline — with different extraction strategies that don't require a single model to generate complex JSON in one shot? (e.g., pipeline approaches, smaller targeted prompts, constrained generation)

3. Is **constrained/guided generation** (e.g., llama.cpp grammar sampling, Outlines, LM Format Enforcer, SGLang) a viable path — forcing the model to emit valid JSON schema-conformant output token-by-token? Has this been successfully applied to knowledge graph extraction at this scale?

4. Any **quantized models** (GGUF Q4/Q5, AWQ, GPTQ) in the 20–34B range that could fit in 16GB and reliably do structured extraction?

Please prioritize solutions with evidence of real-world use (GitHub issues resolved, forum posts with successful runs, benchmarks). I want to avoid going down another path that looks promising but hits the same wall.
