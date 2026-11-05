r"""Project 6 - Ramp and IMU: climb a 10 degree ramp and watch the tilt in /imu.

Isaac Sim side: a ramp (10 degrees, 2 m long) that ends in a flat deck, and an IMU on the robot published as /imu.
ROS 2 side (isaac/ros_nodes/ramp_climber.py): drives forward, reports the slope the IMU measures, stops on the deck.

    powershell -NoProfile -File scripts\isaac\run_isaac.ps1 isaac\scripts\p6_ramp.py [--gui] [--sim-seconds 90]
    pixi run isaac-ramp        (in a second terminal)
"""
import diffbot_isaac as ib

RAMP_START, RAMP_RUN, RAMP_ANGLE, DECK = 0.8, 2.0, 10.0, 1.0   # keep in step with the test

args = ib.common_args(__doc__).parse_args()
ib.start_app(gui=args.gui)
world = ib.build_world()
ib.build_room(width=8.0, depth=6.0)
rise = ib.add_ramp(x_start=RAMP_START, run=RAMP_RUN, angle_deg=RAMP_ANGLE, deck=DECK)
ib.add_diffbot(position=(0.0, 0.0, 0.0))
ib.add_drive_graph()
ib.add_imu()
print(f"[isaac] project 6 ready: /imu is published; the deck is {rise:.2f} m high", flush=True)
if args.screenshot:
    ib.add_light()
    ib.set_view(eye=(1.6, -3.0, 1.3), target=(1.7, 0.0, 0.2))
ib.run(world, args.sim_seconds, screenshot=args.screenshot)
