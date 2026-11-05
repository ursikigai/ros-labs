"""Shared building blocks for the three Isaac Sim projects.

Everything here runs INSIDE Isaac Sim (Python 3.11). The ROS 2 side (rclpy, Jazzy, Python 3.12) is a separate
process; the two talk over DDS, so nothing in this file imports rclpy.

What it provides
  start_app(...)        start Isaac Sim (headless or with a window) and enable the extensions the projects need
  convert_urdf()        turn the course's DiffBot URDF into a USD file (once)
  build_room(...)       ground plane, four walls and optional boxes
  add_diffbot(...)      reference the DiffBot USD into the scene and set up wheel drives and friction
  add_drive_graph(...)  OmniGraph: /cmd_vel -> wheels, /odom, /tf, /joint_states, /clock
  add_lidar(...)        PhysX lidar on the lidar link, published as sensor_msgs/LaserScan on /scan
  add_camera(...)       RGB + depth camera on the robot, published as /camera/image_raw, /camera/depth
  run(...)              step the simulation (optionally for a number of simulated seconds)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
URDF = os.path.join(ROOT, "isaac", "assets", "diffbot.urdf")
USD_DIR = os.path.join(ROOT, "build", "isaac", "diffbot")
USD = os.path.join(USD_DIR, "diffbot.usd")

PLACEMENT = "/World/diffbot"      # move/rotate this prim to place the robot
# The URDF importer writes a container prim named after the first link, with every link and the joints beneath it.
ROBOT = PLACEMENT + "/base_footprint"
BASE_FOOTPRINT = ROBOT + "/base_footprint"  # the articulation root (the URDF's first link)
WHEEL_RADIUS = 0.05
WHEEL_SEPARATION = 0.30

_app = None


def start_app(gui=False, cameras=False):
    """Start Isaac Sim. Must be the first thing a project does (before any omni/pxr import)."""
    global _app
    from isaacsim import SimulationApp

    _app = SimulationApp({"headless": not gui, "width": 1280, "height": 720})
    from isaacsim.core.utils.extensions import enable_extension

    for ext in ("isaacsim.ros2.bridge", "isaacsim.sensors.physx", "isaacsim.sensors.physics", "isaacsim.asset.importer.urdf"):
        enable_extension(ext)
    _app.update()
    return _app


def convert_urdf():
    """DiffBot URDF -> USD (cached). Importing into a file keeps every reference resolvable."""
    if os.path.exists(USD) and os.path.getmtime(USD) >= os.path.getmtime(URDF):
        return USD
    import shutil

    import omni.kit.commands

    shutil.rmtree(USD_DIR, ignore_errors=True)  # stale conversion of an older URDF
    os.makedirs(USD_DIR, exist_ok=True)
    _, cfg = omni.kit.commands.execute("URDFCreateImportConfig")
    cfg.merge_fixed_joints = False   # keep every link: the TF tree should match the course's URDF
    cfg.fix_base = False
    cfg.make_default_prim = True
    cfg.create_physics_scene = False  # the scene owns the physics scene
    cfg.import_inertia_tensor = True
    cfg.convex_decomp = False
    cfg.self_collision = False
    ok, path = omni.kit.commands.execute("URDFParseAndImportFile", urdf_path=URDF, import_config=cfg, dest_path=USD,
                                         get_articulation_root=True)
    if not ok or not os.path.exists(USD):
        raise RuntimeError(f"URDF import failed (ok={ok}, usd exists={os.path.exists(USD)})")
    print(f"[isaac] imported {URDF} -> {USD} (articulation root {path})", flush=True)
    return USD


def build_world():
    """A World (physics 60 Hz) with a ground plane."""
    from isaacsim.core.api import World

    world = World(stage_units_in_meters=1.0, physics_dt=1.0 / 60.0, rendering_dt=1.0 / 30.0)
    world.scene.add_default_ground_plane()
    return world


def _static_box(name, center, size, color=(0.7, 0.7, 0.7)):
    """A fixed collision box (a wall or an obstacle). center/size in metres."""
    from isaacsim.core.api.objects import FixedCuboid
    import numpy as np

    return FixedCuboid(prim_path=f"/World/room/{name}", name=name, position=np.array(center, dtype=float),
                       scale=np.array(size, dtype=float), color=np.array(color))


def build_room(width=8.0, depth=6.0, boxes=()):
    """Four walls around the origin plus optional boxes [(name, (x, y), (sx, sy))] 0.5 m high.

    The room spans x in [-width/2, width/2] and y in [-depth/2, depth/2]; the robot starts at the middle.
    """
    t, h = 0.1, 0.5
    _static_box("wall_n", (0, depth / 2 + t / 2, h / 2), (width + 2 * t, t, h))
    _static_box("wall_s", (0, -depth / 2 - t / 2, h / 2), (width + 2 * t, t, h))
    _static_box("wall_e", (width / 2 + t / 2, 0, h / 2), (t, depth, h))
    _static_box("wall_w", (-width / 2 - t / 2, 0, h / 2), (t, depth, h))
    for name, (x, y), (sx, sy) in boxes:
        _static_box(name, (x, y, h / 2), (sx, sy, h), color=(0.8, 0.4, 0.2))


def add_diffbot(position=(0.0, 0.0, 0.0), yaw_deg=0.0):
    """Put the DiffBot into the scene and make its wheels speed-controlled."""
    import omni.usd
    from isaacsim.core.utils.stage import add_reference_to_stage
    from pxr import Gf, UsdGeom, UsdPhysics, UsdShade, PhysxSchema

    usd = convert_urdf()
    add_reference_to_stage(usd_path=usd, prim_path=PLACEMENT)
    stage = omni.usd.get_context().get_stage()
    prim = stage.GetPrimAtPath(PLACEMENT)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*position))
    xf.AddRotateZOp().Set(float(yaw_deg))

    # Wheels: velocity control = no spring (stiffness 0), a damper that pulls the joint to the target speed.
    for joint in ("left_wheel_joint", "right_wheel_joint"):
        jprim = stage.GetPrimAtPath(f"{ROBOT}/joints/{joint}")
        drive = UsdPhysics.DriveAPI.Get(jprim, "angular")
        drive.GetStiffnessAttr().Set(0.0)
        drive.GetDampingAttr().Set(1000.0)
        drive.GetMaxForceAttr().Set(1000.0)

    # Friction: grippy wheels, a slippery caster (it is a fixed ball in the URDF, so it must slide).
    def material(path, mu, combine):
        mat = UsdShade.Material.Define(stage, path)
        pm = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
        pm.CreateStaticFrictionAttr().Set(mu)
        pm.CreateDynamicFrictionAttr().Set(mu)
        pm.CreateRestitutionAttr().Set(0.0)
        # With the default "average", a frictionless caster would still inherit half of the floor's friction.
        PhysxSchema.PhysxMaterialAPI.Apply(mat.GetPrim()).CreateFrictionCombineModeAttr().Set(combine)
        return mat

    grip = material("/World/physics_materials/grip", 1.5, "max")
    slip = material("/World/physics_materials/slip", 0.0, "min")
    # The colliders sit below an instanced "collisions" prim; a binding on that prim is inherited by its shapes.
    for link, mat in (("left_wheel_link", grip), ("right_wheel_link", grip), ("caster_link", slip), ("base_link", slip)):
        cprim = stage.GetPrimAtPath(f"{ROBOT}/{link}/collisions")
        UsdShade.MaterialBindingAPI.Apply(cprim).Bind(mat, UsdShade.Tokens.weakerThanDescendants, "physics")
    return BASE_FOOTPRINT


def add_drive_graph(context_domain_id=None):
    """/cmd_vel -> wheels, and /odom, /tf (odom->base_footprint->links), /joint_states, /clock out."""
    import omni.graph.core as og

    keys = og.Controller.Keys
    links = [f"{ROBOT}/{n}" for n in ("base_link", "left_wheel_link", "right_wheel_link", "caster_link", "lidar_link")]
    og.Controller.edit(
        {"graph_path": "/DriveGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("SimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("ClockPub", "isaacsim.ros2.bridge.ROS2PublishClock"),
                ("TwistSub", "isaacsim.ros2.bridge.ROS2SubscribeTwist"),
                ("BreakLin", "omni.graph.nodes.BreakVector3"),
                ("BreakAng", "omni.graph.nodes.BreakVector3"),
                ("Diff", "isaacsim.robot.wheeled_robots.DifferentialController"),
                ("Articulation", "isaacsim.core.nodes.IsaacArticulationController"),
                ("Odom", "isaacsim.core.nodes.IsaacComputeOdometry"),
                ("OdomPub", "isaacsim.ros2.bridge.ROS2PublishOdometry"),
                ("OdomTf", "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"),
                ("TfPub", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
                ("JointsPub", "isaacsim.ros2.bridge.ROS2PublishJointState"),
            ],
            keys.SET_VALUES: [
                ("Context.inputs:domain_id", int(context_domain_id if context_domain_id is not None else os.environ.get("ROS_DOMAIN_ID", 0))),
                ("TwistSub.inputs:topicName", "cmd_vel"),
                ("Diff.inputs:wheelRadius", WHEEL_RADIUS),
                ("Diff.inputs:wheelDistance", WHEEL_SEPARATION),
                ("Diff.inputs:maxLinearSpeed", 1.0),
                ("Diff.inputs:maxAngularSpeed", 3.0),
                ("Articulation.inputs:targetPrim", BASE_FOOTPRINT),
                ("Articulation.inputs:jointNames", ["left_wheel_joint", "right_wheel_joint"]),
                ("Odom.inputs:chassisPrim", BASE_FOOTPRINT),
                ("OdomPub.inputs:topicName", "odom"),
                ("OdomPub.inputs:odomFrameId", "odom"),
                ("OdomPub.inputs:chassisFrameId", "base_footprint"),
                ("OdomTf.inputs:parentFrameId", "odom"),
                ("OdomTf.inputs:childFrameId", "base_footprint"),
                ("OdomTf.inputs:topicName", "tf"),
                ("TfPub.inputs:parentPrim", BASE_FOOTPRINT),
                ("TfPub.inputs:targetPrims", links),
                ("TfPub.inputs:topicName", "tf"),
                ("JointsPub.inputs:targetPrim", BASE_FOOTPRINT),
                ("JointsPub.inputs:topicName", "joint_states"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "ClockPub.inputs:execIn"),
                ("OnTick.outputs:tick", "TwistSub.inputs:execIn"),
                ("OnTick.outputs:tick", "Articulation.inputs:execIn"),
                ("OnTick.outputs:tick", "Odom.inputs:execIn"),
                ("OnTick.outputs:tick", "OdomPub.inputs:execIn"),
                ("OnTick.outputs:tick", "OdomTf.inputs:execIn"),
                ("OnTick.outputs:tick", "TfPub.inputs:execIn"),
                ("OnTick.outputs:tick", "JointsPub.inputs:execIn"),
                ("Context.outputs:context", "ClockPub.inputs:context"),
                ("Context.outputs:context", "TwistSub.inputs:context"),
                ("Context.outputs:context", "OdomPub.inputs:context"),
                ("Context.outputs:context", "OdomTf.inputs:context"),
                ("Context.outputs:context", "TfPub.inputs:context"),
                ("Context.outputs:context", "JointsPub.inputs:context"),
                ("SimTime.outputs:simulationTime", "ClockPub.inputs:timeStamp"),
                ("SimTime.outputs:simulationTime", "OdomPub.inputs:timeStamp"),
                ("SimTime.outputs:simulationTime", "OdomTf.inputs:timeStamp"),
                ("SimTime.outputs:simulationTime", "TfPub.inputs:timeStamp"),
                ("SimTime.outputs:simulationTime", "JointsPub.inputs:timeStamp"),
                ("TwistSub.outputs:execOut", "Diff.inputs:execIn"),
                ("TwistSub.outputs:linearVelocity", "BreakLin.inputs:tuple"),
                ("TwistSub.outputs:angularVelocity", "BreakAng.inputs:tuple"),
                ("BreakLin.outputs:x", "Diff.inputs:linearVelocity"),     # Twist.linear.x  (forward speed)
                ("BreakAng.outputs:z", "Diff.inputs:angularVelocity"),    # Twist.angular.z (turn rate)
                ("Diff.outputs:velocityCommand", "Articulation.inputs:velocityCommand"),
                ("Odom.outputs:position", "OdomPub.inputs:position"),
                ("Odom.outputs:orientation", "OdomPub.inputs:orientation"),
                ("Odom.outputs:linearVelocity", "OdomPub.inputs:linearVelocity"),
                ("Odom.outputs:angularVelocity", "OdomPub.inputs:angularVelocity"),
                ("Odom.outputs:position", "OdomTf.inputs:translation"),
                ("Odom.outputs:orientation", "OdomTf.inputs:rotation"),
            ],
        },
    )


def add_lidar(max_range=6.0, resolution_deg=0.5, draw_rays=False):
    """A 360 degree PhysX lidar on the lidar link, published as sensor_msgs/LaserScan on /scan (frame lidar_link).

    PhysX lidar casts rays against the collision shapes: no rendering is needed, so it also works headless.
    """
    import omni.graph.core as og
    import omni.kit.commands
    from pxr import Gf

    ok, prim = omni.kit.commands.execute(
        "RangeSensorCreateLidar", path="/lidar", parent=f"{ROBOT}/lidar_link", min_range=0.12, max_range=max_range,
        draw_points=False, draw_lines=draw_rays, horizontal_fov=360.0, vertical_fov=1.0, horizontal_resolution=resolution_deg,
        vertical_resolution=1.0, rotation_rate=0.0, high_lod=False, yaw_offset=0.0, enable_semantics=False,
        translation=Gf.Vec3d(0.0, 0.0, 0.0))
    if not ok:
        raise RuntimeError("could not create the lidar")
    lidar_path = f"{ROBOT}/lidar_link/lidar"
    keys = og.Controller.Keys
    og.Controller.edit(
        {"graph_path": "/LidarGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("SimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("Beams", "isaacsim.sensors.physx.IsaacReadLidarBeams"),
                ("ScanPub", "isaacsim.ros2.bridge.ROS2PublishLaserScan"),
            ],
            keys.SET_VALUES: [
                ("Context.inputs:domain_id", int(os.environ.get("ROS_DOMAIN_ID", 0))),
                ("Beams.inputs:lidarPrim", lidar_path),
                ("ScanPub.inputs:topicName", "scan"),
                ("ScanPub.inputs:frameId", "lidar_link"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "Beams.inputs:execIn"),
                ("Beams.outputs:execOut", "ScanPub.inputs:execIn"),
                ("Context.outputs:context", "ScanPub.inputs:context"),
                ("SimTime.outputs:simulationTime", "ScanPub.inputs:timeStamp"),
                ("Beams.outputs:azimuthRange", "ScanPub.inputs:azimuthRange"),
                ("Beams.outputs:depthRange", "ScanPub.inputs:depthRange"),
                ("Beams.outputs:horizontalFov", "ScanPub.inputs:horizontalFov"),
                ("Beams.outputs:horizontalResolution", "ScanPub.inputs:horizontalResolution"),
                ("Beams.outputs:intensitiesData", "ScanPub.inputs:intensitiesData"),
                ("Beams.outputs:linearDepthData", "ScanPub.inputs:linearDepthData"),
                ("Beams.outputs:numCols", "ScanPub.inputs:numCols"),
                ("Beams.outputs:numRows", "ScanPub.inputs:numRows"),
                ("Beams.outputs:rotationRate", "ScanPub.inputs:rotationRate"),
            ],
        },
    )
    return lidar_path

def add_light(intensity=1500.0):
    """Cameras see nothing without light: a uniform dome light over the whole scene."""
    import omni.usd
    from pxr import UsdLux

    stage = omni.usd.get_context().get_stage()
    light = UsdLux.DomeLight.Define(stage, "/World/dome_light")
    light.CreateIntensityAttr(intensity)


def add_camera(width=320, height=240, hfov_deg=90.0, position=(0.12, 0.0, 0.10), pitch_deg=0.0):
    """An RGB + depth camera on the body, looking forward (pitch_deg=0) or tilted down by pitch_deg.

    /camera/image_raw   sensor_msgs/Image rgb8   /camera/depth   sensor_msgs/Image 32FC1 (metres)
    A prim called camera_link (x forward, z up, the ROS convention) is published in TF; the real USD camera is its child,
    turned so that it looks along +x. Like Isaac Sim's own tutorials, the images are stamped with frame camera_link
    rather than with a separate optical frame.
    """
    import math

    import omni.graph.core as og
    import omni.usd
    from pxr import Gf, UsdGeom

    stage = omni.usd.get_context().get_stage()
    link = f"{ROBOT}/base_link/camera_link"
    xf = UsdGeom.Xform.Define(stage, link)
    xf.AddTranslateOp().Set(Gf.Vec3d(*position))
    if pitch_deg:
        xf.AddRotateYOp().Set(float(pitch_deg))  # positive = the nose of the camera tips DOWN (right-hand rule about +y)
    cam_path = link + "/camera"
    cam = UsdGeom.Camera.Define(stage, cam_path)
    focal = 20.955  # mm (USD default aperture 20.955 mm wide)
    aperture = 2.0 * focal * math.tan(math.radians(hfov_deg) / 2.0)
    cam.CreateFocalLengthAttr(focal)
    cam.CreateHorizontalApertureAttr(aperture)
    cam.CreateVerticalApertureAttr(aperture * height / width)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.05, 20.0))
    cam.AddRotateXYZOp().Set(Gf.Vec3f(90.0, 0.0, -90.0))  # USD cameras look along -z; this makes it look along +x, z up

    keys = og.Controller.Keys
    og.Controller.edit(
        {"graph_path": "/CameraGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("SimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("RenderProduct", "isaacsim.core.nodes.IsaacCreateRenderProduct"),
                ("Rgb", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("Depth", "isaacsim.ros2.bridge.ROS2CameraHelper"),
                ("CameraTf", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
            ],
            keys.SET_VALUES: [
                ("Context.inputs:domain_id", int(os.environ.get("ROS_DOMAIN_ID", 0))),
                ("RenderProduct.inputs:cameraPrim", cam_path),
                ("RenderProduct.inputs:width", width),
                ("RenderProduct.inputs:height", height),
                ("Rgb.inputs:type", "rgb"),
                ("Rgb.inputs:topicName", "camera/image_raw"),
                ("Rgb.inputs:frameId", "camera_link"),
                ("Depth.inputs:type", "depth"),
                ("Depth.inputs:topicName", "camera/depth"),
                ("Depth.inputs:frameId", "camera_link"),
                ("CameraTf.inputs:parentPrim", BASE_FOOTPRINT),
                ("CameraTf.inputs:targetPrims", [link]),
                ("CameraTf.inputs:topicName", "tf"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "RenderProduct.inputs:execIn"),
                ("OnTick.outputs:tick", "CameraTf.inputs:execIn"),
                ("RenderProduct.outputs:execOut", "Rgb.inputs:execIn"),
                ("RenderProduct.outputs:execOut", "Depth.inputs:execIn"),
                ("RenderProduct.outputs:renderProductPath", "Rgb.inputs:renderProductPath"),
                ("RenderProduct.outputs:renderProductPath", "Depth.inputs:renderProductPath"),
                ("Context.outputs:context", "Rgb.inputs:context"),
                ("Context.outputs:context", "Depth.inputs:context"),
                ("Context.outputs:context", "CameraTf.inputs:context"),
                ("SimTime.outputs:simulationTime", "CameraTf.inputs:timeStamp"),
            ],
        },
    )
    return cam_path

def add_imu():
    """An IMU on base_link, published as sensor_msgs/Imu on /imu (frame base_link).

    orientation = how the body is tilted in the world (the IMU's own estimate, as a quaternion), angular_velocity in rad/s,
    linear_acceleration in m/s^2 INCLUDING gravity: a robot standing still on level ground reads z = +9.81.
    """
    import omni.graph.core as og
    import omni.kit.commands
    import usdrt.Sdf

    parent = f"{ROBOT}/base_link"
    ok, _ = omni.kit.commands.execute("IsaacSensorCreateImuSensor", path="/imu", parent=parent, sensor_period=-1,
                                      linear_acceleration_filter_size=10, angular_velocity_filter_size=10, orientation_filter_size=10)
    if not ok:
        raise RuntimeError("could not create the IMU")
    imu_path = parent + "/imu"
    keys = og.Controller.Keys
    og.Controller.edit(
        {"graph_path": "/ImuGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("SimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("Read", "isaacsim.sensors.physics.IsaacReadIMU"),
                ("Pub", "isaacsim.ros2.bridge.ROS2PublishImu"),
            ],
            keys.SET_VALUES: [
                ("Context.inputs:domain_id", int(os.environ.get("ROS_DOMAIN_ID", 0))),
                ("Read.inputs:readGravity", True),
                ("Pub.inputs:topicName", "imu"),
                ("Pub.inputs:frameId", "base_link"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "Read.inputs:execIn"),
                ("Read.outputs:execOut", "Pub.inputs:execIn"),
                ("Context.outputs:context", "Pub.inputs:context"),
                ("SimTime.outputs:simulationTime", "Pub.inputs:timeStamp"),
                ("Read.outputs:angVel", "Pub.inputs:angularVelocity"),
                ("Read.outputs:linAcc", "Pub.inputs:linearAcceleration"),
                ("Read.outputs:orientation", "Pub.inputs:orientation"),
            ],
        },
    )
    og.Controller.set(og.Controller.attribute("/ImuGraph/Read.inputs:imuPrim"), [usdrt.Sdf.Path(imu_path)])
    return imu_path


def add_marker(name, center, size, color, yaw_deg=0.0, z=0.002, thickness=0.004):
    """A flat coloured patch on the floor (visual only, no collision: the robot just drives over it). center/size in metres."""
    import math

    import numpy as np
    from isaacsim.core.api.objects import VisualCuboid

    half = math.radians(yaw_deg) / 2.0
    return VisualCuboid(prim_path=f"/World/floor/{name}", name=name, position=np.array([center[0], center[1], z], dtype=float),
                        orientation=np.array([math.cos(half), 0.0, 0.0, math.sin(half)]),
                        scale=np.array([size[0], size[1], thickness], dtype=float), color=np.array(color, dtype=float))


def add_ramp(x_start=0.8, run=2.0, angle_deg=10.0, deck=1.0, width=1.2, thickness=0.2):
    """A straight ramp rising along +x from the floor at x_start, then a flat deck. Solid (the robot's wheels grip it).

    Returns (height of the deck in metres). The ramp is a tilted box whose top surface starts exactly at floor level.
    """
    import math

    import numpy as np
    from isaacsim.core.api.objects import FixedCuboid

    th = math.radians(angle_deg)
    rise = run * math.tan(th)
    slant = run / math.cos(th)
    # centre = middle of the top surface, moved down along the surface normal by half the thickness
    cx = x_start + run / 2.0 + math.sin(th) * thickness / 2.0
    cz = rise / 2.0 - math.cos(th) * thickness / 2.0
    half = -th / 2.0  # rotation about +y by -angle raises the +x end
    FixedCuboid(prim_path="/World/room/ramp", name="ramp", position=np.array([cx, 0.0, cz]),
                orientation=np.array([math.cos(half), 0.0, math.sin(half), 0.0]),
                scale=np.array([slant, width, thickness]), color=np.array([0.55, 0.55, 0.6]))
    FixedCuboid(prim_path="/World/room/deck", name="deck", position=np.array([x_start + run + deck / 2.0, 0.0, rise - thickness / 2.0]),
                scale=np.array([deck, width, thickness]), color=np.array([0.45, 0.5, 0.6]))
    return rise


def set_view(eye, target):
    """Point the viewport camera of the Isaac Sim window (only has an effect with --gui)."""
    from isaacsim.core.utils.viewports import set_camera_view

    set_camera_view(eye=list(eye), target=list(target), camera_prim_path="/OmniverseKit_Persp")


def save_viewport(path, size=(1600, 900)):
    """Save what the Isaac Sim viewport shows (needs the window: --gui)."""
    from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    viewport = get_active_viewport()
    viewport.resolution = size
    for _ in range(30):  # let the new resolution render a few frames first
        _app.update()
    capture_viewport_to_file(viewport, path)
    for _ in range(200):
        _app.update()
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            break
    print(f"[isaac] saved viewport picture {path}", flush=True)


def run(world, sim_seconds=None, report_every=5.0, screenshot=None):
    """Play and step the simulation. sim_seconds=None runs until the process is killed.

    With screenshot=PATH (and --gui) a picture of the viewport is saved when the simulated time is reached, then the program ends.
    """
    world.reset()
    world.play()
    last = -report_every
    while _app.is_running():
        world.step(render=True)
        t = world.current_time
        if t - last >= report_every:
            print(f"[isaac] simulated time {t:6.1f} s", flush=True)
            last = t
        if sim_seconds is not None and t >= sim_seconds:
            break
    if screenshot:
        save_viewport(screenshot)
    print("[isaac] stopping", flush=True)
    _app.close()

def common_args(description):
    import argparse

    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--gui", action="store_true", help="open the Isaac Sim window instead of running headless")
    ap.add_argument("--sim-seconds", type=float, default=None, help="stop after this many simulated seconds (default: run until killed)")
    ap.add_argument("--screenshot", default=None, metavar="PNG", help="with --gui: save a picture of the viewport at --sim-seconds, then exit")
    return ap
