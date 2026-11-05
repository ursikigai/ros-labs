# Lab I2 - LiDAR in Isaac Sim, steered by a ready-made obstacle avoider

**Aim.** Give the Isaac Sim robot a 360 degree lidar that publishes a standard `sensor_msgs/LaserScan`, then drive it with the obstacle-avoider node that is part of this folder (`ws\src\diffbot_navigation`), which was written for a different, kinematic simulator and is used **unmodified**. The point: ROS 2 interfaces let you swap the simulator behind them.

**Time.** 30 min. **Needs.** Only this folder, an **NVIDIA RTX GPU** (tested: RTX 5050 Laptop, 8 GB, driver 592.82) and about 15 GB of disk for Isaac Sim, which `pixi run isaac-install` downloads once for all Isaac labs on the machine. By running the scripts you accept NVIDIA's Isaac Sim licence.

## This folder is a complete project

Everything this lab needs is in this folder. Nothing from the other labs is required.

**Requirements:** Windows 10/11, PowerShell, [pixi](https://pixi.sh) (`winget install --id prefix-dev.pixi -e --source winget`), and an NVIDIA RTX GPU with a current driver; about 15 GB disk for Isaac Sim (shared by all Isaac labs, installed once into `C:\ix`); internet for the first install.

| In this folder | |
|---|---|
| `isaac\` | the Isaac Sim scene scripts and ROS 2 nodes |
| `ws\src\` | the ROS 2 packages; `ws\install\` appears after `pixi run build` |
| `scripts\` | helper scripts and the automated tests |
| `pixi.toml` | the environment and every `pixi run ...` command; `README.md` this manual; `tools\replay.ps1` re-runs the manual's commands as a self-test |

**Set it up once.** `pixi install` puts ROS 2 Jazzy into `C:\rlabs` (a few GB; pixi's package cache makes the second lab on the same machine fast). Open PowerShell in this folder and run:

<!--run: fg timeout=2400 expect="PASS: rclpy pub/sub works" expect="packages? finished"-->
```powershell
pixi install
pixi run verify
pixi run build
```

(`pixi run build` compiles this lab's packages into `ws\install`; run it again after every edit in `ws\src`.)

Run one lab at a time, and everything from this folder.

## Theory

The scene is an 8 m x 6 m room (robot at the origin looking along +x) plus two 0.6 m boxes at (1.5, 1.0) and (-1.5, -1.0). A PhysX ray-casting lidar on `lidar_link` (8 cm ahead of the robot centre) has 720 rays (0.5 degree steps), range 0.12-6 m, and is published on `/scan`.

| | the kinematic simulator the avoider was written for | this lab |
|---|---|---|
| who moves the robot | kinematic Python simulator | Isaac Sim physics |
| `/scan` | 360 rays, 1 degree | **720 rays, 0.5 degree** |
| `/cmd_vel` consumer | `diffbot_sim` | OmniGraph differential controller |
| **the avoider** | `obstacle_avoider` | **the same node, no change** (it reads `angle_min` and `angle_increment` from every message, so the ray count does not matter) |

Expected scan at the start, from the geometry: straight ahead 4.00 - 0.08 = **3.92 m**, left and right **3.00 m**, behind 4.00 + 0.08 = **4.08 m** (a live window-mode read gave 3.90 / 3.00 / 4.10 because the robot had already drifted a few centimetres).

## Procedure

**1. T1 - Isaac Sim with the lidar** (a room with two boxes).

<!--run: bg ready="project 2 ready" wait=600-->
```powershell
pixi run isaac-p2 --gui
```

**2. T2 - check the scan against the room.** Index 360 is straight ahead, 540 left (+90 deg), 180 right (-90 deg), 0 behind (+-180 deg).

<!--run: fg expect="720" expect="front 3\.9\d"-->
```powershell
pixi run isaac-ros topic echo /scan --no-daemon --once --spin-time 5 --field angle_increment
$o = pixi run isaac-ros topic echo /scan --no-daemon --once --spin-time 5 --field ranges | Out-String
$r = [regex]::Match($o, '\[(.*?)\]').Groups[1].Value -split ',\s*'
"rays: $($r.Count)"
"front {0:N2}  left {1:N2}  back {2:N2}  right {3:N2}" -f [double]$r[360],[double]$r[540],[double]$r[0],[double]$r[180]
```

**3. T2 - rate of the scan** (messages per wall-clock second; stop it with Ctrl+C - here it stops itself after 30 s).

<!--run: stop=30 expect="average rate"-->
```powershell
pixi run isaac-ros topic hz /scan --spin-time 5
```

**4. T2 - start the obstacle avoider, unchanged.** (Build it once first with `pixi run build`.) The robot starts to wander and turns away from walls and boxes.

<!--run: bg wait=15-->
```powershell
pixi run isaac-avoider
```

**5. T3 - is it avoiding?** Position of the robot five times, 8 s apart (it should move through the room, never stop at a wall):

<!--run: fg timeout=180 expect="x: "-->
```powershell
1..5 | ForEach-Object { pixi run isaac-ros topic echo /odom --no-daemon --once --spin-time 5 --field pose.pose.position; Start-Sleep 8 }
```

<!--run: stopbg-->
```powershell
# Ctrl+C in T1 and T2
```

## Observations (recorded)

| Quantity | Value |
|---|---|
| Scan at the start | 720 rays, 0.5 degree steps (`angle_increment` 0.008727); front / left / back / right = 3.92 / 3.00 / 4.08 / 3.00 m; about 33 messages per wall-clock second |
| The avoider in Isaac Sim | 12.3-12.5 m driven in 60 simulated seconds; closest approach of the robot centre to any wall or box 0.46-0.58 m (robot radius about 0.17 m) |

## Verification (own headless Isaac Sim, 4-6 min; close T1 and T2 first)

<!--run: fg timeout=1200 expect="ALL PASSED"-->
```powershell
pixi run test-isaac-p2
```

9 checks: Isaac Sim publishes `/clock`, `/odom`, `/scan`; the scan is a full circle in frame `lidar_link`; the ranges at 0 / 90 / 180 / -90 degrees match the room to 12 cm; the unchanged avoider drives the robot more than 4 m in 60 simulated seconds, its centre never comes closer to a wall or box than the robot radius (0.17 m), and it stays inside the room.

## Questions

1. Why did the avoider need no change although `/scan` has twice as many rays? Which two fields of `LaserScan` make that work?
2. The measured front range is 3.92 m, not 4.00 m. Why?
3. A kinematic simulator can count collisions directly. How does this lab measure "did not hit" instead?
4. What would break if Isaac Sim published `/scan` in frame `base_link` instead of `lidar_link`?
5. *(Extension)* Add a third box in `isaac\scripts\p2_lidar.py` (`boxes=[...]`) and check the avoider still copes.

## If it does not work

| Symptom | Fix |
|---|---|
| `/scan` missing | wait for `project 2 ready`; `isaac-ros topic list --no-daemon --spin-time 5` |
| The robot does not move | `pixi run isaac-avoider` runs on domain 78 automatically; T1 must be Isaac project 2, not another project |
| The range line prints an error about `[double]` | the echo printed nothing: wait for `project 2 ready` and repeat |
