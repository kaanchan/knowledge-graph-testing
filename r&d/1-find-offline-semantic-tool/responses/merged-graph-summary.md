# Merged Knowledge Graph — Summary

## Overview
- **Total nodes:** 143
- **Total edges:** 153
- **graphify nodes** (code structure): 35
- **nuextract3 nodes** (prose semantics): 100
- **Merged nodes** (concept appeared in both layers): 8
- **Code structure edges:** 47
- **Semantic relation edges:** 106

## Fused Nodes (same concept in code + prose)
- `runlog_py` — runlog.py (file)
- `ralph_test_slice_topology_wrap_node` — wrap_node() (Software)
- `architecture_research_langgraph` — LangGraph (library)
- `architecture_research_aider` — Aider (Software)
- `architecture_research_ollama` — Ollama (service)
- `implementation_plan_src` — src directory (Directory)
- `implementation_plan_tests` — tests directory (panel)
- `implementation_plan_prompts` — prompts directory (File)

## Most Connected Nodes
- **wrap_node()** (`ralph_test_slice_topology_wrap_node`) — 36 connections — source: merged
- **Aider** (`architecture_research_aider`) — 14 connections — source: merged
- **runlog.py** (`runlog_py`) — 10 connections — source: merged
- **Ollama** (`architecture_research_ollama`) — 9 connections — source: merged
- **d_model.py** (`d_model_py`) — 8 connections — source: graphify
- **RalphDashboard** (`ralphdashboard`) — 8 connections — source: nuextract3
- **log()** (`ralph_test_slice_d_model_log`) — 5 connections — source: graphify
- **LangGraph** (`architecture_research_langgraph`) — 5 connections — source: merged
- **qwen25-coder-14b** (`qwen25_coder_14b`) — 5 connections — source: nuextract3
- **main.py** (`main_py`) — 5 connections — source: nuextract3

## Sample Semantic Relations (from nuextract3)
- ralph_test_slice_topology_wrap_node **uses** architecture_research_langgraph
- ralph_test_slice_topology_wrap_node **uses** qwen25_coder_14b
- ralph_test_slice_topology_wrap_node **uses** architecture_research_ollama
- ralph_test_slice_topology_wrap_node **falls back to** gemini
- qwen25_coder_14b **uses** architecture_research_ollama
- architecture_research_ollama **uses** rtx_3090
- qwen2_5_coder_14b **uses** chatml
- qwen2_5_coder_14b **uses** vram
- ralph_test_slice_topology_wrap_node **uses** architecture_research_aider
- ralph_test_slice_topology_wrap_node **uses** nvidia_smi
- ralph_test_slice_topology_wrap_node **uses** architecture_research_ollama
- ralph_test_slice_topology_wrap_node **uses** architecture_research_langgraph
- ralph_test_slice_topology_wrap_node **uses** architecture_research_aider
- ralph_test_slice_topology_wrap_node **uses** qwen25_coder_14b
- ralph_test_slice_topology_wrap_node **uses** main_py

## Sample Code Relations (from graphify)
- `d_model_py` **contains** `ralph_test_slice_d_model_ts` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_log` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_ok` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_fail` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_step` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_show` (d_model.py)
- `d_model_py` **contains** `ralph_test_slice_d_model_chat` (d_model.py)
- `ralph_test_slice_d_model_rationale_1` **rationale_for** `d_model_py` (d_model.py)
- `ralph_test_slice_d_model_ok` **calls** `ralph_test_slice_d_model_ts` (d_model.py)
- `ralph_test_slice_d_model_fail` **calls** `ralph_test_slice_d_model_ts` (d_model.py)
- `ralph_test_slice_d_model_step` **calls** `ralph_test_slice_d_model_ts` (d_model.py)
- `ralph_test_slice_d_model_ok` **calls** `ralph_test_slice_d_model_log` (d_model.py)
- `ralph_test_slice_d_model_fail` **calls** `ralph_test_slice_d_model_log` (d_model.py)
- `ralph_test_slice_d_model_step` **calls** `ralph_test_slice_d_model_log` (d_model.py)
- `ralph_test_slice_d_model_show` **calls** `ralph_test_slice_d_model_log` (d_model.py)

## All Nodes
| id | label | type | source | file |
|---|---|---|---|---|
| `check_env_py` | check_env.py | code | graphify | check_env.py |
| `d_model_py` | d_model.py | code | graphify | d_model.py |
| `ralph_test_slice_d_model_ts` | ts() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_log` | log() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_ok` | ok() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_fail` | fail() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_step` | step() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_show` | show() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_chat` | chat() | code | graphify | d_model.py |
| `ralph_test_slice_d_model_rationale_1` | D_model: Direct local model capability — no Aider, no LiteLLM.  Calls Ollama /ap | rationale | graphify | d_model.py |
| `ralph_test_slice_d_model_rationale_38` | POST to /api/chat, return (response_text, elapsed_seconds). | rationale | graphify | d_model.py |
| `ralph_test_slice_runlog_ts` | _ts() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_log` | log() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_reset_log` | reset_log() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_log_tool` | log_tool() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_ollama_ps` | ollama_ps() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_loud_timeout` | loud_timeout() | code | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_1` | Live run log — tail-able by `Get-Content -Wait ralph_run.log` in another termina | rationale | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_20` | Append a line to ralph_run.log. Best-effort — never raises on disk error. | rationale | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_39` | Truncate the log at the start of a run so it always reflects the current run. | rationale | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_54` | Logs raw tool output to tools_debug.log if RALPH_VERBOSE is true. | rationale | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_65` | Snapshot of /api/ps so timeout messages show whether the model is actually loade | rationale | graphify | runlog.py |
| `ralph_test_slice_runlog_rationale_80` | Big visible block when a timeout fires — designed to surface in a glance. | rationale | graphify | runlog.py |
| `solution_fib_py` | solution_fib.py | code | graphify | solution_fib.py |
| `ralph_test_slice_solution_fib_fibonacci` | fibonacci() | code | graphify | solution_fib.py |
| `topology_py` | topology.py | code | graphify | topology.py |
| `ralph_test_slice_topology_escalate_node` | escalate_node() | code | graphify | topology.py |
| `ralph_test_slice_topology_build_graph` | build_graph() | code | graphify | topology.py |
| `ralph_test_slice_topology_rationale_1` | Dynamic topology loader for RALPH (Meta Test). Loads graph structure from graph. | rationale | graphify | topology.py |
| `ralph_test_slice_topology_rationale_28` | Flip the escalated flag so subsequent calls use the cloud model. | rationale | graphify | topology.py |
| `architecture_research_ralph` | RALPH Architecture & State of the Art | document | graphify | 20260508_003156_architecture_research.md |
| `implementation_plan_ralph` | RALPH Refactoring & Capability Profiling Plan | document | graphify | 20260508_003156_implementation_plan.md |
| `aider_local_usecases_aider` | Aider Offline Use Cases | document | graphify | 20260508_012257_aider_local_usecases.md |
| `visualization_plan_dashboard` | Offline Observability & TV-Mode Visualization Layer | document | graphify | 20260508_012257_visualization_plan.md |
| `architecture_roadmap_ralph` | RALPH Architecture & Evolution Roadmap | document | graphify | architecture_roadmap.md |
| `runlog_py` | runlog.py | code | merged | runlog.py |
| `ralph_test_slice_topology_wrap_node` | wrap_node() | code | merged | topology.py |
| `architecture_research_langgraph` | LangGraph | concept | merged | 20260508_003156_architecture_research.md |
| `architecture_research_aider` | Aider | concept | merged | 20260508_003156_architecture_research.md |
| `architecture_research_ollama` | Ollama | concept | merged | 20260508_003156_architecture_research.md |
| `implementation_plan_src` | src directory | code | merged | 20260508_003156_implementation_plan.md |
| `implementation_plan_tests` | tests directory | code | merged | 20260508_003156_implementation_plan.md |
| `implementation_plan_prompts` | prompts directory | code | merged | 20260508_003156_implementation_plan.md |
| `qwen25_coder_14b` | qwen25-coder-14b | model | nuextract3 | 20260508_003156_architecture_research.md |
| `gemini` | Gemini | model | nuextract3 | 20260508_003156_architecture_research.md |
| `qwen2_5_coder_14b` | Qwen2.5-Coder-14B | model | nuextract3 | 20260508_003156_architecture_research.md |
| `rtx_3090` | RTX 3090 | hardware | nuextract3 | 20260508_003156_architecture_research.md |
| `chatml` | ChatML | format | nuextract3 | 20260508_003156_architecture_research.md |
| `vram` | VRAM | resource | nuextract3 | 20260508_003156_architecture_research.md |
| `nvidia_smi` | nvidia-smi | Tool | nuextract3 | 20260508_003156_implementation_plan.md |
| `main_py` | main.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `config_py` | config.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `evaluator_py` | evaluator.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `executor_py` | executor.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `graph_py` | graph.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `memory_py` | memory.py | VRAM | nuextract3 | 20260508_003156_implementation_plan.md |
| `router_py` | router.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `state_py` | state.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `test_gemini_py` | test_gemini.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `test_langsmith_py` | test_langsmith.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `test_local_py` | test_local.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `qna_architecture_research_md` | QnA_Architecture_Research.md | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `hardware_py` | hardware.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `model_registry_py` | model_registry.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `diagnostics_run_all_py` | diagnostics/run_all.py | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `handoff_md` | HANDOFF.md | File | nuextract3 | 20260508_003156_implementation_plan.md |
| `c_users_kaanchan_projects_ai_ralph_test_target` | C:\Users\kaanchan\Projects\AI\ralph-test-target\ | Directory | nuextract3 | 20260508_003156_implementation_plan.md |
| `20260508_003156_gemini_plan` | 20260508_003156_gemini_plan | Git Tag | nuextract3 | 20260508_003156_implementation_plan.md |
| `claude_3_5_sonnet` | Claude 3.5 Sonnet | Model | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `gpt_4o` | GPT-4o | Model | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `litellm` | LiteLLM | Software | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `llama_3_70b` | Llama 3 70B | Model | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `qwen_32b` | Qwen 32B | Model | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `rtx_3090s` | RTX 3090s | Hardware | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `mac_studio_m2` | Mac Studio M2 | Hardware | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `soc2` | SOC2 | Standard | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `hipaa` | HIPAA | Standard | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `itar` | ITAR | Standard | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `ralphdashboard` | RalphDashboard | class | nuextract3 | 20260508_012257_visualization_plan.md |
| `richlive` | RichLive | class | nuextract3 | 20260508_012257_visualization_plan.md |
| `langsmith` | LangSmith | service | nuextract3 | 20260508_012257_visualization_plan.md |
| `src_dashboard_py` | src/dashboard.py | file | nuextract3 | 20260508_012257_visualization_plan.md |
| `src_main_py` | src/main.py | file | nuextract3 | 20260508_012257_visualization_plan.md |
| `src_runlog_py` | src/runlog.py | rich.live.Live | nuextract3 | 20260508_012257_visualization_plan.md |
| `header_panel` | Header Panel | panel | nuextract3 | 20260508_012257_visualization_plan.md |
| `left_panel` | Left Panel | panel | nuextract3 | 20260508_012257_visualization_plan.md |
| `right_panel` | Right Panel | panel | nuextract3 | 20260508_012257_visualization_plan.md |
| `test_output` | Test Output | panel | nuextract3 | 20260508_012257_visualization_plan.md |
| `ollama_heartbeats` | Ollama heartbeats | log | nuextract3 | 20260508_012257_visualization_plan.md |
| `node_transitions` | node transitions | log | nuextract3 | 20260508_012257_visualization_plan.md |
| `model_timeouts` | model timeouts | log | nuextract3 | 20260508_012257_visualization_plan.md |
| `task_pod` | Task Pod | Architecture | nuextract3 | architecture_roadmap.md |
| `state_routing_matrix` | State Routing Matrix | Architecture | nuextract3 | architecture_roadmap.md |
| `meta_consultant_cloud_node` | Meta-Consultant Cloud Node | Architecture | nuextract3 | architecture_roadmap.md |
| `hardware_aware_calibration_node` | Hardware-Aware Calibration Node | Architecture | nuextract3 | architecture_roadmap.md |
| `node_library` | Node Library | Architecture | nuextract3 | architecture_roadmap.md |
| `dynamic_task_topologies` | Dynamic Task Topologies | Architecture | nuextract3 | architecture_roadmap.md |
| `dashboard_controls` | Dashboard Controls | Architecture | nuextract3 | architecture_roadmap.md |
| `visual_graph_editor` | Visual Graph Editor | Architecture | nuextract3 | architecture_roadmap.md |
| `ralf` | RALF | concept | nuextract3 | 20260508_003156_implementation_plan.md |
| `qna_archirecture_research_md` | QnA_Archirecture_Research.md | concept | nuextract3 | 20260508_003156_implementation_plan.md |
| `free_vram_mb` | free_vram_mb | concept | nuextract3 | 20260508_003156_implementation_plan.md |
| `pair_programming` | pair-programming | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `search_replace_diff_protocol` | SEARCH/REPLACE diff protocol | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `repository_mapping` | repository mapping | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `ctags` | ctags | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `local_models` | local models | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `enterprise_developers` | Enterprise developers | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `offline_local_models` | offline/local models | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `openai` | OpenAI | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `google` | Google | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `autonomous_agents` | Autonomous agents | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `whole_file_generation` | whole-file generation | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `surgical_diffs` | surgical diffs | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `aider_s_formatting_rules` | Aider's formatting rules | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `70b_parameter_models` | 70B+ parameter models | concept | nuextract3 | 20260508_012257_aider_local_usecases.md |
| `raphdashboard` | RaphDashboard | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `log` | log | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `console_print` | console.print | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `graph_stream` | graph.stream | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `full_screen_terminal_ui` | full-screen terminal UI | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `panes` | panes | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `logs` | logs | concept | nuextract3 | 20260508_012257_visualization_plan.md |
| `currently_executing` | Currently Executing | concept | nuextract3 | architecture_roadmap.md |
| `independent_versioning_of_langgraph_configurations` | independent versioning of LangGraph configurations | concept | nuextract3 | architecture_roadmap.md |
| `localized_zoomable_telemetry_traces` | localized zoomable telemetry traces | concept | nuextract3 | architecture_roadmap.md |
| `dashboard_registry` | Dashboard Registry | concept | nuextract3 | architecture_roadmap.md |
| `global_ralph_registry_json` | global .ralph_registry.json | concept | nuextract3 | architecture_roadmap.md |
| `graph_execution_states` | graph execution states | concept | nuextract3 | architecture_roadmap.md |
| `escalate_node` | escalate node | concept | nuextract3 | architecture_roadmap.md |
| `meta_extracted` | Meta-Extracted | concept | nuextract3 | architecture_roadmap.md |
| `local_model_s_failure_trace` | local model's failure trace | concept | nuextract3 | architecture_roadmap.md |
| `before_the_planner` | before the planner | concept | nuextract3 | architecture_roadmap.md |
| `local_model_timeout` | LOCAL_MODEL_TIMEOUT | concept | nuextract3 | architecture_roadmap.md |
| `monolithic_script` | monolithic script | concept | nuextract3 | architecture_roadmap.md |
| `plug_and_play_repository_of_agent_behaviors` | plug-and-play repository of agent behaviors | concept | nuextract3 | architecture_roadmap.md |
| `hardcoded_src_graph_py` | hardcoded src/graph.py | concept | nuextract3 | architecture_roadmap.md |
| `langgraph_topology_logic` | LangGraph topology logic | concept | nuextract3 | architecture_roadmap.md |
| `running_langgraph_engine` | running LangGraph engine | concept | nuextract3 | architecture_roadmap.md |
| `text_only_trace_view` | text-only trace view | concept | nuextract3 | architecture_roadmap.md |
| `nodes_edges_and_live_execution_state` | nodes, edges, and live execution state | concept | nuextract3 | architecture_roadmap.md |
| `add_remove_nodes` | add/remove nodes | concept | nuextract3 | architecture_roadmap.md |
| `tweak_custom_node_parameters` | tweak custom node parameters | concept | nuextract3 | architecture_roadmap.md |