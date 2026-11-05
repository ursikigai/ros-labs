# Lab 4 - LiDAR and Reactive Obstacle Avoidance

**Aim.** Make DiffBot wander the room without touching a wall, using only its 2D LiDAR and a small rule-based controller (no map, no goal).

**Time.** 60 min. **Needs.** Only this folder (no compiler).

## This folder is a complete project

Everything this lab needs is in this folder. Nothing from the other labs is required.

**Requirements:** Windows 10/11, PowerShell, [pixi](https://pixi.sh) (`winget install --id prefix-dev.pixi -e --source winget`), and nothing else.

| In this folder | |
|---|---|
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

A `sensor_msgs/LaserScan` is a list of distances, one per ray, starting at `angle_min` and stepping by `angle_increment`. In the simulator: 360 rays, 1 degree apart, from -180 to +179 degrees (0 degrees = straight ahead), range 0.12-6.0 m; a ray that hits nothing is `inf`. The scan is in frame `lidar_link`, 8 cm ahead of the robot centre.

The controller (`diffbot_navigation/reactive.py`, pure Python) splits the scan into sectors - **front** (+-30 deg, minimum range) and **left** / **right** (30-90 deg, mean range) - and applies three rules:

| Situation | Action |
|---|---|
| front < 0.45 m (`STOP_DIST`) | stop, turn on the spot towards the side with more room, and **remember the direction** |
| 0.45 m < front < 0.90 m (`SLOW_DIST`) | slow down; keep turning if already turning, otherwise nudge away from the nearer side |
| front > 0.90 m | cruise at 0.25 m/s |

Remembering the turn direction (`turn_dir`) stops the robot dithering left/right when both sides look equally open. `inf`/`nan` ranges are first replaced by 10 m, otherwise a single `inf` would make a mean infinite.

## Procedure

**1. T1 - start the robot with its avoider** (RViz2 shows the room, the robot and the red laser points; the robot starts moving by itself).

<!--run: bg ready="rviz2.EXE.*process started" wait=120-->
```powershell
pixi run demo-avoid
```

**2. T2 - look at the data and the decision.**

<!--run: fg expect="/obstacle_avoider" expect="/scan" expect="/collision_count" expect="angle_increment: 0.017" expect="range_max: 6.0" expect="linear:"-->
```powershell
pixi run ros node list --no-daemon --spin-time 5
pixi run ros topic list --no-daemon --spin-time 5
pixi run ros topic echo /scan --no-daemon --once --spin-time 4 --truncate-length 6
pixi run ros topic echo /cmd_vel --no-daemon --once --spin-time 4
```

**3. T2 - how often does the lidar publish?** (stops itself after 15 s)

<!--run: stop=20 expect="average rate: 10\.0"-->
```powershell
pixi run ros topic hz /scan --spin-time 5
```

**4. T2 - is it exploring?** Print the robot's true position five times, 6 s apart; the numbers should keep changing, within x 0-10 and y 0-8.

<!--run: fg timeout=120 expect="x: "-->
```powershell
1..5 | ForEach-Object { pixi run ros topic echo /ground_truth --no-daemon --once --spin-time 4 --field pose.pose.position; Start-Sleep 6 }
```

**5. T2 - collisions.** `/collision_count` publishes only when the robot touches something. 20 s of silence = no collision.

<!--run: stop=25 reject="data:|does not appear|Could not determine"-->
```powershell
pixi run ros topic echo /collision_count --no-daemon --spin-time 5
```

**6. Experiment: make the robot braver.** In `ws\src\diffbot_navigation\diffbot_navigation\reactive.py` the robot stops turning on the spot 0.45 m in front of a wall. The robot's radius is 0.17 m and the lidar sits 0.08 m ahead of the centre. Reduce `STOP_DIST` to 0.25 and run the automated test (stop T1 with Ctrl+C first). Predict first: will it collide?

<!--run: stopbg-->
```powershell
# Ctrl+C in T1
```

<!--run: fg timeout=400-->
```powershell
(Get-Content ws\src\diffbot_navigation\diffbot_navigation\reactive.py) -replace 'STOP_DIST = 0.45','STOP_DIST = 0.25' | Set-Content ws\src\diffbot_navigation\diffbot_navigation\reactive.py
pixi run build-core
pixi run test-class4
```

Record the result (`PASS`/`FAIL` lines) in the table below, then try 0.15 and 0.08 the same way. Restore the value when you are done:

<!--run: fg timeout=200-->
```powershell
(Get-Content ws\src\diffbot_navigation\diffbot_navigation\reactive.py) -replace 'STOP_DIST = 0.25','STOP_DIST = 0.45' | Set-Content ws\src\diffbot_navigation\diffbot_navigation\reactive.py
pixi run build-core
```

## Observations (recorded)

| Quantity | Value |
|---|---|
| `/scan` | 360 rays, `angle_increment` 0.01745 rad, `range_max` 6.0, 10.0 Hz |
| Typical `/cmd_vel` in open space | `linear.x = 0.25`, `angular.z = 0` |
| 60 s of wandering with `STOP_DIST = 0.45` | 13.8 m driven, 14 different 1 m x 1 m cells visited, 0 collisions |
| `STOP_DIST = 0.25` | 14.1 m driven, 15 cells, **0 collisions** - passes |`r`n| `STOP_DIST = 0.15` and `0.08` | still 0 collisions (14.1 m / 14.2 m, 15 cells) |

## Verification

<!--run: fg timeout=300 expect="ALL PASSED"-->
```powershell
pixi run test-class4
```

The test runs the avoider for 60 s and requires: more than 8 m driven, at least 4 different cells visited, and no collision.
The controller's rules are also unit-tested: read `ws\src\diffbot_navigation\test\test_navigation_logic.py` and run `pixi run test-unit`.

## Questions

1. Predict `compute_command` for: (a) open space, (b) a wall dead ahead at 0.3 m with more room on the left, (c) all ranges `inf`. Check your answers in the unit tests.
2. Why must `inf` be replaced before the mean is computed?
3. Why does the controller keep `turn_dir` instead of recomputing left/right every time?
4. The robot visits only 14 of 80 cells in a minute. How would you make it explore more systematically?
5. The test still passes with `STOP_DIST = 0.08`, although the robot radius is 0.17 m. Which of the three rules is keeping the robot away from the walls then? What would you change (and which constant) to make the test fail?`r`n6. *(Extension)* Write a right-hand wall follower that keeps 0.4 m from the wall; add a bumper recovery that reverses for 1 s when `/collision_count` increases.

## If it does not work

| Symptom | Fix |
|---|---|
| Robot does not move | the avoider needs the simulator's `/scan`; `ros node list` must show `/diffbot_sim` and `/obstacle_avoider` |
| A Python edit has no effect | run `pixi run build-core` |
| `topic hz` prints nothing | add `--spin-time 5` and wait 10 s |
