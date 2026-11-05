# Run one stage (or all) of the Essentials exercise tests in the headless container.
#   powershell -File scripts\docker\run_essentials_docker.ps1 -Stage sim
#   powershell -File scripts\docker\run_essentials_docker.ps1 -Stage all
# Headless Gazebo in software rendering sometimes fails to come up at all ("Gazebo finished loading" fails and nothing else is
# checked). That is a start-up flake, not a result, so a stage whose Gazebo never started is run ONCE more.
param([string]$Stage = "all", [string]$Image = "robotics_essentials_ros2:headless", [int]$TimeoutSec = 1200)
$ErrorActionPreference = "Continue"
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$tests = Join-Path $root "scripts\docker"
$out = Join-Path $root "build\docker_out"
New-Item -ItemType Directory -Force $out | Out-Null

$stages = if ($Stage -eq "all") { @("sim", "odometry", "slam", "nav") } else { @($Stage) }
$failed = 0
foreach ($s in $stages) {
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        Write-Host "=== stage: $s ===" $(if ($attempt -gt 1) { "(second try: Gazebo did not start the first time)" })
        $name = "essentials_$s"
        docker rm -f $name 2>$null | Out-Null
        $log = Join-Path $out "stage_$s.txt"
        # docker run is started as a child so a hung stage can be killed after $TimeoutSec
        $p = Start-Process -FilePath "docker" -ArgumentList @("run", "--rm", "--name", $name,
            "-v", "${tests}:/tests:ro", "-v", "${out}:/out", $Image,
            "bash", "/tests/run_stage.sh", $s) `
            -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        $timedOut = $false
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            Write-Host "TIMEOUT after $TimeoutSec s: stopping container $name"
            docker rm -f $name 2>$null | Out-Null
            $timedOut = $true
        }
        # Start-Process often leaves ExitCode empty; the stage script prints the checks' exit code itself.
        $m = Select-String -Path $log -Pattern '\[stage .*\] checks exit code (\d+)' | Select-Object -Last 1
        $ok = ($m -and $m.Matches[0].Groups[1].Value -eq "0" -and -not $timedOut)
        $gazeboNeverStarted = [bool](Select-String -Path $log -Pattern '^FAIL\s+Gazebo finished loading' -Quiet)
        if (-not $ok -and $gazeboNeverStarted -and $attempt -eq 1) { continue }   # start-up flake: try once more
        Get-Content $log | Where-Object { $_ -match '^(===|PASS|FAIL|---|\[stage|distance|odom|gazebo|final|real-time)' -or $_ -match 'RTF' }
        if (-not $ok) { $failed++ }
        break
    }
}
Write-Host "stages with problems: $failed"
exit $failed
