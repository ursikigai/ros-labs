# Install Isaac Sim (about 10 GB) into C:\ix unless some lab on this machine has already done it.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
function Find-IsaacEnv {
    foreach ($d in Get-ChildItem "C:\ix" -Directory -ErrorAction SilentlyContinue) {
        foreach ($c in @((Join-Path $d.FullName "envs\default"), $d.FullName)) {
            if (Test-Path (Join-Path $c "Lib\site-packages\isaacsim")) { return $c }
        }
    }
}
$found = Find-IsaacEnv
if ($found) { Write-Host "Isaac Sim is already installed: $found"; exit 0 }
Write-Host "Installing Isaac Sim 5.1 into C:\ix (about 10 GB; you accept NVIDIA's licence by using it) ..."
pixi install --manifest-path (Join-Path $root "isaac\pixi.toml")
exit $LASTEXITCODE
