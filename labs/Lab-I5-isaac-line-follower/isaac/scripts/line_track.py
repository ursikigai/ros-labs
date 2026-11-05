"""The black line of project 5 as plain maths (no Isaac Sim import, so the ROS 2 side and the tests can use it too).

The line starts straight along +x (so the robot, standing at the origin and looking along +x, is already on it), then
bends smoothly 0.6 m to the left and runs straight on:

    y(x) = 0                              x <= BEND_START
    y(x) = BEND_SIDE * s(t)               t = (x - BEND_START) / BEND_LENGTH,  s(t) = 3t^2 - 2t^3  (a smooth step)
    y(x) = BEND_SIDE                      x >= BEND_START + BEND_LENGTH
"""
import math

X_START = -0.4
X_END = 3.5
BEND_START = 0.8
BEND_LENGTH = 2.0
BEND_SIDE = 0.6
LINE_WIDTH = 0.05


def track_y(x):
    t = min(1.0, max(0.0, (x - BEND_START) / BEND_LENGTH))
    return BEND_SIDE * (3 * t * t - 2 * t * t * t)


def segments(step=0.1):
    """[(centre_x, centre_y, length, yaw_degrees)] of short straight pieces that together draw the line."""
    out = []
    n = int(round((X_END - X_START) / step))
    for i in range(n):
        x0, x1 = X_START + i * step, X_START + (i + 1) * step
        y0, y1 = track_y(x0), track_y(x1)
        length = math.hypot(x1 - x0, y1 - y0)
        out.append(((x0 + x1) / 2, (y0 + y1) / 2, length * 1.25, math.degrees(math.atan2(y1 - y0, x1 - x0))))  # 25 % overlap: no gaps
    return out


def distance_to_line(x, y):
    """Shortest distance from the point (x, y) to the line (sampled every 5 mm)."""
    best = 1e9
    n = int((X_END - X_START) / 0.005)
    for i in range(n + 1):
        px = X_START + i * 0.005
        best = min(best, math.hypot(x - px, y - track_y(px)))
    return best
