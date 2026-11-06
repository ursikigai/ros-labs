# Lab I3 - Camera in Isaac Sim: steer towards a red cube by its colour

**Aim.** Add an RGB + depth camera to the Isaac Sim robot and run a small ROS 2 node that finds a red cube in the image, turns the robot towards it, drives up to it and stops 0.55 m in front, using the depth image to measure the distance. A green cube is a decoy.

**Time.** 45 min. **Needs.** Only this folder, an **NVIDIA RTX GPU** (tested: RTX 5050 Laptop, 8 GB, driver 592.82) and about 15 GB of disk for Isaac Sim, which `pixi run isaac-install` downloads once for all Isaac labs on the machine. By running the scripts you accept NVIDIA's Isaac Sim licence.

## This folder is a complete project

Everything this lab needs is in this folder. Nothing from the other labs is required.

**Requirements:** Windows 10/11, PowerShell, [pixi](https://pixi.sh) (no administrator rights needed; install steps are in [README-SETUP.md](README-SETUP.md)), and an NVIDIA RTX GPU with a current driver; about 15 GB disk for Isaac Sim (shared by all Isaac labs, installed once into `C:\ix`); internet for the first install.

| In this folder | |
|---|---|
| `isaac\` | the Isaac Sim scene scripts and ROS 2 nodes |
| `scripts\` | helper scripts and the automated tests |
| `pixi.toml` | the environment and every `pixi run ...` command; `README.md` this manual; `tools\replay.ps1` re-runs the manual's commands as a self-test |

**Set it up once.** `pixi install` puts ROS 2 Jazzy into `C:\rlabs` (a few GB; pixi's package cache makes the second lab on the same machine fast). Open PowerShell in this folder and run:

<!--run: fg timeout=2400 expect="PASS: rclpy pub/sub works"-->
```powershell
pixi install
pixi run verify
```

Run one lab at a time, and everything from this folder.

## Theory

* Camera on the front of the body, 320 x 240 pixels, 90 degree field of view. Topics: `/camera/image_raw` (`sensor_msgs/Image`, `rgb8`: 3 bytes per pixel) and `/camera/depth` (`32FC1`: one float, metres, per pixel).
* The ROS 2 node `isaac\ros_nodes\color_follower.py` (about 60 lines, numpy only) does, per image:
  1. a pixel is **red** if `R > 120`, `R - G > 70`, `R - B > 70`;
  2. `error = (mean column of red pixels - centre) / half-width`, in -1 ... +1 (negative = target on the left);
  3. turn `w = -1.2 * error`; drive forward only when the target is within 12 % of the centre;
  4. stop when the depth in the middle of the picture is 0.55 m or less; with no red in view, turn slowly to search.
* Scene: the red cube is at (2.2, 1.3) - about 31 degrees to the left of the robot's nose - and the green decoy at (2.2, -1.2).

## Procedure

**1. T1 - Isaac Sim with the camera** (window: robot, red cube, green cube).

<!--run: bg ready="project 3 ready" wait=600-->
```powershell
pixi run isaac-p3 --gui
```

**2. T2 - the images exist.** Encoding, size and rate (the rate is in simulated time).

<!--run: fg expect="/camera/image_raw" expect="/camera/depth" expect="rgb8" expect="32FC1"-->
```powershell
pixi run isaac-ros topic list --no-daemon --spin-time 5
pixi run isaac-ros topic echo /camera/image_raw --no-daemon --once --spin-time 5 --field encoding
pixi run isaac-ros topic echo /camera/depth --no-daemon --once --spin-time 5 --field encoding
pixi run isaac-ros topic echo /camera/image_raw --no-daemon --once --spin-time 5 --field width
```

**3. T2 - start the controller.** The robot turns left until the red cube is in the middle, then drives to it and stops. The terminal prints what the node sees.

<!--run: bg wait=10-->
```powershell
pixi run isaac-follower
```

**4. T3 - did it work?** Wait about 40 s, then read the final position. The cube is at (2.2, 1.3); the robot should stop 0.55 m + half its length in front of it.

<!--run: fg timeout=120 expect="x: "-->
```powershell
Start-Sleep 45
pixi run isaac-ros topic echo /odom --no-daemon --once --spin-time 5 --field pose.pose.position
```

Compute the distance from (x, y) to (2.2, 1.3). Recorded: 0.77 m (the node stops when the camera is 0.55 m from the cube's front face).

<!--run: stopbg-->
```powershell
# Ctrl+C in T1 and T2
```

## Observations (recorded)

| Quantity | Value |
|---|---|
| Images | 320 x 240, `rgb8` and `32FC1` |
| Start | red cube 31 degrees to the left, green decoy on the right |
| End | robot 0.77 m from the cube centre, 1 degree off the nose; it did not go for the decoy |
| Depth straight ahead (cube at 0.50 m by geometry) | 0.48 m |

## Verification (own headless Isaac Sim, 4-6 min; close T1/T2 first)

<!--run: fg timeout=1200 expect="ALL PASSED"-->
```powershell
pixi run test-isaac-p3
```

12 checks: image sizes and encodings; the red pixels are in the left part of the first picture; the depth value matches the geometry; the robot ends nearer to the red cube than to the green decoy, close to it and facing it.

## Questions

1. Why is `R > 120` alone not a good "red" test? What does `R - G > 70` and `R - B > 70` add?
2. What would the node do if the red cube were behind the robot? If there were two red cubes?
3. Why does the node use *depth* to stop instead of the size of the red blob? Which one would a cheap robot with only an RGB camera have to use?
4. Change the colour test to follow the green cube instead. Which constants change?
5. *(Extension)* Add a lidar (see the LiDAR lab) and approach the cube without hitting a box.

## If it does not work

| Symptom | Fix |
|---|---|
| Robot only spins | the cube is not in view; check the camera picture in the Isaac Sim window; the colour test needs the light the script adds |
| `isaac-follower` prints nothing | T1 is not at `project 3 ready` |
| Camera images black | run with `--gui` once to let the shaders compile |
