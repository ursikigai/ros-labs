# Lab I6 - Climb a ramp, judged by the IMU

**Aim.** Put an **IMU** on the robot and climb a 10 degree ramp onto a flat deck. A ROS 2 node reads only the IMU's tilt to decide "I am on the ramp" and "I am on the deck, stop". This is something the kinematic simulator of Labs 3-5 cannot do - it has no tilt - but a physics engine can.

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

An **IMU** (inertial measurement unit, the sensor in every phone) reports `sensor_msgs/Imu`:

| Field | Meaning | Standing still on level ground |
|---|---|---|
| `angular_velocity` | how fast the body turns, rad/s | 0, 0, 0 |
| `linear_acceleration` | the acceleration it **feels**, gravity included, m/s^2 | **(0, 0, +9.81)** |
| `orientation` | tilt as a quaternion | no tilt |

Scene: a ramp starting at x = 0.8 m, 2.0 m long, rising at 10 degrees (so the deck is 2.0 x tan 10 deg = **0.353 m** high), then a flat 1 m deck. The robot starts at the origin looking up the ramp.

`isaac\ros_nodes\ramp_climber.py` converts the orientation to a **slope** (`slope = -pitch`; in ROS a positive pitch tips the nose *down*, so nose-up is negative pitch) and runs three states:

```
waiting  --slope > 5 deg-->  climbing  --slope < 2 deg for 1 s-->  on the deck: stop
any state --slope > 25 deg--> too steep: stop
```

The one-second timer uses the IMU's own (simulated) time stamps, never the wall clock. Isaac Sim's IMU here is **noise-free**; a real one is noisy and drifts, which is why real robots filter it.

## Procedure

**1. T1 - Isaac Sim** (window: ramp and deck).

<!--run: bg ready="project 6 ready" wait=600-->
```powershell
pixi run isaac-p6 --gui
```

**2. T2 - read the IMU at rest.**

<!--run: fg expect="frame_id: base_link" expect="z: 9\.8"-->
```powershell
pixi run isaac-ros topic echo /imu --no-daemon --once --spin-time 5
```

**3. T2 - climb.** The node prints `on the ramp: slope 10.0 degrees` and, at the top, `on the deck: level again`, then stops the robot.

<!--run: bg ready="on the deck: level again" wait=240 expect="on the ramp: slope"-->
```powershell
pixi run isaac-ramp
```

**4. T3 - confirm with the odometry.** The robot should be on the deck: `z` about 0.35 m above its start, x between 2.8 m and 3.8 m, and stand still. (If the node has not printed `on the deck: level again` yet, repeat the command after a few seconds: the numbers above are only valid once it has.)

<!--run: fg expect="x: [23]\.[0-9]" expect="z: 0\.[23]"-->
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
| At rest | frame `base_link`, acceleration (0.00, 0.00, 9.81), tilt 0.00 degrees |
| On the ramp | steepest slope 10.0 degrees (the ramp has 10) |
| Climb in `/odom` | 0.35 m (deck: 0.353 m) |
| End | on the deck, slope 0.0 degrees, stopped before the end of the deck |

## Verification (own headless Isaac Sim, 4-6 min; close T1/T2 first)

<!--run: fg timeout=1200 expect="ALL PASSED"-->
```powershell
pixi run test-isaac-p6
```

11 checks: `/imu` frame is `base_link`; at rest |a| = 9.81 +- 0.8 and no tilt; on the ramp the IMU measures 10 +- 4 degrees; the robot is on the deck (x > 2.85 m, climbed 0.35 +- 0.1 m); level again on the deck; stopped there (moved under 3 cm in the last 2 s) before the end of the deck. Recorded: 11/11.

## Questions

1. Why does the acceleration read +9.81 on the z axis when the robot stands still, not 0?
2. In ROS a positive pitch tips the nose *down*. How does the node turn the quaternion into a "nose-up is positive" slope?
3. Why does the node wait 1 s of "level" before deciding it is on the deck, instead of stopping the moment the slope drops below 2 degrees?
4. Make the ramp 20 degrees (`RAMP_ANGLE` in `p6_ramp.py` **and** in the test) and see where the robot slips or tips. Which state does the node end in?
5. *(Extension)* Add noise to the IMU reading in your node and filter it with a moving average; compare the climb detection with and without it.

## If it does not work

| Symptom | Fix |
|---|---|
| `/imu` missing | T1 not ready (`project 6 ready`) |
| The node prints `too steep` | the slope exceeded 25 degrees: the robot tipped; restart T1 |
