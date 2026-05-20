# test-endpoint.ps1
# Validates that llama-server is live and returning valid responses.
# Run AFTER start-llama-server.ps1 is running in a separate terminal.
#
# USAGE:
#   .\scripts\test-endpoint.ps1
#
# OUTPUTS:
#   - The model ID stem reported by /v1/models (use this value for OLLAMA_MODEL in run-graphify-llama.ps1)
#   - A minimal chat completion response to confirm the model is generating text

param(
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$headers = @{ "Content-Type" = "application/json" }

# ── TEST 1: GET /v1/models ────────────────────────────────────────────────────
Write-Host "=== TEST 1: GET /v1/models ===" -ForegroundColor Cyan
try {
    $modelsResponse = Invoke-RestMethod -Uri "$BaseUrl/v1/models" -Method GET -Headers $headers
    $modelId = $modelsResponse.data[0].id
    Write-Host "SUCCESS: Server is up." -ForegroundColor Green
    Write-Host ""
    Write-Host "Model ID reported by server: $modelId" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "ACTION REQUIRED: Use the model ID above as OLLAMA_MODEL in scripts\run-graphify-llama.ps1" -ForegroundColor Magenta
    Write-Host "  Example: `$env:OLLAMA_MODEL = `"$modelId`"" -ForegroundColor Magenta
    Write-Host ""
} catch {
    Write-Error "FAILED to reach /v1/models at $BaseUrl"
    Write-Error "Is llama-server running? Start it with: .\scripts\start-llama-server.ps1"
    Write-Error "Error: $_"
    exit 1
}

# ── TEST 2: POST /v1/chat/completions (minimal message) ──────────────────────
Write-Host "=== TEST 2: POST /v1/chat/completions ===" -ForegroundColor Cyan

$chatBody = @{
    model    = $modelId
    messages = @(
        @{
            role    = "user"
            content = "Reply with exactly: OK"
        }
    )
    max_tokens  = 16
    temperature = 0.0
} | ConvertTo-Json -Depth 10

try {
    $chatResponse = Invoke-RestMethod `
        -Uri "$BaseUrl/v1/chat/completions" `
        -Method POST `
        -Headers $headers `
        -Body $chatBody

    $reply = $chatResponse.choices[0].message.content
    Write-Host "SUCCESS: Chat completion returned." -ForegroundColor Green
    Write-Host "  Model used:   $($chatResponse.model)"
    Write-Host "  Reply:        $reply"
    Write-Host ""
} catch {
    Write-Error "FAILED to get chat completion from $BaseUrl/v1/chat/completions"
    Write-Error "Error: $_"
    exit 1
}

# ── SUMMARY ──────────────────────────────────────────────────────────────────
Write-Host "=== SUMMARY ===" -ForegroundColor Cyan
Write-Host "llama-server is live and responding." -ForegroundColor Green
Write-Host ""
Write-Host "Set these env vars before running graphify (or let run-graphify-llama.ps1 set them):" -ForegroundColor Yellow
Write-Host "  `$env:OLLAMA_BASE_URL  = `"http://127.0.0.1:8080/v1`""
Write-Host "  `$env:OLLAMA_MODEL     = `"$modelId`"   # <-- confirmed stem from /v1/models"
Write-Host "  `$env:GRAPHIFY_OLLAMA_NUM_CTX    = `"16384`""
Write-Host "  `$env:GRAPHIFY_API_TIMEOUT       = `"900`""
Write-Host "  `$env:GRAPHIFY_MAX_OUTPUT_TOKENS = `"4096`""
