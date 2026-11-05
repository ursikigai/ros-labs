import math

from diffbot_navigation import reactive

# ---------------------------------------------------------------- reactive


def scan(front=10.0, left=10.0, right=10.0, n=360):
    """Build a 360-ray scan with chosen minimum distances in the 3 sectors."""
    inc = 2 * math.pi / n
    ranges = []
    for i in range(n):
        a = -math.pi + i * inc
        if abs(a) <= math.radians(30):
            ranges.append(front)
        elif math.radians(30) < a <= math.radians(90):
            ranges.append(left)
        elif -math.radians(90) <= a < -math.radians(30):
            ranges.append(right)
        else:
            ranges.append(10.0)
    return ranges, -math.pi, inc


def test_reactive_clear_path_drives_straight():
    v, w, d = reactive.compute_command(*scan())
    assert v == reactive.MAX_V and w == 0.0 and d == 0


def test_reactive_blocked_front_stops_and_turns_to_open_side():
    v, w, d = reactive.compute_command(*scan(front=0.3, left=3.0, right=0.5))
    assert v == 0.0 and w > 0 and d == 1
    v, w, d = reactive.compute_command(*scan(front=0.3, left=0.5, right=3.0))
    assert v == 0.0 and w < 0 and d == -1


def test_reactive_keeps_turn_direction_until_clear():
    ranges = scan(front=0.7)  # between stop and slow distance
    v, w, d = reactive.compute_command(*ranges, turn_dir=-1)
    assert w < 0 and d == -1
    v, w, d = reactive.compute_command(*scan(front=3.0), turn_dir=-1)
    assert d == 0 and v == reactive.MAX_V


def test_reactive_handles_inf_and_nan():
    ranges, amin, inc = scan()
    ranges[0] = float("inf")
    ranges[1] = float("nan")
    v, _, _ = reactive.compute_command(ranges, amin, inc)
    assert v > 0
