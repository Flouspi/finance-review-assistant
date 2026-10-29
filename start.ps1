param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$projectApp = Join-Path $PSScriptRoot 'app.py'

# Reuse only this project's running app. Never stop a process occupying a port.
$candidatePorts = 8501..8510
foreach ($candidatePort in $candidatePorts) {
    $listeners = @(Get-NetTCPConnection -LocalPort $candidatePort -State Listen -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if (-not $owner -or -not $owner.CommandLine) { continue }
        $usesProjectPython = $owner.CommandLine.IndexOf($projectPython, [StringComparison]::OrdinalIgnoreCase) -ge 0
        $appPattern = '(?i)\bstreamlit\s+run\s+(?:"?' + [regex]::Escape($projectApp) + '"?|"?app\.py"?)(?=\s|$)'
        if (-not $usesProjectPython -or $owner.CommandLine -notmatch $appPattern) { continue }
        $assistantUrl = "http://127.0.0.1:$candidatePort"
        try {
            $health = Invoke-WebRequest -Uri "$assistantUrl/_stcore/health" -UseBasicParsing -TimeoutSec 3
            if ($health.StatusCode -eq 200 -and $health.Content.Trim() -eq 'ok') {
                Write-Host "Assistant is already running. Open: $assistantUrl"
                if (-not $NoBrowser) { Start-Process $assistantUrl }
                exit 0
            }
        } catch { }
    }
}

$availablePort = $null
foreach ($candidatePort in $candidatePorts) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidatePort)
    try {
        $probe.Start()
        $availablePort = $candidatePort
    } catch {
        # Some other application owns this port; try the next one.
    } finally {
        $probe.Stop()
    }
    if ($null -ne $availablePort) { break }
}
if ($null -eq $availablePort) { throw 'Ports 8501-8510 are occupied. No running process has been stopped.' }

if (-not (Test-Path -LiteralPath $projectPython)) {
    python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
$dependenciesReady = $false
try {
    & $projectPython -c 'import langgraph, streamlit, yaml, httpx, dotenv, pypdf, docx' 2>$null
    $dependenciesReady = ($LASTEXITCODE -eq 0)
} catch {
    $dependenciesReady = $false
}
if (-not $dependenciesReady) {
    & $projectPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
Write-Host "Open this address after startup: http://127.0.0.1:$availablePort"
& $projectPython -m streamlit run $projectApp --server.address 127.0.0.1 --server.port $availablePort --server.headless true --browser.gatherUsageStats false
exit $LASTEXITCODE
