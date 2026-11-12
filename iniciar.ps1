<#
.SYNOPSIS
Prepara el frontend y arranca Acero Cifrado con un solo comando.
.EXAMPLE
.\iniciar.ps1
.EXAMPLE
.\iniciar.ps1 -Puerto 8001 -Dispositivo cpu
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Puerto = 8000,
    [ValidateSet('auto', 'cpu', 'cuda')][string]$Dispositivo = $(if ($env:ACERO_DEVICE) { $env:ACERO_DEVICE } else { 'auto' }),
    [string]$Modelo,
    [switch]$CompartirRed,
    [switch]$Verificar
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$previousModel = $env:ACERO_MODEL_PATH
$previousDevice = $env:ACERO_DEVICE
$exitCode = 0
Push-Location -LiteralPath $projectRoot
try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'Falta .venv. Prepara el entorno Python siguiendo README.md antes del primer arranque.'
    }
    if (-not $Modelo) {
        if ($env:ACERO_MODEL_PATH) { $Modelo = $env:ACERO_MODEL_PATH }
        elseif (Test-Path -LiteralPath 'model/best.pt' -PathType Leaf) { $Modelo = 'model/best.pt' }
        else { $Modelo = 'model/steel-defect-yolo11n.pt' }
    }
    if (-not [IO.Path]::IsPathRooted($Modelo)) { $Modelo = Join-Path $projectRoot $Modelo }
    if (-not (Test-Path -LiteralPath $Modelo -PathType Leaf)) {
        throw "No se encontraron los pesos: $Modelo. Usa -Modelo con un checkpoint existente. Para obtener los pesos de validacion: .\.venv\Scripts\python.exe tools/download_validation_model.py"
    }
    if ([IO.Path]::GetExtension($Modelo) -ne '.pt') { throw 'El modelo debe ser un checkpoint .pt de defectos.' }
    $env:ACERO_MODEL_PATH = (Resolve-Path -LiteralPath $Modelo).Path
    $env:ACERO_DEVICE = $Dispositivo

    Write-Host "`nAcero Cifrado | Preparando la estacion" -ForegroundColor Cyan
    Write-Host "Modelo: $($env:ACERO_MODEL_PATH)"
    Write-Host "Dispositivo: $Dispositivo"
    & $python -c "import uvicorn, fastapi, cv2, torch, ultralytics, sqlalchemy, fpdf, multipart; import os, sys; available=torch.cuda.is_available(); print('GPU: ' + torch.cuda.get_device_name(0) if available else 'CUDA no disponible; modo automatico usara CPU.'); sys.exit('Se solicito CUDA pero PyTorch no la tiene disponible.') if os.environ['ACERO_DEVICE']=='cuda' and not available else None"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo validar el entorno Python. Revisa el error anterior y requirements-dev.txt / requirements-cuda.txt.' }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw 'No se encontro npm. Instala Node.js (version probada: 24) y abre una terminal nueva.' }
    $installedLock = Join-Path $projectRoot 'frontend/node_modules/.package-lock.json'
    $sourceLock = Get-Item -LiteralPath 'frontend/package-lock.json'
    if (-not (Test-Path -LiteralPath $installedLock) -or $sourceLock.LastWriteTimeUtc -gt (Get-Item -LiteralPath $installedLock).LastWriteTimeUtc) {
        Write-Host 'Instalando las dependencias del frontend...'
        & $npm.Source --prefix frontend ci
        if ($LASTEXITCODE -ne 0) { throw 'Fallo npm ci. Revisa la conexion y el error anterior.' }
    }
    Write-Host 'Compilando la interfaz...'
    & $npm.Source --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar el frontend. El servidor no se iniciara.' }
    if ($Verificar) {
        Write-Host "`nPreparacion correcta. Frontend compilado, pesos encontrados y entorno disponible." -ForegroundColor Green
    }
    else {
        $address = if ($CompartirRed) { '0.0.0.0' } else { '127.0.0.1' }
        $url = "http://127.0.0.1:$Puerto"
        $listener = [Net.Sockets.TcpClient]::new()
        try { $portBusy = $listener.ConnectAsync('127.0.0.1', $Puerto).Wait(500) -and $listener.Connected }
        catch { $portBusy = $false }
        finally { $listener.Dispose() }
        if ($portBusy) {
            $sameApp = $false
            try {
                $health = Invoke-RestMethod "$url/health" -TimeoutSec 3
                $page = Invoke-WebRequest "$url/" -UseBasicParsing -TimeoutSec 3
                $localHtml = [IO.File]::ReadAllText((Join-Path $projectRoot 'frontend/dist/index.html'))
                $sameApp = $health.status -eq 'ok' -and $page.Content.Trim() -eq $localHtml.Trim()
            } catch { $sameApp = $false }
            if (-not $sameApp) { throw "El puerto $Puerto esta ocupado por otro proceso o una version anterior. Deten esa instancia o usa -Puerto 8001. No se cerro ningun proceso." }
            Write-Host "`nAcero Cifrado ya esta funcionando: $url" -ForegroundColor Green
            if (-not $health.model_loaded) { Write-Warning 'Esa instancia no tiene modelo cargado. Detenla y vuelve a ejecutar este comando.' }
            Write-Host 'Para cambiar modelo, dispositivo o acceso de red, deten primero la instancia existente.'
        }
        else {
            Write-Host "`nAbre $url | Detener: Ctrl+C" -ForegroundColor Green
            if ($CompartirRed) { Write-Host "Acceso LAN habilitado. En otro dispositivo usa la IP de esta computadora y el puerto $Puerto." }
            & $python -m uvicorn main:app --app-dir backend --host $address --port $Puerto
            $exitCode = $LASTEXITCODE
        }
    }
}
catch {
    Write-Host "`nNo se pudo iniciar Acero Cifrado: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}
finally {
    $env:ACERO_MODEL_PATH = $previousModel
    $env:ACERO_DEVICE = $previousDevice
    Pop-Location
}
exit $exitCode
