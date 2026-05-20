Based on your described constraints and the issues you've encountered, achieving your goal requires a shift in strategy. The core problem is that local models on consumer hardware struggle with the single-pass, "one-shot" generation of a complex knowledge graph from a massive prompt. The solution lies in breaking the task into smaller, manageable steps, supported by the right models and tools.

Here are the most viable, community-verified solutions tailored to your needs.

### 🧠 1. Alternative Local Models Fine-Tuned for Structured Extraction

Instead of relying on general-purpose coding models, you can use small language models (SLMs) specifically fine-tuned for information extraction. These models are trained to produce structured output, like JSON, which directly addresses the issue of "hollow responses" you saw with the 7B Qwen model. They understand the *task* of extraction and are less likely to get lost in complex instructions.

| Model Name | Size | Context | Why it's a good fit for you |
| :--- | :--- | :--- | :--- |
| **NuExtract-v1.5** | 3.8B params | Long documents | A fine-tune of Microsoft's Phi-3.5-mini, available on Ollama. It's a top recommendation for its balance of size and capability. The official Hugging Face page recommends using a temperature of 0 for optimal performance in extraction tasks. |
| **NuExtract-tiny-v1.5** | 0.5B params | 2000 tokens | Based on Qwen2.5-0.5B, this is the ultra-lightweight option for rapid, simple extractions from shorter text segments. |
| **NuExtract-1.5-smol** | 1.7B params | Long documents | A fine-tune of SmolLM2-1.7B, designed for structured information extraction. A good middle-ground choice that's less than half the size of the original NuExtract-v1.5. |

#### 🚀 Real-World Use Case: Multi-Step Pipeline with NuExtract

A highly effective strategy for complex extraction is to use a multi-step pipeline, as demonstrated in practice by developer **heydibyendu** to process medical conversations. You can adapt this approach to your code and documentation:
1.  **Chunking**: Split your documents into smaller, manageable text blocks.
2.  **Entity Extraction (Step 1)**: Use a model like NuExtract to identify key entities (e.g., code functions, variables, document concepts) from each chunk.
3.  **Relationship Extraction (Step 2)**: Send the entities identified in step 1 back to the model to determine the relationships between them.

This approach breaks the complex single-prompt task into smaller, more reliable steps for a small local model.

*   **Evidence & Resources**: This pipeline approach is well-documented. You can find a complete implementation guide in the `heydibyendu/NuExtract` GitHub repository. The Ollama model pages for `nuextract` and `iodose/nuextract-v1.5` also provide detailed usage instructions.

### 🛠️ 2. Alternative Tools for Offline Knowledge Graph Extraction

Beyond `graphify`, there are other tools designed for offline KG construction that may have a more suitable extraction strategy for local models.

| Tool | Description | Key Features | Relevance |
| :--- | :--- | :--- | :--- |
| **kg-gen** | A Python library for extracting knowledge graphs from plain text using AI. | Supports various LLM backends including Ollama. | A direct alternative to `graphify` with explicit Ollama support. |
| **Docling Graph** | Transforms unstructured documents into validated knowledge graphs. | Supports local VLM and LLM extraction, with a config-driven pipeline. | A robust option with multiple extraction backends and schema enforcement. |
| **llm2graph** | A package from a COLM 2025 paper for dynamic knowledge graph construction. | LLM-only pipeline, strict formatting enforcement, and support for local HuggingFace models. | A research-backed tool that emphasizes strict output validation. |

#### 💡 A Hybrid Strategy: AST + Semantic Extraction

A powerful approach is to combine the strengths of different methods. You've already had success with `graphify`'s AST extraction. You can leverage this deterministic output to guide the more complex semantic extraction.

**Recommended Hybrid Workflow:**
1.  **Run AST Extraction**: Use `graphify`'s deterministic parser to extract the code structure (classes, functions, calls) – which you've already done successfully.
2.  **Enrich with Semantic Extraction**: Use a tool like `kg-gen` with a model like NuExtract. The system prompt can be crafted to connect the semantic entities (e.g., "Authentication Module") to the already-extracted code structures (e.g., the `login()` function). This makes the LLM's task easier and the final graph much richer.

### ⛓️ 3. Guaranteeing Valid JSON with Constrained Generation

Constrained (or guided) generation is a technique that forces the LLM to only produce tokens that conform to a predefined schema, guaranteeing valid JSON output. This is the most robust solution to the problem of malformed output.

| Method | How it Works | Key Strengths |
| :--- | :--- | :--- |
| **llama.cpp Grammars** | Uses a formal grammar (GBNF) to define valid output structures at the token level. | Deep integration with the `llama.cpp` ecosystem, including Ollama. |
| **Outlines** | Uses finite-state machines (FSMs) to enforce constraints, guaranteeing structural validity. | High-level Pythonic interface, supports Ollama as a backend, and is praised for balancing flexibility and strict enforcement. |
| **LM Format Enforcer** | Filters the model's token probabilities, only allowing tokens that keep the output valid. | Balances strict compliance with the model's natural style, ensuring high-quality output. |

#### 🚀 Real-World Application: Self-Expanding Knowledge Graphs

The `cpfiffer/self-expansion` project is a direct, real-world demonstration of this concept. It uses **Outlines** to generate reliably structured output for a knowledge graph that can expand itself based on a core directive. The project defines different schemas (Pydantic models) for nodes like `Question`, `Answer`, and `Concept`, and the model's output is strictly constrained to these valid options.

*   **Evidence**: The project's repository includes runnable code, and the authors have given talks on the subject, providing strong evidence that this approach works in practice.

### ⚖️ 4. Quantized Larger Models for 16GB VRAM

To fit a larger, more capable model into your 16GB of VRAM, quantization is necessary.

*   **What Fits**: A 20B-34B parameter model quantized to **Q4_K_M** or **IQ4_XS** is likely the sweet spot for your VRAM. These formats offer a good trade-off between size and quality.
*   **Models to Test**: You should look for GGUF quantizations of models known for strong instruction-following, such as:
    *   **Qwen2.5-32B-Instruct**: A powerful general-purpose model.
    *   **Command R (35B)**: A model by Cohere designed for enterprise RAG and tool use.
    *   **Yi-34B**: Another strong contender from 01.AI.
*   **Community Note**: To find the best balance for your hardware, you can refer to detailed community-maintained GGUF quantization guides that outline the quality/size trade-off for different quants.

### 💎 Summary and Recommended Action Plan

Given your hardware, successful knowledge graph extraction requires a strategy of breaking down the problem. Here is my recommended plan of action:

1.  **Start with a Specialized Model**: This is the quickest win. Install **NuExtract-v1.5** from Ollama and test it on a small document. This immediately addresses the model capability issue you faced.
2.  **Try an Alternative, More Flexible Tool**: If `graphify`'s rigid prompt is still an issue, switch to **`kg-gen`**. Its explicit Ollama support and potential for a more streamlined workflow may be a better fit.
3.  **Implement a Multi-Step Pipeline**: As a logical next step, use NuExtract in a two-step process: first extract entities, then extract relationships from those entities. This is the most reliable way to get complex data from a smaller model.
4.  **Adopt Constrained Generation as a Long-Term Solution**: To fundamentally solve the problem of invalid JSON, adopt a framework like **Outlines**, which supports Ollama. This guarantees schema-compliant output.
5.  **Upgrade Your Model as a Last Resort**: If you absolutely need a single model for the entire complex task, try running a heavily quantized **Qwen2.5-32B-Instruct (Q4_K_M GGUF)** in Ollama and see if the quality and speed are acceptable.

This layered approach will let you methodically overcome the limitations you've encountered. Please feel free to ask if you need more details on implementing any of these specific steps.