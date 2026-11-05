r"""Project 5 - Line follower: a camera that looks down at the floor, and a ROS 2 node that follows a black line.

Isaac Sim side: a pale mat with a black line on it, and a 160x120 camera on the robot's nose tilted 50 degrees down.
ROS 2 side (isaac/ros_nodes/line_follower.py): finds the dark pixels, steers to keep them in the middle of the picture.

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p5_line.py [--gui] [--sim-seconds 90]
    pixi run isaac-line        (in a second terminal)
"""
import diffbot_isaac as ib
import line_track as lt

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0)
ib.add_light()
# a pale mat so the line stands out, then the line itself (short dark pieces that overlap)
ib.add_marker("mat", (1.5, 0.3), (6.0, 2.4), (0.85, 0.85, 0.85), z=0.002, thickness=0.004)
for i, (x, y, length, yaw) in enumerate(lt.segments()):
    ib.add_marker(f"line_{i:02d}", (x, y), (length, lt.LINE_WIDTH), (0.02, 0.02, 0.02), yaw_deg=yaw, z=0.0045, thickness=0.004)
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
# On the front edge of the body (x = 0.15) and well above its roof, or the steep rays would see the robot's own dark body.
ib.add_camera(width=160, height=120, hfov_deg=90.0, position=(0.15, 0.0, 0.16), pitch_deg=50.0)
print("[isaac] project 5 ready: /camera/image_raw looks down at the line", flush=True)
if args.screenshot:
    ib.set_view(eye=(-0.9, -1.6, 1.7), target=(1.6, 0.3, 0.0))
ib.run(world, args.sim_seconds, screenshot=args.screenshot)
