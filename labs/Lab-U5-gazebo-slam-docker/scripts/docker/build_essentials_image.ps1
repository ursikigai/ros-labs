# Build the Docker images for the Robotics & ROS 2 Essentials repository, exactly as the repo defines them.
#   pixi run build-essentials-docker
#
# Why a second clone: with Git's default core.autocrlf=true on Windows, every text file in the repo is checked out
# with CRLF line endings. Then each package name in docker/andino_requirements.txt ends in an invisible \r and
# `apt-get install` answers "Unable to locate package" for all of them, and ros_entrypoint.sh cannot start.
# So the Docker build uses a clone made with core.autocrlf=false (same commit); the original clone is not touched.
$ErrorActionPreference = "Stop"
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

# 1. Docker engine (Docker Desktop with the WSL 2 backend)
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "starting Docker Desktop ..."
    docker desktop start | Out-Null
    for ($i = 0; $i -lt 30; $i++) { Start-Sleep 5; docker info *> $null; if ($LASTEXITCODE -eq 0) { break } }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "Docker engine did not start. Is Docker Desktop installed (winget install Docker.DockerDesktop)?" }
}

# 2. LF clone of the repository
$clone = "upstream\robotics_essentials_ros2-lf"
if (-not (Test-Path "$clone\docker\Dockerfile")) {
    # an interrupted earlier clone leaves an empty folder: remove it first
    if (Test-Path $clone) { cmd /c "attrib -r `"$clone\*`" /s /d >nul 2>&1 & rmdir /s /q `"$clone`"" }
    git -c core.autocrlf=false clone --depth 1 https://github.com/henki-robotics/robotics_essentials_ros2 $clone
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}

# 3. the repo's own image (about 6.5 GB; the first build takes tens of minutes)
Push-Location $clone
docker build -f docker/Dockerfile -t robotics_essentials_ros2 .
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "docker build of the repository's image failed" }
Pop-Location

# 4. the thin headless layer (adds only Xvfb)
docker build -t robotics_essentials_ros2:headless -f scripts/docker/Dockerfile.headless scripts/docker
if ($LASTEXITCODE -ne 0) { throw "docker build of the headless layer failed" }
Write-Host "images ready: robotics_essentials_ros2 and robotics_essentials_ros2:headless"
