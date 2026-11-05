#!/bin/bash
# Runs ONE stage of the Essentials exercise tests inside the robotics_essentials_ros2:headless container.
# Started by scripts/docker/run_essentials_docker.ps1, e.g.
#   docker run ... robotics_essentials_ros2:headless bash /tests/run_stage.sh sim
#
# Stages:  probe     print topics/nodes (for exploring)
#          sim       exercise 0/1: the Andino simulation works and can be driven
#          odometry  exercise 4: our odometry from /joint_states vs Gazebo's /odom
#          slam      exercise 2: slam_toolbox builds a map; map_saver_cli writes a PNG
#          nav       exercise 5: Nav2 with the repo's C++ planner plugin + a Python create_plan service
set -u
STAGE="${1:-sim}"
OUT=/out
mkdir -p "$OUT"
export ROS_DOMAIN_ID=42
export LIBGL_ALWAYS_SOFTWARE=1       # no GPU in the container: Mesa software rendering
export QT_X11_NO_MITSHM=1
LOG="$OUT/${STAGE}_sim.log"
PARAMS_ARG=""
SIM_ARGS="rviz:=False"

stop_all() {
  pkill -f "ros2 launch" 2>/dev/null
  pkill -f "ign gazebo" 2>/dev/null
  pkill -f "gz sim" 2>/dev/null
  pkill -f parameter_bridge 2>/dev/null
  sleep 2
  pkill -9 -f "ign gazebo" 2>/dev/null
  pkill -9 -f "ros2" 2>/dev/null
  [ -n "${XVFB_PID:-}" ] && kill "$XVFB_PID" 2>/dev/null
}
trap stop_all EXIT

# A virtual screen for Gazebo's GUI. Started by hand (not with xvfb-run, whose SIGUSR1 start-up handshake can
# hang when the parent process ignores that signal, as under `docker run` from a script).
XVFB_PID=""
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
  Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp > "$OUT/${STAGE}_xvfb.log" 2>&1 &
  XVFB_PID=$!
  for _ in $(seq 1 40); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 0.5; done
fi
export DISPLAY=:99
echo "[stage $STAGE] virtual display ready: $(xdpyinfo -display :99 2>/dev/null | grep dimensions | xargs)"

if [ "$STAGE" = "nav" ]; then
  # Exercise 5 step 1 ("Change the Planner"): replace NavFn by the repo's plugin in a COPY of nav2_params.yaml.
  SRC=$(ros2 pkg prefix andino_gz)/share/andino_gz/config/nav2_params.yaml
  sed 's#nav2_navfn_planner/NavfnPlanner#custom_nav2_planner/CustomPlanner#' "$SRC" > /tmp/nav2_params_custom.yaml
  N=$(grep -c 'custom_nav2_planner/CustomPlanner' /tmp/nav2_params_custom.yaml)
  echo "planner replaced in params copy: $N occurrence(s)"
  [ "$N" = "1" ] || { echo "ERROR: expected exactly 1 planner line to replace"; exit 3; }
  cp /tmp/nav2_params_custom.yaml "$OUT/nav2_params_custom.yaml"
  SIM_ARGS="rviz:=False nav2:=True params_file:=/tmp/nav2_params_custom.yaml"
fi

echo "[stage $STAGE] starting simulation: ros2 launch andino_gz andino_gz.launch.py $SIM_ARGS"
# shellcheck disable=SC2086
ros2 launch andino_gz andino_gz.launch.py $SIM_ARGS > "$LOG" 2>&1 &

if [ "$STAGE" = "slam" ]; then
  sleep 5
  echo "[stage slam] starting slam_toolbox_online_async"
  ros2 launch andino_gz slam_toolbox_online_async.launch.py > "$OUT/slam_toolbox.log" 2>&1 &
fi

if [ "$STAGE" = "probe" ]; then
  sleep 75
  echo "=== ros2 node list"; ros2 node list 2>&1 | head -40
  echo "=== ros2 topic list -t"; ros2 topic list -t 2>&1 | head -60
  echo "=== ign topic list"; ign topic -l 2>&1 | head -40
  echo "=== sim log tail"; tail -15 "$LOG"
  exit 0
fi

python3 /tests/essentials_checks.py "$STAGE"
RC=$?
echo "[stage $STAGE] checks exit code $RC"
exit $RC
