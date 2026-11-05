# Fetch an upstream repository at a pinned commit into upstream\<dir> (skips if it is already there).
#   powershell -NoProfile -File scripts\fetch_upstream.ps1 <dir> <url> <commit>
param([Parameter(Mandatory = $true)][string]$Dir, [Parameter(Mandatory = $true)][string]$Url, [Parameter(Mandatory = $true)][string]$Rev)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $root "upstream\$Dir"
if ((Test-Path (Join-Path $dst ".git")) -and (@(Get-ChildItem $dst -Force | Where-Object { $_.Name -ne ".git" }).Count -gt 0)) { Write-Host "already fetched: $dst"; exit 0 }
if (Test-Path $dst) { cmd /c "attrib -r `"$dst\*`" /s /d >nul 2>&1 & rmdir /s /q `"$dst`"" }   # a half-finished earlier fetch
New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
git -c core.autocrlf=false init -q $dst
git -C $dst remote add origin $Url
git -C $dst -c core.autocrlf=false fetch -q --depth 1 origin $Rev
if ($LASTEXITCODE -ne 0) { throw "git fetch of $Url ($Rev) failed" }
git -C $dst -c core.autocrlf=false checkout -q FETCH_HEAD
Write-Host "fetched $Url at $Rev into $dst"
