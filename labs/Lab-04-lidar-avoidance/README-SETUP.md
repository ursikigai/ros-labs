# Setup for Lab 4 - LiDAR and Reactive Obstacle Avoidance

This page only gets your computer ready. The lab itself is in [README.md](README.md). **Running a lab does not need administrator rights**: everything below runs as a normal user, except the one extra install marked *(administrator)* if your lab has one.

## 1. What you need

* Windows 10 or 11 with PowerShell (already on your computer) and internet access (the first run downloads a few GB).
* About 5 GB of free disk for this lab's environment (pixi shares downloads between labs, so the next lab is smaller).
* Permission to create folders on `C:\` (normal on a personal laptop): the lab keeps its environment in `C:\rlabs` and its build files in `C:\rb`.

## 2. Install pixi (once per computer, no administrator rights)

pixi sets up ROS 2 and everything else for you. Open PowerShell and run:

```powershell
powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```

Close PowerShell, open a new one and check:

```powershell
pixi --version
```

(It installs into `%UserProfile%\.pixi\bin`, inside your own user folder. `winget install prefix-dev.pixi` also works.)

## 3. Get this lab (no Git needed)

Keep it in a short folder **outside OneDrive** (OneDrive locks files and breaks builds), for example in your user folder:

```powershell
cd $HOME
Invoke-WebRequest https://github.com/ursikigai/ros-labs/archive/refs/heads/main.zip -OutFile ros-labs.zip
Expand-Archive ros-labs.zip -DestinationPath .
Rename-Item ros-labs-main ros-labs
```

If you have Git you can use `git clone https://github.com/ursikigai/ros-labs.git` instead. Only the folder `labs\Lab-04-lidar-avoidance` is needed for this lab.

## 4. Run the lab

```powershell
cd $HOME\ros-labs\labs\Lab-04-lidar-avoidance
pixi install
pixi run verify
```

`pixi install` downloads the environment (minutes the first time). `pixi run verify` must print `PASS: rclpy pub/sub works`. Then open [README.md](README.md) and follow it from the top; its last step is a one-command automated check.

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| `pixi` is not recognised | close PowerShell and open a new one; the installer only changes the PATH of new windows |
| "running scripts is disabled" | the lab commands already avoid this. If you start a `.ps1` file yourself, use `powershell -NoProfile -ExecutionPolicy Bypass -File <file>` (no administrator needed) |
| a build says a package is missing right after it "finished" | run `pixi run build` again; moving or re-downloading the lab folder is handled automatically |
| a program from an earlier try is still running | `Get-Process \| Where-Object { $_.Path -like "C:\rlabs\*" -or $_.Path -like "C:\ix\*" } \| Stop-Process -Force` |
| red text starting with `Pixi task (...)` | that is pixi's status line, not an error |
| the first `pixi install` seems stuck | it is downloading a few GB; wait, and use a good connection |
