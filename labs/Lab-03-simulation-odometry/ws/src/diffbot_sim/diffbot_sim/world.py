"""2D occupancy-grid world with ray casting (pure Python + numpy, no ROS)."""
import math

import numpy as np


class GridWorld:
    """grid[row, col] is True when occupied. Row index = y, col index = x."""

    def __init__(self, grid, resolution=0.05):
        self.grid = np.asarray(grid, dtype=bool)
        self.resolution = float(resolution)
        self.rows, self.cols = self.grid.shape
        self.width = self.cols * self.resolution
        self.height = self.rows * self.resolution

    # --- queries -------------------------------------------------------
    def world_to_cell(self, x, y):
        return int(math.floor(y / self.resolution)), int(math.floor(x / self.resolution))

    def cell_to_world(self, row, col):
        """Centre of a cell."""
        return (col + 0.5) * self.resolution, (row + 0.5) * self.resolution

    def is_occupied(self, x, y):
        row, col = self.world_to_cell(x, y)
        if row < 0 or col < 0 or row >= self.rows or col >= self.cols:
            return True  # outside the map counts as a wall
        return bool(self.grid[row, col])

    def circle_collides(self, x, y, radius, samples=12):
        """Approximate circle-vs-grid test using the centre and a ring of points."""
        if self.is_occupied(x, y):
            return True
        for k in range(samples):
            a = 2.0 * math.pi * k / samples
            if self.is_occupied(x + radius * math.cos(a), y + radius * math.sin(a)):
                return True
        return False

    def raycast(self, ox, oy, angles, max_range):
        """Distance to the first occupied cell along each world-frame angle.

        Returns an array the same shape as `angles`; `inf` where nothing is hit.
        """
        angles = np.asarray(angles, dtype=float)
        step = self.resolution * 0.5
        dists = np.arange(0.0, max_range + step, step)  # (S,)
        xs = ox + np.outer(np.cos(angles), dists)  # (A, S)
        ys = oy + np.outer(np.sin(angles), dists)
        cols = np.floor(xs / self.resolution).astype(int)
        rows = np.floor(ys / self.resolution).astype(int)
        outside = (rows < 0) | (cols < 0) | (rows >= self.rows) | (cols >= self.cols)
        hit = outside.copy()
        inside = ~outside
        hit[inside] = self.grid[rows[inside], cols[inside]]
        any_hit = hit.any(axis=1)
        first = hit.argmax(axis=1)
        ranges = np.where(any_hit, dists[first], np.inf)
        return np.where(ranges > max_range, np.inf, ranges)

    def to_occupancy_data(self):
        """Flat row-major list of int8 values (0 free, 100 occupied) for OccupancyGrid."""
        return (self.grid.astype(np.int8) * 100).flatten().tolist()


def _fill(grid, res, x0, y0, x1, y1):
    r0, r1 = int(round(y0 / res)), int(round(y1 / res))
    c0, c1 = int(round(x0 / res)), int(round(x1 / res))
    grid[r0:r1, c0:c1] = True


def default_world(resolution=0.05):
    """10 m x 8 m room with two staggered walls and a box: needs an S-shaped path."""
    res = resolution
    width, height = 10.0, 8.0
    grid = np.zeros((int(height / res), int(width / res)), dtype=bool)
    t = 0.1  # boundary wall thickness
    _fill(grid, res, 0, 0, width, t)
    _fill(grid, res, 0, height - t, width, height)
    _fill(grid, res, 0, 0, t, height)
    _fill(grid, res, width - t, 0, width, height)
    _fill(grid, res, 3.0, 0.0, 3.2, 5.0)  # wall 1: gap at the top
    _fill(grid, res, 6.0, 3.0, 6.2, 8.0)  # wall 2: gap at the bottom
    _fill(grid, res, 4.4, 5.5, 5.2, 6.3)  # free-standing box
    return GridWorld(grid, res)
