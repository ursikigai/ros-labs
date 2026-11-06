# Setup for Lab U5 - Gazebo, odometry, SLAM and Nav2 in the Essentials Docker image

This page only gets your computer ready. The lab itself is in [README.md](README.md). **Running a lab does not need administrator rights**: everything below runs as a normal user, except the one extra install marked *(administrator)* if your lab has one.

## 1. What you need

* Windows 10 or 11 with PowerShell (already on your computer) and internet access (the first run downloads a few GB).
* About 5 GB of free disk for this lab's environment (pixi shares downloads between labs, so the next lab is smaller).
* Permission to create folders on `C:\` (normal on a personal laptop): the lab keeps its environment in `C:\rlabs` and its build files in `C:\rb`.
* **Docker Desktop** with the WSL 2 backend, with about 12 GB RAM for its VM and 10 GB free disk (see section 5).

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

If you have Git you can use `git clone https://github.com/ursikigai/ros-labs.git` instead. Only the folder `labs\Lab-U5-gazebo-slam-docker` is needed for this lab.

## 4. Run the lab

```powershell
cd $HOME\ros-labs\labs\Lab-U5-gazebo-slam-docker
pixi install

```

`pixi install` downloads the environment (minutes the first time). Then open [README.md](README.md) and follow it from the top; its last step is a one-command automated check.

## 5. Docker Desktop *(administrator, once per computer)*

Docker Desktop (with WSL 2) needs an administrator to install, and your account must be a member of the `docker-users` group. Ask your lab administrator if it is not installed yet. Before the lab, start Docker Desktop, wait until it says the engine is running, and check:

```powershell
docker version
```

## 6. If something goes wrong

| Symptom | Fix |
|---|---|
| `pixi` is not recognised | close PowerShell and open a new one; the installer only changes the PATH of new windows |
| "running scripts is disabled" | the lab commands already avoid this. If you start a `.ps1` file yourself, use `powershell -NoProfile -ExecutionPolicy Bypass -File <file>` (no administrator needed) |
| a build says a package is missing right after it "finished" | run `pixi run build` again; moving or re-downloading the lab folder is handled automatically |
| a program from an earlier try is still running | `Get-Process \| Where-Object { $_.Path -like "C:\rlabs\*" -or $_.Path -like "C:\ix\*" } \| Stop-Process -Force` |
| red text starting with `Pixi task (...)` | that is pixi's status line, not an error |
| the first `pixi install` seems stuck | it is downloading a few GB; wait, and use a good connection |
