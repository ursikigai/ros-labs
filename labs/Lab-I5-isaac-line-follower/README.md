# Lab I5 - Line follower with a downward camera

**Aim.** A camera looks down at the floor; a ROS 2 node finds the dark pixels of a black line and steers to keep them in the middle of the picture. The robot follows a line with a smooth 0.6 m bend to the left and stops where the line ends.

**Time.** 30 min. **Needs.** Only this folder, an **NVIDIA RTX GPU** (tested: RTX 5050 Laptop, 8 GB, driver 592.82) and about 15 GB of disk for Isaac Sim, which `pixi run isaac-install` downloads once for all Isaac labs on the machine. By running the scripts you accept NVIDIA's Isaac Sim licence.

## This folder is a complete project

Everything this lab needs is in this folder. Nothing from the other labs is required.

**Requirements:** Windows 10/11, PowerShell, [pixi](https://pixi.sh) (`winget install --id prefix-dev.pixi -e --source winget`), and an NVIDIA RTX GPU with a current driver; about 15 GB disk for Isaac Sim (shared by all Isaac labs, installed once into `C:\ix`); internet for the first install.

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

* Camera: 160 x 120 pixels, 90 degree field of view, on the front edge of the body, 21 cm above the floor, tilted **50 degrees down**. It sees the floor from about 1 cm to 0.9 m ahead. (It must be well in front of the roof, otherwise its steepest rays see the robot's own dark body.)
* Scene: a pale mat with a black line - straight, a smooth 0.6 m bend to the left, straight again.
* `isaac\ros_nodes\line_follower.py`:
  1. a pixel is **dark** if its grey value is below 70 % of the picture's **median** grey value (the "black" line is rendered mid-grey, about 100 of 255, because the light reflects off it, so a fixed threshold fails);
  2. `error = (mean column of the dark pixels - centre) / (width / 2)`, -1 ... +1, negative = line on the left;
  3. turn `w = -1.6 * error`; drive at 0.12 m/s, slower in sharp turns;
  4. fewer than 30 dark pixels = line lost = **stop** (this is how it ends at the end of the line).
* This is a **proportional controller** on the measured error, closed through the camera and the physics.

## Procedure

**1. T1 - Isaac Sim** (window: mat, black line, robot standing on its start).

<!--run: bg ready="project 5 ready" wait=600-->
```powershell
pixi run isaac-p5 --gui
```

**2. T2 - the image.** Size and encoding; in the Isaac Sim window you see the same picture the node uses.

<!--run: fg expect="rgb8" expect="160"-->
```powershell
pixi run isaac-ros topic echo /camera/image_raw --no-daemon --once --spin-time 5 --field encoding
pixi run isaac-ros topic echo /camera/image_raw --no-daemon --once --spin-time 5 --field width
```

**3. T2 - follow the line.** The node prints its error and speeds, and `line lost: stopped` at the end (about 55 simulated seconds).

<!--run: bg ready="line lost: stopped" wait=300-->
```powershell
pixi run isaac-line
```

**4. T3 - where did it end?** The line ends at x = 3.5 m, after the bend (y = 0.60 m). The robot should be near there and standing still.

<!--run: fg expect="x: 3\.[0-9]" expect="y: 0\.[4-7]"-->
```powershell
pixi run isaac-ros topic echo /odom --no-daemon --once --spin-time 5 --field pose.pose.position
```

<!--run: stopbg-->
```powershell
# Ctrl+C in T1 and T2
```

## Observations (recorded)

| Quantity | Value |
|---|---|
| Image | 160 x 120 `rgb8`; 1718 dark pixels at the start (the line), floor median 243 of 255 |
| Run | followed the line to its end in about 55 simulated seconds; ended at y = 0.60 m after the bend, then stopped |
| Accuracy | 0.4 cm from the line on average, 1.6 cm at worst (measured from `/odom` against the line's formula) |

## Verification (own headless Isaac Sim, 4-6 min; close T1/T2 first)

<!--run: fg timeout=1200 expect="ALL PASSED"-->
```powershell
pixi run test-isaac-p5
```

11 checks: image size and encoding; the line is visible near the middle of the first picture (150-3500 dark pixels, none from the robot's own body); the floor is pale (median > 150); the follower's rule says "drive on, hardly turn"; the robot reaches x > 3.0 m, after the bend (y within 15 cm of 0.6 m); mean distance from the line < 6 cm and worst < 18 cm; it stops at the end.

## Questions

1. Why is "darker than 70 % of the median" better than "grey value below 70"? What would go wrong with a black floor?
2. What happens with `w = -3.0 * error`? With `-0.5 * error`? Predict, then change the constant in `line_follower.py` and run again.
3. The camera looks down at 50 degrees, not straight down. What does the robot gain, what does it lose?
4. A proportional controller cannot remove a constant offset in a curve. How would a PID controller help?
5. *(Extension)* Make the line a closed loop (`isaac\scripts\line_track.py`) or stop at a red patch (a colour test like "R > 120, R - G > 70, R - B > 70").

## If it does not work

| Symptom | Fix |
|---|---|
| Robot stops immediately | fewer than 30 dark pixels: the camera does not see the line; restart T1 |
| Half of the picture counts as "dark" | the camera sees the robot's own body: check `position`/`pitch_deg` of `add_camera` |
