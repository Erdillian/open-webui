#Requires -Version 7
# Lance le backend Open WebUI + frontend pour le User Journey memory_layer
# Les paramètres principaux (PORT, DATABASE_URL, CHROMA_DATA_PATH) sont lus depuis .env

$ErrorActionPreference = "Stop"

# Configuration
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RepoRoot "backend"
$BackendLog = Join-Path $RepoRoot "backend_user_journey.log"
$BackendLogErr = Join-Path $RepoRoot "backend_user_journey_err.log"

# Variables d'environnement (complètent le .env)
$env:ENV = "test"
$env:ENABLE_MEMORIES = "true"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:PYTHONIOENCODING = "utf-8"
# Forcer UTF-8 sur stdout/stderr pour éviter les erreurs d'encodage Windows
$null = [System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Open WebUI - User Journey Launcher" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Vérifier qu'Ollama répond
Write-Host "`n[1/4] Verification d'Ollama..." -ForegroundColor Cyan
try {
    $OllamaModels = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    Write-Host "  Ollama est demarre." -ForegroundColor Green
    $HasEmbed = $OllamaModels.models.name -contains "nomic-embed-text:latest"
    if (-not $HasEmbed) {
        Write-Warning "  Le modele nomic-embed-text:latest n'est pas telecharge. La couche memoire risque de ne pas fonctionner."
    }
}
catch {
    Write-Host "  ERREUR : Ollama ne repond pas sur http://localhost:11434." -ForegroundColor Red
    Write-Host "  Demarre Ollama avec : ollama serve" -ForegroundColor Yellow
    Read-Host "Appuie sur Entree pour fermer"
    exit 1
}

# Vérifier le venv Python
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "  ERREUR : Venv Python introuvable : $PythonExe" -ForegroundColor Red
    Read-Host "Appuie sur Entree pour fermer"
    exit 1
}
Write-Host "  Python OK : $PythonExe" -ForegroundColor Green

# Lire le port depuis .env (fallback 8081)
$Port = 8081
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^PORT\s*=\s*(\d+)') {
            $Port = [int]$Matches[1]
            break
        }
    }
}

# Nettoyer les anciens logs
if (Test-Path $BackendLog) { Remove-Item $BackendLog -Force }
if (Test-Path $BackendLogErr) { Remove-Item $BackendLogErr -Force }

Write-Host "`n[2/4] Backend dir : $BackendDir" -ForegroundColor Cyan
Write-Host "[3/4] Demarrage du backend sur le port $Port..." -ForegroundColor Cyan
Write-Host "  Logs : $BackendLog" -ForegroundColor Gray

$BackendProc = Start-Process -FilePath $PythonExe `
    -ArgumentList "-m uvicorn open_webui.main:app --host 0.0.0.0 --port $Port" `
    -WorkingDirectory $BackendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendLogErr `
    -PassThru

# Attendre que le backend soit prêt
$MaxWait = 120
$Elapsed = 0
$Ready = $false
while ($Elapsed -lt $MaxWait) {
    Start-Sleep -Seconds 2
    $Elapsed += 2
    try {
        $Health = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 3
        if ($Health.status -eq "ok" -or $Health -match "ok") {
            $Ready = $true
            break
        }
    }
    catch {
        # Attendre
    }
    Write-Host "  Attente du backend... ($Elapsed s)" -ForegroundColor Yellow
}

if (-not $Ready) {
    Write-Host "`n  ERREUR : Le backend n'a pas demarre dans les $MaxWait secondes." -ForegroundColor Red
    Write-Host "  Consulte le log : $BackendLog" -ForegroundColor Yellow
    if (-not $BackendProc.HasExited) { $BackendProc.Kill() }
    Read-Host "Appuie sur Entree pour fermer"
    exit 1
}

Write-Host "  Backend PRET !" -ForegroundColor Green

# Ouvrir le navigateur
$Url = "http://localhost:$Port"
Write-Host "`n[4/4] Ouverture du navigateur sur $Url..." -ForegroundColor Cyan
Start-Process $Url

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Application disponible sur :" -ForegroundColor Green
Write-Host "  $Url" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nConnecte-toi avec :" -ForegroundColor White
Write-Host "  Email : admin@local.dev" -ForegroundColor White
Write-Host "  Mot de passe : admin123" -ForegroundColor White
Write-Host "`nPuis dis-moi 'je commence le User Journey'." -ForegroundColor White
Write-Host "Pour arreter, ferme cette fenetre ou fais Ctrl+C." -ForegroundColor Gray
Write-Host "`n--- Logs backend (temps reel) ---" -ForegroundColor Cyan

# Afficher les logs en temps réel
try {
    Get-Content $BackendLog, $BackendLogErr -Wait -Tail 0
}
finally {
    if (-not $BackendProc.HasExited) {
        Write-Host "`nArret du backend..." -ForegroundColor Yellow
        $BackendProc.Kill()
    }
}
