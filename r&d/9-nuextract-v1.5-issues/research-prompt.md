# Research Prompt — NuExtract-v1.5 Reliability on Real-World Markdown Documentation

**Context:** We are running an offline knowledge graph extraction experiment on a Python AI agent project called Ralph. The codebase has markdown docs written in first-person prose ("I have successfully implemented...") typical of developer handoff notes. We are comparing two extraction paths: Path A (graphify + llama.cpp Phi-4) and Path B (NuExtract-v1.5 + kg-gen).

**The problem we ran into with NuExtract-v1.5 (via Ollama, model `iodose/nuextract-v1.5`):**

NuExtract silently returns an empty template echo — `{"entities": [{"name": "", "type": ""}]}` — instead of extracted entities when given real-world developer documentation. It works correctly on:
- Short factual sentences: "Ralph is an AI framework using LangGraph and Ollama" → 4 entities ✓
- Simple declarative third-person text → works ✓

It fails on:
- First-person prose: "I have successfully implemented a headless backend for RALPH..." → 0 entities ✗
- Verbose complex sentences with multiple clauses → 0 entities ✗
- Real markdown docs even after stripping `#` headers → 0 entities ✗

We also discovered that when it does produce output, it emits two JSON blocks: an empty template echo followed by the real output in a ` ```json ` fence. Our pipeline was only extracting the first block (the echo). We fixed this.

**What we need to know:**

1. **Is this a known limitation of NuExtract-v1.5?** Is there documented guidance about text types it handles well vs poorly?
2. **Is there a correct prompt format or preprocessing step** that makes NuExtract-v1.5 work reliably on first-person/narrative prose? We tried stripping markdown headers and replacing "I have" → "The author has" — neither fixed it.
3. **Is `nuextract-v2` or a successor model available** that handles diverse text styles better? We have 16GB VRAM.
4. **Recommended alternative extraction models** for structured entity/relation extraction from developer docs (offline, GGUF/Ollama-compatible, fits in ~8GB VRAM alongside other models)?

**Our workaround:** We switched to phi4 via Ollama chat API using a JSON schema instruction prompt. This works (88 entities, 51 relations from 5 docs). But we'd prefer a dedicated extraction model if one exists that is reliable on real-world text.

**Hardware:** Windows 11, 16GB VRAM GPU, running llama.cpp + Ollama locally.
