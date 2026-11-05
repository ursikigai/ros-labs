r"""Project 1 - Drive DiffBot in Isaac Sim from ROS 2.

Isaac Sim hosts the world and the physics; ROS 2 (any terminal) drives the robot:
    /cmd_vel (geometry_msgs/Twist)  ->  left and right wheel speeds
    /odom, /tf, /joint_states, /clock  <-  published by the simulator

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p1_drive.py [--gui] [--sim-seconds 60]
"""
import diffbot_isaac as ib

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0)
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
print("[isaac] project 1 ready: publish geometry_msgs/Twist on /cmd_vel", flush=True)
if args.screenshot:
    ib.add_light()
    ib.set_view(eye=(-1.15, -1.35, 0.85), target=(0.15, 0.0, 0.05))
ib.run(world, args.sim_seconds, screenshot=args.screenshot)