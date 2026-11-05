# Run a Python script inside Isaac Sim with the ROS 2 (Jazzy) bridge wired up.
#   powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p1_drive.py [script args]
# Isaac Sim (Python 3.11) lives in its own environment under C:\ix, SHARED by every Isaac lab on this machine, because the
# download is about 10 GB. `pixi run isaac-install` creates it if no lab has done so yet. It talks to ROS 2 (Python 3.12) over DDS.
# The script gives Isaac Sim a CLEAN environment (fresh Windows PATH, no conda/ROS variables): Isaac's own Jazzy DLLs must not
# be mixed with the conda ones.
param([Parameter(Mandatory = $true, Position = 0)][string]$Script, [Parameter(ValueFromRemainingArguments = $true)]$ScriptArgs)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Find-IsaacEnv {   # pixi keeps the environment in C:\ix\<name>-<hash>\envs\default
    foreach ($d in Get-ChildItem "C:\ix" -Directory -ErrorAction SilentlyContinue) {
        foreach ($c in @((Join-Path $d.FullName "envs\default"), $d.FullName)) {
            if ((Test-Path (Join-Path $c "python.exe")) -and (Test-Path (Join-Path $c "Lib\site-packages\isaacsim"))) { return $c }
        }
    }
}
$envRoot = Find-IsaacEnv
if (-not $envRoot) { throw "Isaac Sim is not installed under C:\ix. Run: pixi run isaac-install" }
$envDir = [pscustomobject]@{ FullName = $envRoot }
$py = Join-Path $envDir.FullName "python.exe"

$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
foreach ($v in @(Get-ChildItem Env: | Where-Object { $_.Name -match '^(CONDA|PIXI|AMENT|COLCON|ROS_|RMW_|PYTHON|CMAKE_PREFIX|OMNI_KIT)' })) {
    Remove-Item "Env:$($v.Name)"
}
# what conda's activation would add
$env:Path = "$($envDir.FullName);$($envDir.FullName)\Library\mingw-w64\bin;$($envDir.FullName)\Library\usr\bin;$($envDir.FullName)\Library\bin;$($envDir.FullName)\Scripts;$env:Path"
$sitePackages = (& $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" | Select-Object -Last 1).Trim()
$bridgeLib = Join-Path $sitePackages "isaacsim\exts\isaacsim.ros2.bridge\jazzy\lib"
if (-not (Test-Path $bridgeLib)) { throw "Isaac Sim ROS 2 bridge libraries not found at $bridgeLib. Run: pixi run isaac-install" }
$env:Path = "$env:Path;$bridgeLib"
$env:ROS_DISTRO = "jazzy"
$env:RMW_IMPLEMENTATION = "rmw_fastrtps_cpp"
$env:ROS_DOMAIN_ID = "78"             # the ROS 2 side uses the same domain
$env:OMNI_KIT_ACCEPT_EULA = "YES"     # by running the labs you accept the NVIDIA Isaac Sim licence
& $py -u (Join-Path $root $Script) @ScriptArgs
exit $LASTEXITCODE
