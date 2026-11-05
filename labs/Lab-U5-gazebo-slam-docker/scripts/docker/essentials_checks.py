#!/usr/bin/env python3
"""Checks for the ORIGINAL robotics_essentials_ros2 setup, run INSIDE its Docker image (ROS 2 Humble, Gazebo Fortress,
Andino robot), headless. Started by run_stage.sh. Stages:

  sim       the simulation runs, publishes scan/odom/joint_states and the robot obeys cmd_vel      (exercises 0-1)
  odometry  odometry computed from /joint_states agrees with Gazebo's own /odom                    (exercise 4)
  slam      slam_toolbox builds a map while driving; map_saver_cli writes a PNG                    (exercise 2)
  nav       Nav2 uses the repo's C++ planner plugin, which calls a Python create_plan service      (exercise 5)

The Python solutions of the exercises (odometry, create_plan service) are the course's own implementations of the
repo's tasks; everything else (images, launch files, plugin, robot) is the repository's.
"""
import math
import os
import subprocess
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState, LaserScan

STAGE = sys.argv[1] if len(sys.argv) > 1 else "sim"
OUT = "/out"
WORLD = "gazebo_world"
WHEEL_RADIUS, WHEEL_SEPARATION = 0.033, 0.137  # values given in the repo's exercise 4


# ---------------------------------------------------------------------------------------------- reporting
class Checker:
    def __init__(self, title):
        self.failures = 0
        print(f"=== {title} ===", flush=True)

    def check(self, ok, msg):
        print(("PASS  " if ok else "FAIL  ") + msg, flush=True)
        self.failures += 0 if ok else 1

    def finish(self, title):
        print(f"--- {title}: {'ALL PASSED' if not self.failures else str(self.failures) + ' FAILED'}", flush=True)
        return 1 if self.failures else 0


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


# ---------------------------------------------------------------------------------------------- the probe node
class Probe(Node):
    def __init__(self):
        super().__init__("essentials_probe", parameter_overrides=[Parameter("use_sim_time", Parameter.Type.BOOL, True)])
        self.sim_time = None
        self.odom = self.scan = self.joints = self.map = self.plan = None
        self.plan_count = 0
        self.create_subscription(Clock, "/clock", lambda m: setattr(self, "sim_time", m.clock.sec + m.clock.nanosec * 1e-9), 10)
        self.create_subscription(Odometry, "/odom", lambda m: setattr(self, "odom", m), 10)
        self.create_subscription(LaserScan, "/scan", lambda m: setattr(self, "scan", m), qos_profile_sensor_data)
        self.create_subscription(JointState, "/joint_states", lambda m: setattr(self, "joints", m), 10)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, "/map", lambda m: setattr(self, "map", m), latched)
        self.create_subscription(Path, "/plan", self.on_plan, 10)
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)

    def on_plan(self, msg):
        if msg.poses:
            self.plan, self.plan_count = msg, self.plan_count + 1

    # --- time helpers (everything is paced by SIMULATION time, since software rendering runs slower than real time)
    def spin(self, wall_s):
        end = time.monotonic() + wall_s
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def wait_until(self, pred, timeout=180.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return True
            rclpy.spin_once(self, timeout_sec=0.1)
        return bool(pred())

    def drive(self, v, w, sim_seconds, wall_limit=240.0):
        """Publish (v, w) at 20 Hz until `sim_seconds` of simulated time have passed; then stop."""
        self.wait_until(lambda: self.sim_time is not None, 30)
        t0, wall0 = self.sim_time, time.monotonic()
        while self.sim_time - t0 < sim_seconds and time.monotonic() - wall0 < wall_limit:
            self.cmd.publish(Twist(linear=_vec(x=v), angular=_vec(z=w)))
            rclpy.spin_once(self, timeout_sec=0.05)
        self.cmd.publish(Twist())
        self.spin(1.0)

    def rtf(self, wall_s=6.0):
        """Real-time factor: simulated seconds per wall second."""
        self.wait_until(lambda: self.sim_time is not None, 30)
        t0, w0 = self.sim_time, time.monotonic()
        self.spin(wall_s)
        return (self.sim_time - t0) / (time.monotonic() - w0)


def _vec(x=0.0, z=0.0):
    from geometry_msgs.msg import Vector3
    return Vector3(x=float(x), y=0.0, z=float(z))


def unpause_world():
    """Gazebo starts paused (the exercises say 'press the play button'); do the same through the service."""
    r = subprocess.run(["ign", "service", "-s", f"/world/{WORLD}/control", "--reqtype", "ignition.msgs.WorldControl",
                        "--reptype", "ignition.msgs.Boolean", "--timeout", "5000", "--req", "pause: false"],
                       capture_output=True, text=True, timeout=30)
    return "true" in r.stdout


def pose_of(odom):
    p = odom.pose.pose
    return p.position.x, p.position.y, yaw_of(p.orientation)


# ---------------------------------------------------------------------------------------------- stages
def bring_up(c, p):
    # Gazebo starts PAUSED and a paused world publishes no sensor data, so press 'play' first. The service only
    # exists once Gazebo has finished loading, so retry until it answers.
    played = p.wait_until(lambda: unpause_world(), 300)
    c.check(played, "Gazebo finished loading and the world was un-paused through its service (the 'play button')")
    ok = p.wait_until(lambda: p.scan is not None and p.odom is not None and p.joints is not None and p.sim_time is not None, 180)
    c.check(ok, "the ROS bridge is up: /scan, /odom, /joint_states and /clock all publish")
    p.spin(2.0)
    t = p.sim_time
    p.spin(3.0)
    c.check(p.sim_time > t, "simulated time advances")
    print(f"real-time factor: {p.rtf():.2f} (simulated seconds per wall second, software rendering)", flush=True)
    return ok


def stage_sim(c, p):
    bring_up(c, p)
    names = list(p.joints.name)
    c.check("left_wheel_joint" in names and "right_wheel_joint" in names, f"/joint_states carries both wheels ({names})")
    c.check(len(p.scan.ranges) > 100 and any(math.isfinite(r) for r in p.scan.ranges),
            f"/scan has {len(p.scan.ranges)} rays and sees the depot ({sum(math.isfinite(r) for r in p.scan.ranges)} finite)")
    x0, y0, _ = pose_of(p.odom)
    p.drive(0.2, 0.0, 4.0)
    x1, y1, _ = pose_of(p.odom)
    d = math.hypot(x1 - x0, y1 - y0)
    print(f"distance travelled in 4 simulated seconds at 0.2 m/s: {d:.2f} m", flush=True)
    c.check(0.5 < d < 1.0, f"the robot obeys /cmd_vel (moved {d:.2f} m, expected about 0.8)")


def stage_odometry(c, p):
    bring_up(c, p)
    # Exercise 4: odometry from wheel rotation, written by us. Positions (not velocities) are integrated.
    state = {"x": 0.0, "y": 0.0, "th": 0.0, "prev": None}

    def on_joints(msg):
        try:
            l = msg.position[msg.name.index("left_wheel_joint")]
            r = msg.position[msg.name.index("right_wheel_joint")]
        except (ValueError, IndexError):
            return
        if state["prev"] is not None:
            dl, dr = (l - state["prev"][0]) * WHEEL_RADIUS, (r - state["prev"][1]) * WHEEL_RADIUS
            ds, dth = (dl + dr) / 2.0, (dr - dl) / WHEEL_SEPARATION
            state["x"] += ds * math.cos(state["th"] + dth / 2.0)
            state["y"] += ds * math.sin(state["th"] + dth / 2.0)
            state["th"] += dth
        state["prev"] = (l, r)

    p.create_subscription(JointState, "/joint_states", on_joints, 50)
    p.spin(1.0)
    gx0, gy0, gth0 = pose_of(p.odom)
    state["x"] = state["y"] = state["th"] = 0.0
    p.drive(0.2, 0.0, 4.0)
    p.drive(0.0, 0.5, 3.0)
    p.drive(0.2, 0.0, 3.0)
    gx, gy, gth = pose_of(p.odom)
    gx, gy, gth = gx - gx0, gy - gy0, wrap(gth - gth0)
    # Gazebo reports the pose in the odom frame; rotate our start-relative numbers into the same frame
    c_, s_ = math.cos(-gth0), math.sin(-gth0)
    gx, gy = c_ * gx - s_ * gy, s_ * gx + c_ * gy
    print(f"our odometry : x={state['x']:.3f} y={state['y']:.3f} yaw={state['th']:.3f}", flush=True)
    print(f"gazebo /odom : x={gx:.3f} y={gy:.3f} yaw={gth:.3f}", flush=True)
    # What the wheel rotation implies for this command sequence (0.2 m/s for 4 s, 0.5 rad/s for 3 s, 0.2 m/s for 3 s):
    px, py, pth = 0.8 + 0.6 * math.cos(1.5), 0.6 * math.sin(1.5), 1.5
    print(f"kinematic prediction from the commands: x={px:.3f} y={py:.3f} yaw={pth:.3f}", flush=True)
    err_pred = math.hypot(state["x"] - px, state["y"] - py)
    c.check(err_pred < 0.08 and abs(wrap(state["th"] - pth)) < 0.08,
            f"our wheel odometry reproduces the commanded motion (off by {err_pred:.3f} m, {abs(wrap(state['th'] - pth)):.3f} rad)")
    # Gazebo's /odom is the OdometryPublisher plugin: the PHYSICAL pose, including wheel slip. It need not equal the
    # wheel odometry. That difference is exactly what the exercise asks students to observe, so record it.
    err = math.hypot(state["x"] - gx, state["y"] - gy)
    dth = abs(wrap(state["th"] - gth))
    print(f"wheel odometry vs Gazebo's physical pose: {err:.3f} m and {dth:.3f} rad apart (wheel slip in the physics)", flush=True)
    c.check(math.hypot(gx, gy) > 0.5, f"the robot really moved (Gazebo says {math.hypot(gx, gy):.2f} m)")
    c.check(err < 0.4 and dth < 0.6, "both describe the same trajectory (within 0.4 m and 0.6 rad); the remainder is slip")


def stage_slam(c, p):
    bring_up(c, p)
    c.check(p.wait_until(lambda: p.map is not None, 180), "slam_toolbox publishes a /map")
    for v, w, t in [(0.0, 0.5, 14.0), (0.2, 0.0, 5.0), (0.0, 0.5, 14.0), (0.2, 0.0, 4.0), (0.0, 0.5, 14.0)]:
        p.drive(v, w, t)
    p.spin(5.0)
    m = p.map
    known = sum(1 for v in m.data if v >= 0)
    occupied = sum(1 for v in m.data if v > 50)
    free = sum(1 for v in m.data if v == 0)
    print(f"map: {m.info.width}x{m.info.height} cells at {m.info.resolution} m; known={known} free={free} occupied={occupied}", flush=True)
    c.check(free > 300, f"the map has free space ({free} cells)")
    c.check(occupied > 30, f"the map has walls/obstacles ({occupied} occupied cells)")
    r = subprocess.run(["ros2", "run", "nav2_map_server", "map_saver_cli", "--free", "0.15", "--fmt", "png", "-f", f"{OUT}/andino_map"],
                       capture_output=True, text=True, timeout=90)
    png = f"{OUT}/andino_map.png"
    c.check(os.path.exists(png) and os.path.getsize(png) > 0 and os.path.exists(f"{OUT}/andino_map.yaml"),
            f"map_saver_cli (exercise 2) wrote andino_map.png ({os.path.getsize(png) if os.path.exists(png) else 0} bytes) and .yaml")


def stage_nav(c, p):
    from create_plan_msgs.srv import CreatePlan
    from nav2_msgs.action import NavigateToPose
    from rclpy.action import ActionClient
    from std_srvs.srv import Trigger
    import tf2_ros

    requests = []

    def on_create_plan(req, res):
        """The repo's exercise 5, solved by us: a straight line, one pose every 0.1 m."""
        s, g = req.start.pose.position, req.goal.pose.position
        requests.append(((s.x, s.y), (g.x, g.y)))
        path = Path()
        path.header.frame_id = req.goal.header.frame_id
        path.header.stamp = p.get_clock().now().to_msg()
        n = max(1, int(math.hypot(g.x - s.x, g.y - s.y) / 0.1))
        for i in range(n + 1):
            t = i / n
            ps = PoseStamped()
            ps.header = path.header
            ps.pose.position.x, ps.pose.position.y = s.x + t * (g.x - s.x), s.y + t * (g.y - s.y)
            ps.pose.orientation.w = 1.0
            path.poses.append(ps)
        res.path = path
        return res

    p.create_service(CreatePlan, "create_plan", on_create_plan)
    bring_up(c, p)

    buf = tf2_ros.Buffer()
    tf2_ros.TransformListener(buf, p)
    init_pub = p.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)

    def localized():
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.pose.pose.orientation.w = 1.0
        msg.pose.covariance[0] = msg.pose.covariance[7] = 0.05
        msg.pose.covariance[35] = 0.05
        init_pub.publish(msg)  # the 'give a pose estimate' step of the exercises
        p.spin(1.0)
        return buf.can_transform("map", "odom", rclpy.time.Time())

    c.check(p.wait_until(localized, 240), "Nav2 localizes (initial pose accepted, TF map -> odom exists)")
    active = {}
    for name in ("lifecycle_manager_navigation", "lifecycle_manager_localization"):
        cli = p.create_client(Trigger, f"/{name}/is_active")
        ok = False
        if cli.wait_for_service(timeout_sec=30):
            fut = cli.call_async(Trigger.Request())
            p.wait_until(fut.done, 20)
            ok = fut.done() and fut.result().success
        active[name] = ok
    c.check(all(active.values()), f"Nav2 lifecycle managers report ACTIVE ({active})")

    log = open(f"{OUT}/nav_sim.log", errors="replace").read() if os.path.exists(f"{OUT}/nav_sim.log") else ""
    c.check("custom_nav2_planner/CustomPlanner" in log,
            "the planner server loaded the REPO's plugin: custom_nav2_planner/CustomPlanner")

    # choose a goal in free space straight ahead (any direction), using the real map
    p.wait_until(lambda: p.map is not None, 60)
    m, goal = p.map, None
    res, ox, oy, W, H = m.info.resolution, m.info.origin.position.x, m.info.origin.position.y, m.info.width, m.info.height

    def free_disc(x, y, clearance=0.35):
        r = int(clearance / res)
        cx, cy = int((x - ox) / res), int((y - oy) / res)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                ix, iy = cx + dx, cy + dy
                if ix < 0 or iy < 0 or ix >= W or iy >= H or m.data[iy * W + ix] != 0:
                    return False
        return True

    for dist in (1.6, 1.4, 1.2, 1.0):
        for k in range(8):
            a = k * math.pi / 4
            if all(free_disc(i * 0.1 * math.cos(a), i * 0.1 * math.sin(a)) for i in range(0, int(dist / 0.1) + 1)):
                goal = (dist * math.cos(a), dist * math.sin(a))
                break
        if goal:
            break
    c.check(goal is not None, f"found a free straight corridor from the start for the goal: {None if not goal else tuple(round(v, 2) for v in goal)}")
    if not goal:
        return

    x0, y0, _ = pose_of(p.odom)
    ac = ActionClient(p, NavigateToPose, "navigate_to_pose")
    c.check(ac.wait_for_server(timeout_sec=60), "Nav2's navigate_to_pose action server is available")
    g = NavigateToPose.Goal()
    g.pose.header.frame_id = "map"
    g.pose.pose.position.x, g.pose.pose.position.y = goal
    g.pose.pose.orientation.w = 1.0
    fut = ac.send_goal_async(g)
    p.wait_until(fut.done, 30)
    handle = fut.result()
    c.check(handle is not None and handle.accepted, "goal accepted by Nav2")
    status = None
    if handle and handle.accepted:
        rf = handle.get_result_async()
        p.wait_until(rf.done, 420)
        status = rf.result().status if rf.done() else None
    c.check(status == 4, f"Nav2 reports SUCCEEDED (status {status})")
    x1, y1, _ = pose_of(p.odom)
    dist_goal = math.hypot((x1 - x0) - goal[0], (y1 - y0) - goal[1])
    print(f"final: moved ({x1 - x0:.2f}, {y1 - y0:.2f}) for goal ({goal[0]:.2f}, {goal[1]:.2f}); {dist_goal:.2f} m from the goal", flush=True)
    c.check(dist_goal < 0.45, f"the robot ended within 0.45 m of the goal ({dist_goal:.2f} m)")
    c.check(len(requests) >= 1, f"the C++ plugin called our create_plan service ({len(requests)} requests)")
    dev = 0.0
    if p.plan is not None:
        pts = [(q.pose.position.x, q.pose.position.y) for q in p.plan.poses]
        (ax, ay), (bx, by) = pts[0], pts[-1]
        L = math.hypot(bx - ax, by - ay) or 1.0
        dev = max(abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / L for px, py in pts)
    c.check(p.plan is not None and dev < 0.03, f"the plan published by Nav2 is a straight line from our service (max deviation {dev:.3f} m)")


def main():
    titles = {"sim": "Essentials exercises 0-1: Andino simulation", "odometry": "Essentials exercise 4: wheel odometry",
              "slam": "Essentials exercise 2: slam_toolbox mapping", "nav": "Essentials exercise 5: C++ planner plugin in Nav2"}
    title = f"{titles[STAGE]} (original Docker image, headless Gazebo)"
    c = Checker(title)
    rclpy.init()
    p = Probe()
    try:
        {"sim": stage_sim, "odometry": stage_odometry, "slam": stage_slam, "nav": stage_nav}[STAGE](c, p)
    except Exception as exc:  # report, do not hide
        import traceback
        traceback.print_exc()
        c.check(False, f"stage crashed: {exc!r}")
    rc = c.finish(title)
    p.destroy_node()
    rclpy.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())
