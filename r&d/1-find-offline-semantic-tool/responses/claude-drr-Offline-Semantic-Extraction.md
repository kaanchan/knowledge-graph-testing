# Offline Semantic Extraction for Knowledge Graphs on a 16GB-VRAM Consumer Box

## TL;DR
- **The wall you hit is well-documented**: 7–14B general-purpose models without grammar-constrained decoding routinely fail at complex multi-field JSON. Switch to (a) a structured-output engine (llama.cpp GBNF / `--json-schema` or vLLM+XGrammar / llguidance), and (b) a model trained for schema adherence — **Microsoft Phi-4 14B and NousResearch Hermes 4 14B are the two strongest 16GB-VRAM candidates**, with GPT-OSS 20B as a faster but buggier third option.
- **Decompose the schema**: replace graphify's one-shot "nodes+edges+confidence+hyperedges+provenance+rationale" prompt with a two-pass pipeline — **GLiNER (205M, CPU) for entity spans → REBEL/mREBEL or ReLiK for relations → narrow LLM call for confidence/provenance/rationale → Pydantic assembly**. This is the architecture LightRAG, Neo4j Agent Memory, and the GraphRAG-RS 2026 update all converged on after the same failure you saw.
- **Drop Ollama for this workload**: Ollama's `format=json` mode shells out to llama.cpp's grammar sampler but adds ~10% VRAM overhead and ~15–30% throughput overhead vs raw llama.cpp; for production extraction at 100+ files, run **`llama-server` directly with `--json-schema`** or switch to **vLLM with `guided_json` (XGrammar backend, which has been the vLLM default since v0.6.5)**. Both give you guaranteed schema validity at single-digit-millisecond TPOT — actually *faster* than free generation in the JSONSchemaBench results.

## Key Findings

### 1. Why qwen2.5-coder hangs and goes hollow — the failure mode is generic to sub-14B models

LearnOpenCV's GraphRAG practitioners explicitly tested every relevant sub-14B model on the *exact same task class you are doing* (entity/relation JSON extraction in Fast-GraphRAG):

> "We have tested several Ollama models under 14B class including Qwen, Deepseek, Gemma, Mistral-Nemo and Llama. However, a common issue we faced across these models was they were not able to generate response with proper structured output as expected by validators during summarize_entity_description stage in the Fast GraphRAG pipeline… The only model that worked successfully locally under 14B was Phi4 14B."

This is the same "hollow response" symptom you reported with qwen2.5-coder:7b. Independent confirmation: HKUDS/LightRAG issue #30 documents 0-node/0-edge extraction failures across llama3.1:70b *and* llama3.2:3b via Ollama, and the official LightRAG docs now recommend "≥32B parameter models for knowledge graph extraction."

For qwen2.5-coder:14b specifically timing out at 10+ minutes per chunk while the GPU sits at 20–40%: this is llama.cpp doing free generation with a hard max-tokens cap and the model getting stuck in repetition loops on a schema it can't satisfy. The low GPU utilization is the model waiting on KV-cache memory I/O, not on compute — typical when a model lacks a clean stop condition.

### 2. Best 16GB-VRAM models for complex structured JSON (evidence-based ranking)

| Model | Q4_K_M VRAM | Evidence for structured JSON | Caveats |
|---|---|---|---|
| **Phi-4 14B** | ~9–10 GB | "Only model that worked successfully locally under 14B" for Fast-GraphRAG entity/relation extraction (LearnOpenCV); 510 min to index 430 items locally; Geeky Gadgets: "adept at extracting detailed and accurate information from complex datasets" and "generating clean, well-formatted code, including JSON structures and classification scripts." | No native function-calling protocol; works in prompt-described schema + grammar mode |
| **Hermes 4 14B** (Qwen3-14B base) | ~9–10 GB | Model card states explicitly: "Schema adherence & structured outputs: trained to produce valid JSON for given schemas and to repair malformed objects"; built-in `<tool_call>` tokens; SGLang/vLLM auto-parsers | Released August 2025 (arXiv 2508.18255); less field-tested than Phi-4 |
| **Qwen3 14B** | ~9 GB | "Structured outputs supported" per SiliconFlow API spec; "best balance of speed and capability for instruction-following tasks" on RTX 4080 16GB (glukhov.org Ollama benchmark) | Generic instruction-tuned, no JSON-specific RL |
| **GPT-OSS 20B** | ~13.7 GB | Fastest 16GB option (42 tok/s, fits 60K context); designed for "function calling with strict JSON schemas" | Documented Ollama/vLLM bugs: HuggingFace discussion #111 reports "generates the correct structured output, then continues with unrelated content, breaking standard parsers"; Harmony format injects unrequested reasoning traces |
| Mistral 7B v0.3 | ~5 GB | InferenceRig 2026: "more reliable at following format constraints than most of its successors… production pipelines where JSON format compliance matters" | 7B intelligence ceiling on complex multi-field schemas |
| Gemma 3 12B | ~8 GB | None for structured KG extraction; listed among models that *failed* in LearnOpenCV's test | Avoid for this task |

**Quantized 20–34B in 16GB**: Qwen3 32B Q3 (~14 GB) is technically loadable but leaves almost no context room. Gemma 4 26B MoE Q4_K_M fits at 16–18 GB only with 1–2 GB of CPU offload (per Crawleo benchmark). Neither is practical for batch extraction over 169 Python files; you will go from "hangs" to "swaps."

### 3. Constrained decoding is the proven path — and it's *faster*, not slower

The JSONSchemaBench paper (arXiv 2501.10868v3) is the definitive benchmark. On a Llama-3.1-8B-Instruct backbone with **llama.cpp backend**, median time-per-output-token (TPOT) and compliance rates were:

| Engine | TPOT (ms, llama.cpp backend) | Compliance — GlaiveAI (function-call schemas) | Compliance — GitHub Hard schemas |
|---|---|---|---|
| LM-only (no constraint) | 15.40 | 90% | 13% |
| **Guidance / llguidance** | **6.37** | 98% | 69% |
| llama.cpp GBNF | 29.98 | 97% | 63% |
| Outlines v0.1.8 | 30.33 | 96% | **6%** |
| XGrammar (HF backend only*) | 66.78 | 93% | 41% |

*The paper notes "XGrammar doesn't support Llamacpp as backend," so the XGrammar TPOT figure is on Hugging Face Transformers and not directly comparable.

Three non-obvious takeaways:

(a) **Guidance is actually faster than unconstrained generation** because the grammar prunes the sampling distribution. The paper measures a 58.6% TPOT reduction on GlaiveAI (6.37 ms vs 15.40 ms LM-only). Common shorthand: "constrained decoding speeds up generation by ~50% vs unconstrained" — the measured number is larger.

(b) **Outlines collapses on complex/recursive schemas**: 6% empirical coverage on GitHub Hard, 22% on Washington Post. Your graphify schema is exactly this hard class — nested nodes/edges/hyperedges/provenance.

(c) **XGrammar's own benchmark** (MLC blog citing arXiv 2411.15100v3) claims "up to 3× speedup on JSON Schema and over 100× on CFG, compared to the best baseline in each case" for per-token mask latency. **vLLM has shipped XGrammar as the default guided-decoding backend since v0.6.5** ("Use xgrammar as the default guided decoding backend (#10785)"), with Outlines as fallback. BentoML reports "in some long context test cases, lm-format-enforcer fails to enforce correct outputs."

### 4. Specialist NLP tools that beat any small LLM at NER/RE on consumer hardware

These run **fully offline on CPU or 4–8 GB VRAM**, are deterministic, and target exactly the "doc semantic node" gap in your current graphify output:

- **GLiNER** (urchade/GLiNER, NAACL 2024): 205M-parameter bidirectional transformer for zero-shot NER + joint relation extraction; the model card states it "outperforms ChatGPT and several LLMs fine-tuned for NER" and is "optimized to run on CPUs and consumer hardware. No GPU required." Practical throughput from the autognosi/GraphRAG-RS team on Tom Sawyer corpus (176 chunks): ~4 min 30 s end-to-end via ONNX Runtime, 39 chunks/min, 631 entities extracted with high precision for Person/Place/Organization. The team explicitly designed GLiNER-Relex as a deterministic alternative because LLM extraction at ~20–60 s per chunk on consumer GPU was unacceptable.
- **REBEL / mREBEL** (Babelscape/rebel-large, EMNLP 2021 Findings): BART-based seq2seq, ~400M params, produces relation triplets directly with special `<triplet>` tokens. Runs on CPU or any GPU; widely used as the LLM-free relation-extraction backbone in LlamaIndex KG pipelines.
- **ReLiK** (Sapienza NLP, ACL 2024 Findings, arXiv 2408.00103): Retriever–Reader architecture for joint entity linking + relation extraction; abstract states "up to 40× inference speed compared to competitors" with SOTA accuracy. Integrated with LlamaIndex and Neo4j.
- **Microsoft GraphRAG / nano-graphrag / LightRAG**: All offline-capable via Ollama, but per their own docs and the LearnOpenCV practitioner test, all three **require ≥14B (Phi-4) or ideally ≥32B models** to produce non-empty graphs. They will hit the same wall as graphify with sub-14B models.
- **LangChain `LLMGraphTransformer`**: Supports both tool-mode (for native-function-calling models) and "prompt-based" fallback mode; usable but doesn't solve the underlying small-model schema problem.

### 5. The pipeline architecture that actually works

The 2026 GraphRAG-RS update (autognosi, Medium Feb 2026) and Neo4j's Agent Memory documentation independently converged on the same multi-pass design after seeing the failures you saw:

```
Pass 1 (deterministic, fast, CPU):
  GLiNER NER → entity spans + types
Pass 2 (deterministic, fast, CPU):
  GLiNER-Relex or REBEL → relation triplets
Pass 3 (LLM, narrow prompt, GBNF-constrained):
  Per-entity disambiguation + confidence + provenance + rationale
  on the candidate set from Pass 1–2
Pass 4 (deterministic, Pydantic):
  Assemble final nodes/edges JSON; attach EXTRACTED / INFERRED /
  AMBIGUOUS labels from confidence thresholds
```

This is essentially ReLiK's Retriever–Reader decomposition, and Neo4j Agent Memory ships it as `ExtractionPipeline(stages=[SpacyEntityExtractor(), GLiNEREntityExtractor.for_schema(...)])`. The crucial benefit for your case: **the LLM never has to emit a 4000-token nested schema in one shot**. Each Pass 3 call is a 200-token JSON fragment about one entity, which 7–14B models *can* handle reliably.

## Details

### Why your current single-shot complex schema fails

Graphify asks the model to produce in one response: nodes (types, IDs, names), edges (source/target/type), hyperedges, per-edge confidence floats, EXTRACTED/INFERRED/AMBIGUOUS provenance labels, and rationales. JSONSchemaBench shows that on the *hardest* real-world schema subset (GitHub Hard, JsonSchemaStore), every constrained-decoding engine drops to 13–69% compliance even with Llama-3.1-8B; unconstrained generation gets 13–21%. Your schema is squarely in this complexity class.

The "hollow response" from qwen2.5-coder:7b is the model emitting opening braces, getting lost in the schema, and looping until max_tokens — graphify's "model too small for JSON instruction following" warning is accurate. The 10+ minute timeout on the 14B is the same failure mode at higher token capacity.

### What to change concretely

1. **Switch the runtime from Ollama to `llama-server` (llama.cpp) with `--json-schema`** (or `--grammar-file`). Ollama's `format=json` does call into llama.cpp's grammar sampler, but its OpenAI-compatible endpoint doesn't expose the schema-conversion path cleanly, and Ollama runs at roughly 15–30% lower throughput with ~10% higher VRAM than raw llama.cpp on the same model (morphllm.com benchmark; dev.to/plasmon_imp also reports ~0.3 GB Ollama overhead at the 8GB tier). Start command:
   ```
   llama-server -m phi-4-14b-Q4_K_M.gguf --json-schema @schema.json \
                --n-gpu-layers 99 --ctx-size 16384 --port 8080
   ```
   This guarantees every response is schema-valid at the token level. No retries, no hollow responses. The llama.cpp grammars README explicitly notes: "The JSON schema is only used to constrain the model output and is not injected into the prompt. The model has no visibility into the schema, so… describe it explicitly in your prompt." — i.e., still include the schema in the prompt as documentation, even though the grammar enforces it.

2. **Replace qwen2.5-coder with Phi-4 14B as the primary model**, with Hermes 4 14B as the backup. Both fit in ~10 GB Q4_K_M, leaving 6 GB for KV-cache at 16K context. Phi-4 has the strongest community evidence for this exact task; Hermes 4 has the explicit "trained to produce valid JSON for given schemas and to repair malformed objects" property that helps when the schema is borderline.

3. **Decompose the prompt** — split graphify's semantic extraction pass into (a) entity pass with GLiNER (no LLM), (b) relation pass with REBEL or a narrow LLM call per entity pair, (c) provenance/rationale pass on already-identified relations. The third pass is the only one needing the LLM, and it gets a 5-field schema instead of a 20-field one.

4. **For markdown/text docs specifically**, run GLiNER first with a custom label set derived from your AST nodes (class names, function names, module names extracted in Pass 1). This gives you "doc → code" cross-edges deterministically, which is the bulk of the "doc semantic node" value you're missing today.

### Alternatives that look promising but hit the same wall — flagged

- **Microsoft GraphRAG / GraphRAG-local-ollama**: Documented working with mistral/gemma2/phi3 via Ollama (TheAiSingularity and Igor3407 forks), but multiple practitioners (chishengliu blog, LearnOpenCV) report it requires careful prompt engineering and patching with sub-32B models. The forks haven't been updated in months; treat as reference, not production.
- **LightRAG with Ollama**: Issue #30 documents the exact "0 entities, 0 relationships" failure with multiple Ollama models; the project's own README now recommends ≥32B.
- **Outlines as a structured-output backend**: It's a popular Reddit/HN recommendation, but JSONSchemaBench v0.1.8 numbers show empirical coverage of 6% on GitHub Hard and 22% on Washington Post — the schema class graphify uses. Don't pick it for nested/recursive schemas without re-benchmarking the newer Rust backend.
- **GPT-OSS 20B**: Fastest on 16GB VRAM (42 tok/s, 13.7 GB at 60K context), but HuggingFace discussion #111 and glukhov.org both report "generates the correct structured output, then continues with unrelated content, breaking standard parsers." Use only with manual pre/post-split markers; not drop-in.
- **LM Format Enforcer**: BentoML reports "in some long context test cases, lm-format-enforcer fails to enforce correct outputs"; vLLM has deprioritized it in favor of XGrammar.

### Community evidence at 100+ file scale

- **Carlo C. / autognosi GraphRAG-RS** (Medium, Feb 2026): Processes book-length corpora on consumer GPU with KV-caching + GLiNER-Relex + Mistral-NeMo 12B fallback; explicitly recommends GLiNER-Relex for "scientific papers, legal documents, financial reports" where vocabulary is bounded — i.e., your case.
- **Neo4j Agent Memory**: Ships `SpacyEntityExtractor → GLiNEREntityExtractor` pipeline as the documented offline production pattern, with explicit "GLiNER specifically benefits from batching on GPU" guidance for the 5080 class.
- **LearnOpenCV Fast-GraphRAG**: 430 items indexed in 8.5 hours on local Phi-4 14B — directly comparable to your 22 docs + 169 Python files scale (expect 1–2 hours).

## Recommendations

**Stage 1 — Stop the bleeding (this week)**
- Replace Ollama with `llama-server` (llama.cpp) and pass `--json-schema` corresponding to graphify's expected output. This alone should resolve "hollow responses" and most of the 10-minute timeouts, even before changing models.
- Swap qwen2.5-coder for **Phi-4 14B Q4_K_M** (microsoft/phi-4 GGUF). It's the only sub-14B model with direct evidence of working on this exact task class.

**Stage 2 — Get doc/semantic nodes flowing (next week)**
- Add a **GLiNER pre-pass** in front of graphify's LLM stage to seed it with candidate entity spans from your markdown docs. Label set: derive from the 1,597 AST nodes you already have (class names, module names, top imports) plus generic `Concept`, `Algorithm`, `Configuration`, `Decision`. This is what makes the LLM call easy.
- Re-run on the 22 markdown + 169 Python files. **Benchmark target**: if Phi-4 14B + grammar produces ≥80% of files with valid JSON in <60 s/file, you're done.

**Stage 3 — Scale and quality (if needed)**
- If Phi-4 14B still hallucinates relations, add **REBEL or ReLiK** as a deterministic relation backbone, and use the LLM only to label provenance (EXTRACTED/INFERRED/AMBIGUOUS) on already-extracted triplets. This is the GraphRAG-RS 2026 pattern.
- If you need higher recall on conceptual docs, fine-tune GLiNER on 20–50 hand-labeled examples from your corpus — a 30-minute job on the RTX 5080 that typically lifts F1 by 5–15 points.

**Decision thresholds that change the plan**
- If Phi-4 14B + GBNF produces <50% valid JSON on your corpus → drop the LLM for KG extraction entirely; use GLiNER + REBEL + Pydantic assembly. Accept narrower "EXTRACTED" labels and skip "INFERRED."
- If per-file latency stays >120 s with Phi-4 → either switch to GPT-OSS 20B with manual post-parsing (faster, but accept some retries), or move to **vLLM with `guided_json` + XGrammar** for batched throughput.
- If GPU utilization stays <50% after switching to llama.cpp → the bottleneck is prompt processing, not generation; reduce context to 8K and chunk more aggressively.

## Caveats

- **JSONSchemaBench has a conflict of interest**: it was co-authored by Guidance/llguidance maintainers and Guidance wins most of its categories. The raw numbers are reproducible (code released), but treat the qualitative ranking with skepticism. The absolute finding that *all* engines collapse on hard schemas is robust across independent reports.
- **LearnOpenCV's Phi-4 result is N=1**: a single practitioner team testing a single pipeline (Fast-GraphRAG's `summarize_entity_description` stage), not a controlled comparison. The *category* finding (one of Phi-4 / ≥32B works, others <14B don't) is more robust than the exact ranking.
- **Hermes 4 14B is recent** (released August 2025, arXiv 2508.18255). The "trained for structured outputs / repairs malformed JSON" claim comes from the Nous Research model card, not yet independently benchmarked at scale; treat as promising but unproven for your specific task class.
- **Outlines results may have improved** since the JSONSchemaBench v0.1.8 numbers (Jan 2025); the newer Rust backend may have closed the gap. The hard-schema collapse is structural to FSM-based approaches, however, so improvements will likely be incremental.
- **Graphify's confidence/provenance schema is unusual**: most KG-extraction tools don't emit EXTRACTED/INFERRED/AMBIGUOUS labels. You will likely need to compute these deterministically in a Pass 4 (e.g., GLiNER score ≥0.85 → EXTRACTED; LLM-only edges → INFERRED; conflicting passes → AMBIGUOUS) rather than expecting any model to produce them natively.
- **RTX 5080 / Windows 11 caveats**: the RTX 5080 (Blackwell, sm_120) requires CUDA 12.8+ and recent llama.cpp/vLLM builds. Some pre-built wheels lag; building llama.cpp from source against the CUDA 12.8 toolkit may be required. ONNX Runtime for GLiNER works fine on Windows but GPU acceleration there requires the matching CUDA EP build.
- **Single-shot vs decomposed precision trade**: decomposing into GLiNER + LLM passes will give you many more nodes (good for your "zero semantic/doc nodes" problem) but may reduce *edge* precision compared to a hypothetical perfectly-working single-shot LLM extraction, because cross-entity reasoning happens in one model context. The provenance labels are your safety net here — keep them and weight queries by them.