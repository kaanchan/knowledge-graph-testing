# start-llama-server.ps1
# Starts llama-server (llama.cpp) with Phi-4 14B Q4_K_M on GPU, 16K context, port 8080.
#
# PREREQUISITES:
#   1. Download llama.cpp Windows CUDA binary (CUDA 12.x, x64) from:
#      https://github.com/ggerganov/llama.cpp/releases  (latest release, e.g. llama-b...-win-cuda12-x64.zip)
#      Extract to C:\Users\kaanchan\bin\llama.cpp\ so that llama-server.exe exists there.
#
#   2. Download Phi-4 14B Q4_K_M GGUF from Hugging Face:
#      https://huggingface.co/bartowski/phi-4-GGUF
#      File: phi-4-Q4_K_M.gguf
#      Save to D:\models\phi-4-Q4_K_M.gguf
#
# USAGE:
#   .\scripts\start-llama-server.ps1
#   Leave the terminal open — server runs in the foreground.
#   After startup, run scripts\test-endpoint.ps1 in a second terminal.

param(
    [string]$ModelPath   = "D:\Models\gguf\phi-4-Q4_K_M.gguf",
    [string]$ServerExe   = "C:\Users\kaanchan\bin\llama.cpp\llama-server.exe",
    [int]   $GpuLayers   = 99,
    [int]   $CtxSize     = 16384,
    [int]   $Port        = 8080
)

if (-not (Test-Path $ServerExe)) {
    Write-Error "llama-server.exe not found at: $ServerExe"
    Write-Error "Download from https://github.com/ggerganov/llama.cpp/releases and extract to D:\llama.cpp\"
    exit 1
}

if (-not (Test-Path $ModelPath)) {
    Write-Error "Model file not found at: $ModelPath"
    Write-Error "Download phi-4-Q4_K_M.gguf from https://huggingface.co/bartowski/phi-4-GGUF"
    exit 1
}

Write-Host "Starting llama-server..." -ForegroundColor Cyan
Write-Host "  Model:      $ModelPath"
Write-Host "  GPU layers: $GpuLayers"
Write-Host "  Context:    $CtxSize tokens"
Write-Host "  Port:       $Port"
Write-Host ""
Write-Host "Server will be available at: http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

& $ServerExe `
    -m $ModelPath `
    --n-gpu-layers $GpuLayers `
    --ctx-size $CtxSize `
    --port $Port `
    --host 127.0.0.1
