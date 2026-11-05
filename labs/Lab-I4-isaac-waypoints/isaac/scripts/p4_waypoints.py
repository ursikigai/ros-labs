r"""Project 4 - Waypoints: drive to three coloured squares on the floor, in order.

Isaac Sim side: the DiffBot in a room with a red, a green and a blue square painted on the floor (flat, no collision).
ROS 2 side (isaac/ros_nodes/waypoints.py): reads /odom, publishes /cmd_vel, and visits A (red), B (green), C (blue).

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p4_waypoints.py [--gui] [--sim-seconds 90]
    pixi run isaac-waypoints        (in a second terminal)
"""
import diffbot_isaac as ib

# The three squares: keep in step with WAYPOINTS in isaac/ros_nodes/waypoints.py
WAYPOINTS = {"A_red": (1.5, 0.0, (0.9, 0.1, 0.1)), "B_green": (1.5, 1.5, (0.1, 0.7, 0.2)), "C_blue": (-0.5, 1.5, (0.15, 0.3, 0.9))}

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0)
for name, (x, y, colour) in WAYPOINTS.items():
    ib.add_marker(name, (x, y), (0.4, 0.4), colour)
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
if args.screenshot:
    ib.add_light()
    ib.set_view(eye=(-1.8, -3.0, 3.2), target=(0.6, 0.8, 0.0))
print("[isaac] project 4 ready: drive with /cmd_vel, read /odom", flush=True)
ib.run(world, args.sim_seconds, screenshot=args.screenshot)
