from __future__ import annotations

"""Simple 2D grid pathfinding utilities (used by NPC roaming/navigation)."""

import heapq
import math
from dataclasses import dataclass
from typing import Iterable, Iterator


Cell = tuple[int, int]  # (ix, iy)


@dataclass(frozen=True)
class AABB:
    """Axis-aligned bounding box in XY (world space)."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def inflated(self, r: float) -> "AABB":
        return AABB(self.xmin - r, self.ymin - r, self.xmax + r, self.ymax + r)

    def contains_xy(self, x: float, y: float) -> bool:
        return (self.xmin <= x <= self.xmax) and (self.ymin <= y <= self.ymax)


@dataclass(frozen=True)
class NavGrid:
    """A 2D occupancy grid in XY with fixed-size square cells."""

    xy_min: tuple[float, float]
    xy_max: tuple[float, float]
    cell_size: float
    width: int
    height: int
    blocked: tuple[tuple[bool, ...], ...]  # [iy][ix]

    @staticmethod
    def build(
        *,
        xy_min: tuple[float, float],
        xy_max: tuple[float, float],
        cell_size: float,
        obstacles: Iterable[AABB],
        inflate: float = 0.0,
    ) -> "NavGrid":
        """
        Build a NavGrid by rasterizing AABB obstacles onto a cell grid.

        Args:
            xy_min: World-space min bounds (x, y).
            xy_max: World-space max bounds (x, y).
            cell_size: Size of one cell in world units.
            obstacles: AABBs in XY to mark as blocked.
            inflate: Obstacle inflation radius (useful for accounting for agent radius).
        """
        xmin, ymin = xy_min
        xmax, ymax = xy_max
        if xmax <= xmin or ymax <= ymin:
            raise ValueError("Invalid bounds")
        if cell_size <= 0:
            raise ValueError("cell_size must be > 0")

        width = int(math.ceil((xmax - xmin) / cell_size))
        height = int(math.ceil((ymax - ymin) / cell_size))

        inflated = [o.inflated(inflate) for o in obstacles]

        rows: list[list[bool]] = []
        for iy in range(height):
            row: list[bool] = []
            for ix in range(width):
                # Mark blocked if the obstacle intersects the cell area (more conservative than
                # sampling only the center; avoids routes that "clip" building corners).
                cx0 = xmin + ix * cell_size
                cy0 = ymin + iy * cell_size
                cx1 = cx0 + cell_size
                cy1 = cy0 + cell_size
                row.append(any(_aabb_intersects(cx0, cy0, cx1, cy1, o) for o in inflated))
            rows.append(row)

        return NavGrid(
            xy_min=xy_min,
            xy_max=xy_max,
            cell_size=cell_size,
            width=width,
            height=height,
            blocked=tuple(tuple(r) for r in rows),
        )

    def in_bounds(self, c: Cell) -> bool:
        """Return True if the cell index is inside the grid bounds."""
        ix, iy = c
        return 0 <= ix < self.width and 0 <= iy < self.height

    def is_blocked(self, c: Cell) -> bool:
        """Return True if the cell is blocked by an obstacle."""
        ix, iy = c
        return self.blocked[iy][ix]

    def world_to_cell(self, x: float, y: float) -> Cell:
        """Convert world-space XY to a clamped grid cell index."""
        xmin, ymin = self.xy_min
        ix = int(math.floor((x - xmin) / self.cell_size))
        iy = int(math.floor((y - ymin) / self.cell_size))
        # Clamp into bounds (callers can still check is_blocked).
        ix = max(0, min(self.width - 1, ix))
        iy = max(0, min(self.height - 1, iy))
        return (ix, iy)

    def cell_center_world(self, c: Cell) -> tuple[float, float]:
        """Return the world-space center of a cell."""
        ix, iy = c
        xmin, ymin = self.xy_min
        x = xmin + (ix + 0.5) * self.cell_size
        y = ymin + (iy + 0.5) * self.cell_size
        return (x, y)

    def neighbors4(self, c: Cell) -> Iterator[Cell]:
        """Iterate 4-connected, unblocked neighbor cells."""
        ix, iy = c
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (ix + dx, iy + dy)
            if self.in_bounds(n) and (not self.is_blocked(n)):
                yield n


def astar(grid: NavGrid, start: Cell, goal: Cell) -> list[Cell] | None:
    """
    4-connected A* path on a NavGrid.

    Returns a list of cells from start->goal inclusive, or None if no path.
    """
    if not grid.in_bounds(start) or not grid.in_bounds(goal):
        return None
    if grid.is_blocked(start) or grid.is_blocked(goal):
        return None

    def h(c: Cell) -> float:
        # Manhattan distance is admissible for 4-connected movement.
        return float(abs(c[0] - goal[0]) + abs(c[1] - goal[1]))

    open_heap: list[tuple[float, float, Cell]] = []
    heapq.heappush(open_heap, (h(start), 0.0, start))

    came_from: dict[Cell, Cell] = {}
    g_score: dict[Cell, float] = {start: 0.0}

    while open_heap:
        _, g, cur = heapq.heappop(open_heap)
        if cur == goal:
            return _reconstruct(came_from, cur)

        # Stale entry check
        if g > g_score.get(cur, float("inf")):
            continue

        for nb in grid.neighbors4(cur):
            ng = g + 1.0
            if ng < g_score.get(nb, float("inf")):
                came_from[nb] = cur
                g_score[nb] = ng
                heapq.heappush(open_heap, (ng + h(nb), ng, nb))

    return None


def simplify_path_cells(path: list[Cell]) -> list[Cell]:
    """
    Drop intermediate collinear points from a 4-connected grid path.
    """
    if len(path) <= 2:
        return path
    out: list[Cell] = [path[0]]
    prev = path[0]
    prev_dir = (path[1][0] - prev[0], path[1][1] - prev[1])
    for i in range(1, len(path) - 1):
        cur = path[i]
        nxt = path[i + 1]
        d = (nxt[0] - cur[0], nxt[1] - cur[1])
        if d != prev_dir:
            out.append(cur)
        prev_dir = d
        prev = cur
    out.append(path[-1])
    return out


def cells_to_waypoints(grid: NavGrid, path: list[Cell]) -> list[tuple[float, float]]:
    return [grid.cell_center_world(c) for c in path]


def _reconstruct(came_from: dict[Cell, Cell], cur: Cell) -> list[Cell]:
    path = [cur]
    while cur in came_from:
        cur = came_from[cur]
        path.append(cur)
    path.reverse()
    return path


def _aabb_intersects(
    ax0: float,
    ay0: float,
    ax1: float,
    ay1: float,
    b: AABB,
) -> bool:
    # Separating axis test for 2D AABBs.
    if ax1 < b.xmin or ax0 > b.xmax:
        return False
    if ay1 < b.ymin or ay0 > b.ymax:
        return False
    return True


