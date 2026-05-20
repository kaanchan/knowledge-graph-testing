# start-llama-server-grammar.ps1
# Step 2 fallback variant — documents grammar injection workflow for GBNF enforcement.
# GH issue #4 (ref #8)
#
# ── IMPORTANT: HOW GRAMMAR WORKS IN LLAMA-SERVER ─────────────────────────────
#
# Grammar is NOT passed at server startup.
# llama-server does NOT accept a --grammar or --grammar-file flag at launch.
#
# Instead, grammar is injected PER-REQUEST in the request body:
#
#   POST /v1/chat/completions
#   {
#     "model": "phi-4",
#     "messages": [...],
#     "grammar": "<contents of scripts/graphify.gbnf>"
#   }
#
# This means:
#   - The server itself starts IDENTICALLY to start-llama-server.ps1
#   - The grammar constraint is the caller's responsibility (graphify or a proxy)
#
# ── GRAPHIFY COMPATIBILITY ────────────────────────────────────────────────────
#
# graphify sends requests via its llm.py module. Two options:
#
#   OPTION A — inspect graphify llm.py for extra_body support (preferred, zero new components)
#     graphify's _call_openai_compat() in llm.py passes extra_body to the OpenAI client.
#     Check whether there is an env var (e.g. GRAPHIFY_EXTRA_BODY) that populates extra_body —
#     none was found in the Phase 2 source inspection, so this may require a one-line patch
#     to llm.py to read an env var and inject "grammar" into the extra_body dict.
#     File: %APPDATA%\uv\tools\graphifyy\Lib\site-packages\graphify\llm.py
#
#   OPTION B — Thin FastAPI proxy (if Option A not available)
#     Deploy a small proxy that:
#       - Listens on port 8081 (graphify points here via OLLAMA_BASE_URL)
#       - Injects "grammar" field into every /v1/chat/completions request body
#       - Forwards to llama-server on port 8080
#     Proxy code: write as scripts/grammar-proxy.py (not in current scope)
#     Reference: https://github.com/ggerganov/llama.cpp/blob/master/grammars/README.md
#
# ── HOW TO TEST GRAMMAR DIRECTLY (bypassing graphify) ────────────────────────
#
# This script starts llama-server (same as start-llama-server.ps1) and then
# fires a single test request with the grammar injected, so you can verify the
# grammar parses correctly before wiring it into graphify.

param(
    [string]$ModelPath = "D:\models\phi-4-Q4_K_M.gguf",
    [string]$ServerExe = "D:\llama.cpp\llama-server.exe",
    [int]   $GpuLayers = 99,
    [int]   $CtxSize   = 16384,
    [int]   $Port      = 8080,
    [switch]$TestOnly  # If set, assumes server is already running and just sends the grammar test
)

$GbnfPath = Join-Path $PSScriptRoot "graphify.gbnf"

if (-not (Test-Path $GbnfPath)) {
    Write-Error "Grammar file not found: $GbnfPath"
    Write-Error "Expected: scripts\graphify.gbnf"
    exit 1
}

$grammarContent = Get-Content $GbnfPath -Raw

# ── Start server (same flags as start-llama-server.ps1) ──────────────────────

if (-not $TestOnly) {
    if (-not (Test-Path $ServerExe)) {
        Write-Error "llama-server.exe not found: $ServerExe"
        exit 1
    }
    if (-not (Test-Path $ModelPath)) {
        Write-Error "Model not found: $ModelPath"
        exit 1
    }

    Write-Host "Starting llama-server (grammar variant)..." -ForegroundColor Cyan
    Write-Host "  Server startup is IDENTICAL to start-llama-server.ps1."
    Write-Host "  Grammar is injected per-request, not at startup."
    Write-Host ""
    Write-Host "Run this in a SEPARATE terminal, then re-run with -TestOnly to test grammar." -ForegroundColor Yellow
    Write-Host ""

    & $ServerExe `
        -m $ModelPath `
        --n-gpu-layers $GpuLayers `
        --ctx-size $CtxSize `
        --port $Port `
        --host 127.0.0.1
} else {
    # ── Grammar test request ──────────────────────────────────────────────────
    Write-Host "=== Grammar test: POST /v1/chat/completions with graphify.gbnf ===" -ForegroundColor Cyan
    Write-Host ""

    # Get model ID from running server
    try {
        $modelsResp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -Method GET
        $modelId = $modelsResp.data[0].id
    } catch {
        Write-Error "Server not responding at port $Port. Start with: .\scripts\start-llama-server-grammar.ps1"
        exit 1
    }

    $testBody = @{
        model    = $modelId
        messages = @(
            @{
                role    = "system"
                content = "You are a knowledge graph extractor. Output valid JSON matching the provided schema."
            },
            @{
                role    = "user"
                content = "Extract entities and relations from: 'The function foo() calls bar() in module utils.'"
            }
        )
        grammar     = $grammarContent   # GBNF grammar injected per-request
        max_tokens  = 512
        temperature = 0.0
    } | ConvertTo-Json -Depth 10

    $headers = @{ "Content-Type" = "application/json" }

    try {
        $response = Invoke-RestMethod `
            -Uri "http://127.0.0.1:$Port/v1/chat/completions" `
            -Method POST `
            -Headers $headers `
            -Body $testBody

        $reply = $response.choices[0].message.content
        Write-Host "Response from model (grammar-constrained):" -ForegroundColor Green
        Write-Host $reply
        Write-Host ""

        # Quick JSON parse check
        try {
            $parsed = $reply | ConvertFrom-Json
            Write-Host "JSON parse: OK" -ForegroundColor Green
            Write-Host "  Nodes: $($parsed.nodes.Count)"
            Write-Host "  Edges: $($parsed.edges.Count)"
        } catch {
            Write-Warning "Response is not valid JSON — grammar may need adjustment."
        }

    } catch {
        Write-Error "Request failed: $_"
        exit 1
    }
}
