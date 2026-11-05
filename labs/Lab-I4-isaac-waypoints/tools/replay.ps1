# Replay the commands of a lab manual and check them -- the manuals are tested with this very script.
#
#   powershell -NoProfile -File lab-manuals\tools\replay.ps1 lab-manuals\Lab-03-simulation-odometry.md
#   powershell -NoProfile -File lab-manuals\tools\replay.ps1 -All
#
# Every ```powershell block of a manual is run, in order, in a fresh PowerShell from the repository root.
# A comment right before a block tells the script how:
#   <!--run: bg ready="regex" wait=120-->   long-running (a "terminal 1" command): start it, wait until its output matches
#                                           the regex, keep it running for the following blocks; killed at the end of the manual
#   <!--run: fg timeout=120 expect="regex"-->  (default) run to the end, must exit 0 and (if given) the output must match
#   <!--run: fg expectfail ...-->           like fg, but the command is supposed to fail (exit code not 0)
#   <!--run: stop=15 expect="regex"-->      a command that never ends (topic hz ...): run N seconds, then stop it
#   <!--run: stopbg-->                      "press Ctrl+C in T1": stops the background commands started so far (block holds only a comment)
#   <!--run: skip-->                        not replayed (needs a human: GUI clicks, installers)
# expect="..." may be repeated; reject="regex" means the output must NOT contain it. Output of every block goes to build\replay\<manual>.log.
param([Parameter(Position = 0)][string]$Manual, [switch]$All, [string]$Only = "")
$ErrorActionPreference = "Continue"
$Repo = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $Repo "build\replay"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$env:PYTHONUNBUFFERED = "1"

function Stop-Everything {
    # Kill every process started from inside the project (pixi environment, overlays), the lab environments (C:\rlabs) and Isaac Sim (C:\ix).
    Get-Process | Where-Object { $_.Path -and ($_.Path -like "*ros2-pbl-course*" -or $_.Path -like "C:\ix\*" -or $_.Path -like "C:\rlabs\*") } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Parse-Attrs([string]$s) {
    $a = @{}; $a["expect"] = @()
    foreach ($m in [regex]::Matches($s, '(\w+)(?:=(?:"([^"]*)"|(\S+)))?')) {
        $k = $m.Groups[1].Value; $v = if ($m.Groups[2].Success) { $m.Groups[2].Value } else { $m.Groups[3].Value }
        if ($k -eq "expect") { $a["expect"] += $v } else { $a[$k] = $v }
    }
    $a
}

function Start-Block([string]$code, [string]$log, [string]$tmp) {
    $body = New-Object System.Collections.Generic.List[string]
    $body.Add("Set-Location '$Repo'")
    $n = 0
    foreach ($line in ($code -split "`r?`n")) {
        $n++
        if ($line.Trim() -eq "" -or $line.Trim().StartsWith("#")) { continue }
        $body.Add('$global:LASTEXITCODE = 0')
        $body.Add($line)
        $body.Add("if (`$LASTEXITCODE -ne 0) { Write-Output (`"[command failed: exit `" + `$LASTEXITCODE + `"] (line $n)`"); exit 1 }")
    }
    Set-Content -Path $tmp -Value $body -Encoding UTF8
    Start-Process -FilePath cmd.exe -ArgumentList "/c powershell -NoProfile -ExecutionPolicy Bypass -File `"$tmp`" > `"$log`" 2>&1" -PassThru -WindowStyle Hidden
}

function Read-Log([string]$log) {
    # the writer (cmd redirect) still has the file open, so share it for reading
    try {
        $fs = New-Object IO.FileStream($log, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try { (New-Object IO.StreamReader($fs)).ReadToEnd() } finally { $fs.Dispose() }
    } catch { "" }
}

function Replay-Manual([string]$path) {
    $name = [IO.Path]::GetFileNameWithoutExtension($path)
    $text = Get-Content $path -Raw
    $blocks = [regex]::Matches($text, '(?s)(?:<!--run:\s*(.*?)-->\s*)?```powershell\r?\n(.*?)```')
    $transcript = Join-Path $OutDir "$name.log"
    Set-Content $transcript "Replay of $path   $(Get-Date -Format s)`n" -Encoding UTF8
    Stop-Everything
    $bg = @(); $pass = 0; $fail = 0; $skip = 0; $i = 0
    foreach ($b in $blocks) {
        $i++
        $attrs = if ($b.Groups[1].Success) { Parse-Attrs $b.Groups[1].Value } else { @{ expect = @() } }
        $code = $b.Groups[2].Value
        $log = Join-Path $OutDir "$name.block$i.txt"; $tmp = Join-Path $OutDir "$name.block$i.ps1"
        $head = ($code -split "`r?`n" | Where-Object { $_.Trim() -ne "" -and -not $_.Trim().StartsWith("#") } | Select-Object -First 1)
        Add-Content $transcript "`n--- block $i : $head"
        if ($attrs.ContainsKey("skip")) { $skip++; Add-Content $transcript "SKIP"; continue }
        if ($attrs.ContainsKey("stopbg")) {   # "press Ctrl+C in T1"
            foreach ($q in $bg) { if (-not $q.HasExited) { taskkill /PID $q.Id /T /F | Out-Null } }
            $bg = @(); Stop-Everything; $pass++; Add-Content $transcript "STOP background commands => PASS"
            Write-Host ("  block {0,2}  PASS  (stop the background commands)" -f $i); continue
        }
        $ok = $true; $why = ""
        $p = Start-Block $code $log $tmp
        if ($attrs.ContainsKey("bg")) {
            $wait = if ($attrs["wait"]) { [int]$attrs["wait"] } else { 120 }
            $ready = $attrs["ready"]; $sw = [Diagnostics.Stopwatch]::StartNew(); $up = $false
            while ($sw.Elapsed.TotalSeconds -lt $wait) {
                Start-Sleep -Seconds 2
                if ($ready) { if ((Read-Log $log) -match $ready) { $up = $true; break } } elseif ($sw.Elapsed.TotalSeconds -ge 8) { $up = $true; break }
                if ($p.HasExited) { break }
            }
            if (-not $up) { $ok = $false; $why = "background command not ready (/$ready/) within ${wait}s" }
            $bg += $p
        } elseif ($attrs.ContainsKey("stop")) {
            Start-Sleep -Seconds ([int]$attrs["stop"])
            if (-not $p.HasExited) { taskkill /PID $p.Id /T /F | Out-Null }
            Start-Sleep -Seconds 1
        } else {
            $to = if ($attrs["timeout"]) { [int]$attrs["timeout"] } else { 120 }
            if (-not $p.WaitForExit($to * 1000)) { taskkill /PID $p.Id /T /F | Out-Null; $ok = $false; $why = "timeout after ${to}s" }
            elseif ($attrs.ContainsKey("expectfail")) { if ($p.ExitCode -eq 0) { $ok = $false; $why = "was expected to fail but exited 0" } }
            elseif ($p.ExitCode -ne 0) { $ok = $false; $why = "exit code $($p.ExitCode)" }
            Start-Sleep -Milliseconds 500
        }
        $out = Read-Log $log
        foreach ($rx in $attrs["expect"]) { if ($out -notmatch $rx) { $ok = $false; $why += " expected /$rx/ not found" } }
        if ($attrs["reject"] -and $out -match $attrs["reject"]) { $ok = $false; $why += " found unwanted /$($attrs['reject'])/" }
        $show = ($out -split "`r?`n" | Select-Object -First 40) -join "`n"
        Add-Content $transcript $show
        if ($ok) { $pass++; Add-Content $transcript "=> PASS" } else { $fail++; Add-Content $transcript "=> FAIL: $why" }
        Write-Host ("  block {0,2}  {1,-5} {2}" -f $i, $(if ($ok) { "PASS" } else { "FAIL" }), $head)
        if (-not $ok) { Write-Host "           $why" }
    }
    foreach ($p in $bg) { if (-not $p.HasExited) { taskkill /PID $p.Id /T /F | Out-Null } }
    Stop-Everything
    Write-Host ("{0}: {1} passed, {2} failed, {3} skipped" -f $name, $pass, $fail, $skip)
    Add-Content $transcript "`nSUMMARY: $pass passed, $fail failed, $skip skipped"
    [pscustomobject]@{ Manual = $name; Pass = $pass; Fail = $fail; Skip = $skip }
}

$files = if ($All) { Get-ChildItem (Join-Path $Repo "lab-manuals") -Filter "Lab-*.md" | Sort-Object Name | ForEach-Object { $_.FullName } } else { @((Resolve-Path $Manual).Path) }
if ($Only) { $files = $files | Where-Object { $_ -match $Only } }
$results = foreach ($f in $files) { Write-Host "== $([IO.Path]::GetFileName($f))"; Replay-Manual $f }
$bad = ($results | Measure-Object -Property Fail -Sum).Sum
Write-Host ("TOTAL: {0} passed, {1} failed, {2} skipped" -f ($results | Measure-Object -Property Pass -Sum).Sum, $bad, ($results | Measure-Object -Property Skip -Sum).Sum)
exit ([int]($bad -gt 0))
