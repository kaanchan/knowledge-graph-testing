# run-graphify-llama.ps1
# Path A — Run graphify against llama-server (Phi-4 14B) with JSON schema enforcement.
# Step 1, GH issue #3 (ref #8)
#
# PREREQUISITES:
#   1. llama-server must be running (start-llama-server.ps1 in a separate terminal)
#   2. Run test-endpoint.ps1 first to confirm the server is live and get OLLAMA_MODEL stem
#   3. uv must be installed and graphify must be in your project dependencies
#
# IMPORTANT: confirm OLLAMA_MODEL stem from Step 0 /v1/models output before running.
#   Run: .\scripts\test-endpoint.ps1
#   Look for "Model ID reported by server: <id>" and set $env:OLLAMA_MODEL below.
#
# USAGE:
#   .\scripts\run-graphify-llama.ps1 -Directory <path-to-ralph-codebase>
#
#   Example:
#     .\scripts\run-graphify-llama.ps1 -Directory "C:\Projects\ralph"
#
# OUTPUT:
#   graphify writes its output JSON to the current working directory or per its --output flag.
#   After running, validate output with: python scripts\validate_graphify_output.py

param(
    [Parameter(Mandatory = $true)]
    [string]$Directory,

    [string]$OllamaBaseUrl          = "http://127.0.0.1:8080/v1",
    [string]$OllamaModel            = "phi-4",           # CONFIRM: run test-endpoint.ps1 first
    [string]$GraphifyOllamNumCtx    = "16384",
    [string]$GraphifyApiTimeout     = "900",
    [string]$GraphifyMaxOutputTokens = "4096"
)

# ── Validate prerequisites ────────────────────────────────────────────────────

if (-not (Test-Path $Directory)) {
    Write-Error "Target directory not found: $Directory"
    exit 1
}

# Quick server health check before proceeding
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:8080/v1/models" -Method GET -TimeoutSec 5
} catch {
    Write-Error "llama-server is not responding at $OllamaBaseUrl"
    Write-Error "Start it first with: .\scripts\start-llama-server.ps1"
    exit 1
}

# ── Set environment variables ─────────────────────────────────────────────────
# These env vars are read by graphify's llm.py (OLLAMA_BASE_URL redirects to llama-server)

$env:OLLAMA_BASE_URL             = $OllamaBaseUrl
$env:OLLAMA_MODEL                = $OllamaModel
$env:GRAPHIFY_OLLAMA_NUM_CTX     = $GraphifyOllamNumCtx
$env:GRAPHIFY_API_TIMEOUT        = $GraphifyApiTimeout
$env:GRAPHIFY_MAX_OUTPUT_TOKENS  = $GraphifyMaxOutputTokens

Write-Host "=== graphify → llama-server (Path A, Step 1) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Environment:"
Write-Host "  OLLAMA_BASE_URL            = $env:OLLAMA_BASE_URL"
Write-Host "  OLLAMA_MODEL               = $env:OLLAMA_MODEL"
Write-Host "  GRAPHIFY_OLLAMA_NUM_CTX    = $env:GRAPHIFY_OLLAMA_NUM_CTX"
Write-Host "  GRAPHIFY_API_TIMEOUT       = $env:GRAPHIFY_API_TIMEOUT"
Write-Host "  GRAPHIFY_MAX_OUTPUT_TOKENS = $env:GRAPHIFY_MAX_OUTPUT_TOKENS"
Write-Host ""
Write-Host "Target directory: $Directory" -ForegroundColor Yellow
Write-Host ""

# ── Run graphify ──────────────────────────────────────────────────────────────
# --backend ollama: uses OLLAMA_BASE_URL + OLLAMA_MODEL env vars
# --directory: path to codebase slice to analyse

Write-Host "Running graphify..." -ForegroundColor Cyan
uv run graphify --backend ollama --directory $Directory

if ($LASTEXITCODE -ne 0) {
    Write-Error "graphify exited with code $LASTEXITCODE"
    Write-Error "Check server logs in the llama-server terminal."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "graphify completed." -ForegroundColor Green
Write-Host ""
Write-Host "Next: validate the output JSON:"
Write-Host "  python scripts\validate_graphify_output.py --input <graphify-output.json>"
Write-Host ""
Write-Host "SUCCESS GATE: >= 1 edge per file, all node IDs match ^[a-z0-9_]+$, confidence enum populated."
Write-Host "If gate NOT met -> proceed to Step 2 (GBNF grammar fallback): .\scripts\start-llama-server-grammar.ps1"
