# ROS 2 Labs (Windows)

Seventeen hands-on ROS 2 (Jazzy) projects. **Every lab is a complete, separate project** in its own folder under `labs\`: its own environment (`pixi.toml`), source code, scripts, automated test and manual (`README.md`). You can do any lab on its own, in any order; nothing is shared between them except the tools you install once.

## 1. Install two tools (once per computer)

Open **PowerShell** and run, then close and reopen PowerShell:

```powershell
winget install --id Git.Git -e --source winget
winget install --id prefix-dev.pixi -e --source winget
```

## 2. Get the labs

```powershell
git clone https://github.com/ursikigai/ros-labs.git ros-labs
cd ros-labs
```

Only want one lab? Download just that folder:

```powershell
git clone --filter=blob:none --sparse https://github.com/ursikigai/ros-labs.git ros-labs
cd ros-labs
git sparse-checkout set labs/Lab-02-robot-model
```

## 3. Run a lab

```powershell
cd labs\Lab-02-robot-model
```

Open that folder's **`README.md`** (or its PDF in `pdf\`) and follow it. Every manual starts with the same two commands, `pixi install` (downloads the lab's environment, minutes the first time) and `pixi run verify`, and then continues with the lab's own steps. The last step of each manual is a one-command automated check (`pixi run test-...`).

## The labs

| Folder (under `labs\`) | Project | Also needs | Time |
|---|---|---|---|
| **Course: build the robot step by step** | | | |
| `Lab-01-turtle-catcher` | Turtle Catcher: nodes, topics, services, parameters, launch | C++ compiler | 45 min |
| `Lab-02-robot-model` | DiffBot model: URDF, xacro, TF, RViz2 | | 45 min |
| `Lab-03-simulation-odometry` | Simulator and wheel odometry | | 90 min |
| `Lab-04-lidar-avoidance` | LiDAR obstacle avoidance | | 60 min |
| `Lab-05-autonomous-navigation` | A* planner + pure pursuit + actions | | 90 min |
| `Lab-06-nav2` | The real Nav2 stack | | 45 min |
| **Original public repositories, built and run unmodified** (downloaded by the lab at a pinned commit) | | | |
| `Lab-U1-packt-ros2-from-scratch` | Packt "ROS 2 from Scratch", chapter 9 (Python + C++) | C++ compiler | 90 min |
| `Lab-U2-turtlesim` | turtlesim built from source | C++ compiler | 45 min |
| `Lab-U3-urdf-tutorial` | the eight `urdf_tutorial` robots | | 45 min |
| `Lab-U4-nav2-custom-planner` | Your own planner inside Nav2 | C++ compiler | 60 min |
| `Lab-U5-gazebo-slam-docker` | Gazebo, SLAM and Nav2 in Docker | Docker Desktop | 30 min |
| **NVIDIA Isaac Sim (physics simulator)** | | | |
| `Lab-I1-isaac-drive` | Drive in Isaac Sim from ROS 2 | NVIDIA RTX GPU | 45 min |
| `Lab-I2-isaac-lidar` | LiDAR in Isaac Sim + obstacle avoider | NVIDIA RTX GPU | 30 min |
| `Lab-I3-isaac-camera` | Camera: follow a red cube | NVIDIA RTX GPU | 45 min |
| `Lab-I4-isaac-waypoints` | Waypoints | NVIDIA RTX GPU | 30 min |
| `Lab-I5-isaac-line-follower` | Line follower | NVIDIA RTX GPU | 30 min |
| `Lab-I6-isaac-ramp-imu` | Ramp and IMU | NVIDIA RTX GPU | 30 min |

"C++ compiler" = Visual Studio Build Tools with the *Desktop development with C++* workload (includes a Windows SDK). Labs without it are pure Python. The Isaac Sim labs need about 15 GB of disk for Isaac Sim, installed once into `C:\ix` and shared by all six.

## Good to know

* **Where things go.** Each lab's ROS environment is kept in `C:\rlabs` and its build files in `C:\rb`, not inside the cloned folder (this avoids Windows' 260-character path limit and lets you move or zip a lab folder freely). pixi shares downloaded packages between labs, so the second lab is much quicker than the first.
* **One lab at a time.** Labs use the same ROS network; stop everything (Ctrl+C) before starting another lab. To clear stuck programs: `Get-Process | Where-Object { $_.Path -like "C:\rlabs\*" -or $_.Path -like "C:\ix\*" } | Stop-Process -Force`.
* **Red text in PowerShell** that starts with `Pixi task (...)` is pixi's status line, not an error.
* **Self-test.** Each lab can replay its own manual: `powershell -NoProfile -File tools\replay.ps1 README.md` (from inside the lab folder; it opens windows, so leave the mouse alone).
* **PDFs.** `pdf\` has every manual as a PDF and `ROS2-Labs-All.pdf` with all of them (rebuild with `python tools\make_pdfs.py` after `pip install markdown`).
* **What was tested, and what was not:** see [TESTED.md](TESTED.md).
