r"""Project 3 - A camera in Isaac Sim, and a ROS 2 node that steers by what it sees.

The robot gets an RGB + depth camera (/camera/image_raw, /camera/depth). A red cube and a green decoy stand in the room.
The ROS 2 side (isaac/ros_nodes/color_follower.py) finds the red pixels in the image and turns the robot towards them,
then drives up to the cube.

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p3_camera.py [--gui] [--sim-seconds 90]
    pixi run isaac-follower        (in a second terminal)
"""
import diffbot_isaac as ib

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0)
ib.add_light()
# Coloured cubes (0.3 m): the red one is the target, the green one a decoy. Fixed, so they are solid walls to the robot.
from isaacsim.core.api.objects import FixedCuboid
import numpy as np

FixedCuboid(prim_path="/World/room/target_red", name="target_red", position=np.array([2.2, 1.3, 0.15]),
            scale=np.array([0.3, 0.3, 0.3]), color=np.array([0.9, 0.05, 0.05]))
FixedCuboid(prim_path="/World/room/decoy_green", name="decoy_green", position=np.array([2.2, -1.2, 0.15]),
            scale=np.array([0.3, 0.3, 0.3]), color=np.array([0.05, 0.8, 0.1]))
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
ib.add_camera()
print("[isaac] project 3 ready: /camera/image_raw and /camera/depth are published", flush=True)
if args.screenshot:
    ib.set_view(eye=(-2.6, -2.5, 2.1), target=(1.4, 0.2, 0.1))
ib.run(world, args.sim_seconds, screenshot=args.screenshot)