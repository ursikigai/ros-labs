"""Drive an Isaac Sim robot for a number of SIMULATED seconds.

Isaac Sim does not run at wall-clock speed (it publishes its own time on /clock). `pixi run isaac-drive` counts wall-clock
seconds, so the distance it drives depends on how fast the simulation runs. This script counts /clock instead, so
v = 0.2 m/s for 4 s really means 0.8 m of simulated motion.

    pixi run python lab-manuals\\code\\drive_sim.py <linear m/s> <angular rad/s> <simulated seconds>
    pixi run python lab-manuals\\code\\drive_sim.py 0.2 0.0 4
"""
import os
import sys
import time

# the Isaac Sim projects use ROS domain 78 and Fast DDS (must be set before rclpy starts)
os.environ.setdefault("ROS_DOMAIN_ID", "78")
os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_fastrtps_cpp")

import rclpy  # noqa: E402
from geometry_msgs.msg import Twist, Vector3  # noqa: E402
from rosgraph_msgs.msg import Clock  # noqa: E402


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    v, w, seconds = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])

    rclpy.init()
    node = rclpy.create_node("drive_sim")
    pub = node.create_publisher(Twist, "cmd_vel", 10)
    now = [None]
    node.create_subscription(Clock, "clock", lambda m: now.__setitem__(0, m.clock.sec + m.clock.nanosec * 1e-9), 10)

    # wait until the simulator is listening and its clock runs
    deadline = time.monotonic() + 30.0
    while (now[0] is None or pub.get_subscription_count() == 0) and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if now[0] is None or pub.get_subscription_count() == 0:
        print("FAILED: no /clock or nobody listens on /cmd_vel. Is Isaac Sim running (pixi run isaac-p1)?")
        return 1

    t0 = now[0]
    wall_limit = time.monotonic() + 20.0 * seconds + 30.0     # never loop for ever if the clock stops
    while now[0] - t0 < seconds and time.monotonic() < wall_limit:
        pub.publish(Twist(linear=Vector3(x=v), angular=Vector3(z=w)))
        rclpy.spin_once(node, timeout_sec=0.05)
    for _ in range(5):
        pub.publish(Twist())                                  # explicit stop
        rclpy.spin_once(node, timeout_sec=0.05)
    print(f"drove v={v} m/s, w={w} rad/s for {now[0] - t0:.2f} simulated seconds")
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
