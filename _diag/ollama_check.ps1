[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host '=== OLLAMA HEALTH ==='
try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop
    Write-Host ("HTTP " + $r.StatusCode)
    $j = $r.Content | ConvertFrom-Json
    if ($j.models) {
        Write-Host 'models:'
        foreach ($m in $j.models) {
            Write-Host (" - {0,-40} size={1}" -f $m.name, $m.size)
        }
    } else {
        Write-Host 'no models listed'
    }
} catch {
    Write-Host ("OLLAMA UNREACHABLE: " + $_.Exception.Message)
}

Write-Host ''
Write-Host '=== AMNEZIA VPN (Telegram tunnel) ==='
$svc = Get-Service -Name 'AmneziaVPN-service' -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host ("service: " + $svc.Status + " (" + $svc.StartType + ")")
} else {
    Write-Host 'AmneziaVPN-service: NOT FOUND'
}

Write-Host ''
Write-Host '=== TELEGRAM REACHABILITY (149.154.167.99:443) ==='
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect('149.154.167.99', 443, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(4000, $false)
    if ($ok) {
        $tcp.EndConnect($iar)
        Write-Host 'TCP 149.154.167.99:443 - OK'
        $tcp.Close()
    } else {
        $tcp.Close()
        Write-Host 'TCP 149.154.167.99:443 - TIMEOUT (4s)'
    }
} catch {
    Write-Host ("TCP 149.154.167.99:443 - ERROR: " + $_.Exception.Message)
}

Write-Host ''
Write-Host '=== TELEGRAM REACHABILITY (api.telegram.org:443) ==='
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect('api.telegram.org', 443, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(4000, $false)
    if ($ok) {
        $tcp.EndConnect($iar)
        Write-Host 'TCP api.telegram.org:443 - OK'
        $tcp.Close()
    } else {
        $tcp.Close()
        Write-Host 'TCP api.telegram.org:443 - TIMEOUT (4s)'
    }
} catch {
    Write-Host ("TCP api.telegram.org:443 - ERROR: " + $_.Exception.Message)
}
