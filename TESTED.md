# What was tested, and how

**Machine:** Windows 11 Home (10.0.26200), 24 GB RAM, GeForce RTX 5050 Laptop GPU (8 GB, driver 592.82), Docker Desktop (WSL 2), pixi 0.81.0, Git 2.56, ROS 2 Jazzy (RoboStack), Python 3.12, Isaac Sim 5.1.

## Method

Each lab was tested **as a standalone project, from its own folder in this repository**: `pixi install` created its environment in `C:\rlabs`, and then every `powershell` block of the lab's `README.md` was run, in order, by the lab's own `tools\replay.ps1` in a fresh Windows PowerShell, exactly as a student types it. A block passes when it exits with code 0 (or fails, where the manual says it must) **and** prints the output the manual promises. Programs a manual starts in "T1" were started and stopped by the script. The Isaac Sim labs were replayed with the real window (`--gui`). Transcripts are in each lab's `build\replay\` (not committed).

| Lab | Blocks passed | Failed | Skipped | Replayed |
|---|---:|---:|---:|---|
| [Lab-01-turtle-catcher](labs/Lab-01-turtle-catcher/README.md) | 18 | 0 | 0 | 2026-11-04 21:40 |
| [Lab-02-robot-model](labs/Lab-02-robot-model/README.md) | 10 | 0 | 0 | 2026-11-05 11:31 |
| [Lab-03-simulation-odometry](labs/Lab-03-simulation-odometry/README.md) | 11 | 0 | 0 | 2026-11-04 21:44 |
| [Lab-04-lidar-avoidance](labs/Lab-04-lidar-avoidance/README.md) | 10 | 0 | 0 | 2026-11-04 21:52 |
| [Lab-05-autonomous-navigation](labs/Lab-05-autonomous-navigation/README.md) | 13 | 0 | 1 | 2026-11-04 21:58 |
| [Lab-06-nav2](labs/Lab-06-nav2/README.md) | 7 | 0 | 0 | 2026-11-04 22:10 |
| [Lab-I1-isaac-drive](labs/Lab-I1-isaac-drive/README.md) | 8 | 0 | 0 | 2026-11-05 10:00 |
| [Lab-I2-isaac-lidar](labs/Lab-I2-isaac-lidar/README.md) | 8 | 0 | 0 | 2026-11-05 10:05 |
| [Lab-I3-isaac-camera](labs/Lab-I3-isaac-camera/README.md) | 7 | 0 | 0 | 2026-11-05 10:09 |
| [Lab-I4-isaac-waypoints](labs/Lab-I4-isaac-waypoints/README.md) | 6 | 0 | 0 | 2026-11-05 10:12 |
| [Lab-I5-isaac-line-follower](labs/Lab-I5-isaac-line-follower/README.md) | 7 | 0 | 0 | 2026-11-05 10:16 |
| [Lab-I6-isaac-ramp-imu](labs/Lab-I6-isaac-ramp-imu/README.md) | 7 | 0 | 0 | 2026-11-05 10:20 |
| [Lab-U1-packt-ros2-from-scratch](labs/Lab-U1-packt-ros2-from-scratch/README.md) | 19 | 0 | 0 | 2026-11-05 08:52 |
| [Lab-U2-turtlesim](labs/Lab-U2-turtlesim/README.md) | 15 | 0 | 0 | 2026-11-05 10:24 |
| [Lab-U3-urdf-tutorial](labs/Lab-U3-urdf-tutorial/README.md) | 13 | 0 | 0 | 2026-11-05 09:00 |
| [Lab-U4-nav2-custom-planner](labs/Lab-U4-nav2-custom-planner/README.md) | 8 | 0 | 0 | 2026-11-05 09:06 |
| [Lab-U5-gazebo-slam-docker](labs/Lab-U5-gazebo-slam-docker/README.md) | 9 | 0 | 1 | 2026-11-05 11:38 |
| **Total** | **176** | **0** | **2** | |

"Skipped" blocks need a person (RViz2 click, opening a picture).


## Problems found by this testing (fixed before release)

* `scripts\in_upstream.bat` split arguments at `=` (broke `model:=...` and ROS remaps): fixed.
* `ros2 topic echo`, `param get` and `param list` need `--spin-time 5` without the ROS daemon: added everywhere.
* A catch-by-hand step in the Turtle Catcher lab always lost a race against the controller: the lab now starts the nodes one at a time first.
* `pixi run isaac-drive` counts wall-clock seconds while Isaac Sim runs faster than real time: the Isaac drive lab ships `code\drive_sim.py`, paced by `/clock`.
* Standalone packaging bugs found while testing the folders: a runner path one level too high, a fetch step that trusted an emptied clone, a PowerShell parse error and a wrong environment path in the Isaac launcher.

## Not tested

* **A machine with nothing installed.** Everything was already present here: `winget install` of Git and pixi, the first `pixi install` of a *brand-new* pixi cache, the very first Isaac Sim download (the labs reused the existing 10 GB install in `C:\ix`), the very first Docker image build (cached here) and Docker Desktop / WSL 2 / Visual Studio Build Tools / NVIDIA driver installation.
* **The labs that download from GitHub or Docker Hub** (U1-U5) were tested with working internet access; they need it once.
* **Docker lab (U5) timing:** headless Gazebo sometimes fails to start inside the container; the lab's runner retries such a stage once. The recorded run passed all stages.
* **Anything that needs a mouse:** clicking *Nav2 Goal* in RViz2, dragging joint sliders, judging pictures in RViz2, Isaac Sim and the SLAM map.
* **The open exercises** (write your own planner, add a camera link, ...). Only the ones with a shipped solution are tested (`code\` folders).
* **Numbers in the "Observations" tables** come from single runs; spawn positions, physics and timing change them a little. The "Verification" tests use tolerances for that.
* Other machines: a different GPU/driver (Isaac Sim 5.1 has reported crashes on some RTX 50 combinations), other Docker memory settings, non-Windows systems.
