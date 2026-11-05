r"""Project 2 - LiDAR in Isaac Sim, read by the course's own obstacle avoider.

Adds a 360 degree PhysX lidar to the DiffBot of project 1 and publishes it as sensor_msgs/LaserScan on /scan, frame
lidar_link: the same message the course's Class 4 simulator publishes. So the Class 4 node runs UNCHANGED:

    pixi run isaac-avoider        (ROS 2 side: ros2 run diffbot_navigation obstacle_avoider)

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p2_lidar.py [--gui] [--sim-seconds 60]
"""
import diffbot_isaac as ib

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0, boxes=[("box_a", (1.5, 1.0), (0.6, 0.6)), ("box_b", (-1.5, -1.0), (0.6, 0.6))])
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
ib.add_lidar(draw_rays=bool(args.screenshot))
print("[isaac] project 2 ready: /scan is published; send /cmd_vel or start the obstacle avoider", flush=True)
if args.screenshot:
    ib.add_light()
    ib.set_view(eye=(-3.2, -3.4, 3.4), target=(0.4, 0.0, 0.0))
ib.run(world, args.sim_seconds, screenshot=args.screenshot)