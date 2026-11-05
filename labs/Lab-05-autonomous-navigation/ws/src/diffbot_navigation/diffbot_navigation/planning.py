"""Grid path planning: inflation, A*, shortcutting (pure Python + numpy, no ROS).

Adapted from the "Straight Line Planner" idea in upstream/robotics_essentials_ros2
(exercise 5): the planner is a separate component answering "get me a path from A to B".
Here it upgrades the straight line to obstacle-aware A*.
"""
import heapq
import math

import numpy as np

SQRT2 = math.sqrt(2.0)
NEIGHBOURS = [
    (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
    (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2),
]


def inflate(occupied, radius_cells):
    """Grow obstacles by `radius_cells` (disk structuring element), numpy only."""
    occupied = np.asarray(occupied, dtype=bool)
    if radius_cells <= 0:
        return occupied.copy()
    rows, cols = occupied.shape
    out = occupied.copy()
    r = int(radius_cells)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx > r * r or (dy == 0 and dx == 0):
                continue
            src_r = slice(max(0, -dy), min(rows, rows - dy))
            src_c = slice(max(0, -dx), min(cols, cols - dx))
            dst_r = slice(max(0, dy), min(rows, rows + dy))
            dst_c = slice(max(0, dx), min(cols, cols + dx))
            out[dst_r, dst_c] |= occupied[src_r, src_c]
    return out


def nearest_free(blocked, cell, max_radius):
    """Closest free cell to `cell` within `max_radius` cells, or None."""
    r0, c0 = cell
    rows, cols = blocked.shape
    best, best_d = None, None
    for r in range(max(0, r0 - max_radius), min(rows, r0 + max_radius + 1)):
        for c in range(max(0, c0 - max_radius), min(cols, c0 + max_radius + 1)):
            if not blocked[r, c]:
                d = (r - r0) ** 2 + (c - c0) ** 2
                if best_d is None or d < best_d:
                    best, best_d = (r, c), d
    return best


def astar(blocked, start, goal):
    """8-connected A* on a boolean grid (True = blocked). Cells are (row, col).

    Returns a list of cells from start to goal, or None if no path exists.
    """
    rows, cols = blocked.shape
    if blocked[start] or blocked[goal]:
        return None

    def h(cell):  # octile distance
        dy, dx = abs(cell[0] - goal[0]), abs(cell[1] - goal[1])
        return (dx + dy) + (SQRT2 - 2.0) * min(dx, dy)

    open_heap = [(h(start), 0.0, start)]
    g_cost = {start: 0.0}
    parent = {start: None}
    closed = set()
    while open_heap:
        _, g, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        if cur == goal:
            path = []
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            return path[::-1]
        closed.add(cur)
        for dr, dc, step in NEIGHBOURS:
            nr, nc = cur[0] + dr, cur[1] + dc
            if nr < 0 or nc < 0 or nr >= rows or nc >= cols or blocked[nr, nc]:
                continue
            if dr and dc and (blocked[cur[0] + dr, cur[1]] or blocked[cur[0], cur[1] + dc]):
                continue  # no cutting corners
            ng = g + step
            if ng < g_cost.get((nr, nc), float("inf")):
                g_cost[(nr, nc)] = ng
                parent[(nr, nc)] = cur
                heapq.heappush(open_heap, (ng + h((nr, nc)), ng, (nr, nc)))
    return None


def line_of_sight(blocked, a, b):
    """True if the straight segment between cells a and b crosses no blocked cell."""
    steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 1
    for i in range(steps + 1):
        t = i / steps
        r = int(round(a[0] + t * (b[0] - a[0])))
        c = int(round(a[1] + t * (b[1] - a[1])))
        if blocked[r, c]:
            return False
    return True


def shortcut(path, blocked):
    """Greedy string-pulling: drop intermediate cells that are visible from an earlier one."""
    if len(path) <= 2:
        return list(path)
    out = [path[0]]
    i = 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not line_of_sight(blocked, path[i], path[j]):
            j -= 1
        out.append(path[j])
        i = j
    return out


def resample(points, spacing=0.1):
    """Densify a polyline [(x, y), ...] so consecutive points are <= spacing apart."""
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        dist = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(dist / spacing)))
        for k in range(1, n + 1):
            t = k / n
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def path_length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
