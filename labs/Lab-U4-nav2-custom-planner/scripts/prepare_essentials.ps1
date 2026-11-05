# Prepare a Jazzy-compatible COPY of the Essentials repo's ROS packages (the clone in upstream\ stays untouched).
#
# robotics_essentials_ros2 targets ROS 2 *Humble*. In Jazzy, nav2_core::GlobalPlanner::createPlan gained a third
# argument (std::function<bool()> cancel_checker), so the repo's custom_nav2_planner plugin no longer compiles.
# This script copies packages\ to upstream_ws\essentials\src and applies exactly that one signature change.
# Usage (repo root):  powershell -File scripts\prepare_essentials.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "upstream\robotics_essentials_ros2\packages"
$dst = Join-Path $root "upstream_ws\essentials\src"
if (-not (Test-Path $src)) { throw "clone not found: $src" }
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item -Recurse -Force "$src\*" $dst

$hpp = Join-Path $dst "custom_nav2_planner\include\custom_nav2_planner\custom_nav2_planner.hpp"
$cpp = Join-Path $dst "custom_nav2_planner\src\custom_nav2_planner.cpp"

$h = [IO.File]::ReadAllText($hpp)
$h2 = [regex]::Replace($h, "(const geometry_msgs::msg::PoseStamped & goal)\) override;", "`$1,`r`n  std::function<bool()> cancel_checker) override;")
if ($h2 -eq $h) { throw "header patch did not apply" }
[IO.File]::WriteAllText($hpp, $h2)

$c = [IO.File]::ReadAllText($cpp)
$c2 = [regex]::Replace($c, "(CustomPlanner::createPlan\(\s*const geometry_msgs::msg::PoseStamped & start,\s*const geometry_msgs::msg::PoseStamped & goal)\)", "`$1,`r`n  std::function<bool()> cancel_checker)")
if ($c2 -eq $c) { throw "source patch did not apply" }
[IO.File]::WriteAllText($cpp, $c2)

Write-Host "patched copy ready: $dst"
