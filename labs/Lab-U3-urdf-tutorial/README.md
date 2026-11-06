# Lab U3 - The `urdf_tutorial` robots (R2-D2 style, eight steps)

**Aim.** Build the official `urdf_tutorial` package from its repository and look at its eight example robots, from one cylinder to a macro-generated robot, to see how each URDF/xacro feature changes what RViz2 draws.

**Time.** 45 min. **Needs.** Only this folder. (The package is pure Python/XML: no compiler.) The repository is downloaded by `pixi run build-urdf`. Source: `upstream\urdf_tutorial-ros2` (branch `ros2`), built into `upstream_ws\urdf`.

## This folder is a complete project

Everything this lab needs is in this folder. Nothing from the other labs is required.

**Requirements:** Windows 10/11, PowerShell, [pixi](https://pixi.sh) (no administrator rights needed; install steps are in [README-SETUP.md](README-SETUP.md)), and internet access once, to download `ros/urdf_tutorial` from GitHub.

| In this folder | |
|---|---|
| `upstream\` | the original repository (downloaded by the first build task, pinned commit); `upstream_ws\` its build |
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

| File | New feature |
|---|---|
| `01-myfirst.urdf` | one link with a cylinder |
| `02-multipleshapes.urdf` | two links, one **fixed joint** |
| `03-origins.urdf` | joint **origin** (`xyz`, `rpy`): where the child sits |
| `04-materials.urdf` | **materials** (colours) |
| `05-visual.urdf` | different shapes, **meshes** for the head |
| `06-flexible.urdf` | **movable joints**: continuous, revolute, prismatic - sliders appear |
| `07-physics.urdf` | `collision` and `inertial` tags (needed by a physics simulator) |
| `08-macroed.urdf.xacro` | **xacro**: constants, macros, math - same robot, much shorter |

`display.launch.py` starts `robot_state_publisher` (URDF -> TF), `joint_state_publisher_gui` (sliders for the movable joints) and RViz2. The robot is chosen with the launch argument `model:=urdf/<file>`.

## Procedure

Shortcut for commands that need this package (re-type in each new terminal):

```
function urdf { pixi run cmd /c scripts\in_upstream.bat urdf @args }
```

**1. Build.**

<!--run: fg timeout=600 expect="packages? finished"-->
```powershell
pixi run build-urdf
```

**2. T1 - the first robot** (a single blue cylinder; fixed frame `base_link`).

<!--run: bg ready="rviz2.EXE.*process started" wait=120-->
```powershell
pixi run demo-urdf
```

**3. T2 - what was published.**

<!--run: fg expect="/robot_state_publisher" expect="/rviz" expect="/robot_description" expect="/tf_static"-->
```powershell
pixi run ros node list --no-daemon --spin-time 5
pixi run ros topic list --no-daemon --spin-time 5
```

**4. T1 - the movable robot.** Stop T1 (Ctrl+C), then start the sixth robot. Move the sliders: the head turns, the gripper opens, the arm slides.

<!--run: stopbg-->
```powershell
# Ctrl+C in T1
```

<!--run: bg ready="rviz2.EXE.*process started" wait=120-->
```powershell
pixi run demo-urdf model:=urdf/06-flexible.urdf
```

<!--run: fg expect="head_swivel" expect="gripper_extension"-->
```powershell
pixi run ros topic echo /joint_states --no-daemon --once --spin-time 5
```

(Only the movable joints are in `/joint_states`; the fixed ones never change.)

**5. T1 - the macro version.** Compare 07 and 08: same robot, one file written with xacro.

<!--run: stopbg-->
```powershell
# Ctrl+C in T1
```

<!--run: bg ready="rviz2.EXE.*process started" wait=120-->
```powershell
pixi run demo-urdf model:=urdf/08-macroed.urdf.xacro
```

<!--run: fg expect="robot name=.{0,2}macroed"-->
```powershell
pixi run ros topic echo /robot_description --no-daemon --once --spin-time 5 --field data
```

Count the lines of the two source files, and expand the xacro to plain URDF to see what the macros produce:

<!--run: fg expect="Successfully Parsed XML" expect="root Link: base_link"-->
```powershell
(Get-Content upstream\urdf_tutorial-ros2\urdf\07-physics.urdf).Count    # 417
(Get-Content upstream\urdf_tutorial-ros2\urdf\08-macroed.urdf.xacro).Count    # 237
pixi run xacro upstream\urdf_tutorial-ros2\urdf\08-macroed.urdf.xacro -o r2d2.urdf
pixi run check_urdf r2d2.urdf
Remove-Item r2d2.urdf
```

<!--run: stopbg-->
```powershell
# Ctrl+C in T1
```

**6. Try the others.** Run `pixi run demo-urdf model:=urdf/0N-....urdf` for 01-05 and 07. Before each, predict what RViz2 will draw.

## Observations (recorded)

| Item | Value |
|---|---|
| Nodes with `01-myfirst` | `/robot_state_publisher`, `/rviz`; topics `/robot_description`, `/tf_static` (no `/joint_states`: the robot has no movable joint). With `06-flexible` the slider node `/joint_state_publisher` also appears and `/joint_states` is published |
| `06-flexible` joints in `/joint_states` | `head_swivel`, `gripper_extension`, `left_gripper_joint`, `right_gripper_joint` and the four wheel joints |
| Source size | `07-physics.urdf` 417 lines, `08-macroed.urdf.xacro` 237 lines (the robot is named `macroed`); the xacro expands to a URDF with root link `base_link` |

## Verification

<!--run: fg timeout=900 expect="ALL PASSED"-->
```powershell
pixi run test-urdf
```

17 checks: for each of the eight robots the package's own `display.launch.py` is started; the published `/robot_description` equals the source file (after xacro: same link and joint counts) and every link resolves in TF.

## Questions

1. Which joint types appear in `06-flexible.urdf` and which of them gets a slider?
2. In `03-origins.urdf`, what is the difference between the joint `origin` and the visual `origin`?
3. How many lines does the macro version save (417 vs 237), and which repeated block does the macro replace?
4. Why does `07-physics.urdf` need `inertial` and `collision` tags when RViz2 does not?
5. *(Extension)* Add a camera link to `08-macroed.urdf.xacro` using the same macro style (edit a *copy*, not the clone).

## If it does not work

| Symptom | Fix |
|---|---|
| `malformed launch argument 'model:'` | you are using an older `scripts\in_upstream.bat`; update it (it must read `%*`) |
| `package 'urdf_tutorial' not found` | `pixi run build-urdf` |
| RViz2 grey | set *Fixed Frame* to `base_link` |
