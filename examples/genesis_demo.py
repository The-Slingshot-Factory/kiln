from __future__ import annotations

import argparse
import math
from pathlib import Path
import random
import time

from kiln.actors import CarBlock, CarBlockConfig, ControlMode, DiscreteAction, NPCBlock, NPCBlockConfig
from kiln.actors.pathfinding import AABB, NavGrid
from kiln.sim.genesis import GenesisSim, GenesisSimConfig


def _camera_height_for_bounds(
    *,
    xy_min: tuple[float, float],
    xy_max: tuple[float, float],
    fov_deg: float,
    margin: float = 1.15,
) -> float:
    half_extent = max(
        abs(xy_min[0]),
        abs(xy_min[1]),
        abs(xy_max[0]),
        abs(xy_max[1]),
    )
    half_fov = math.radians(float(fov_deg)) * 0.5
    return (half_extent / max(1e-6, math.tan(half_fov))) * margin


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiln + Genesis smoke test (headless).")
    parser.add_argument("--steps", type=int, default=600, help="Number of simulation steps to run.")
    parser.add_argument("--npcs", type=int, default=5, help="Number of NPC blocks.")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed.")
    parser.add_argument(
        "--gs-backend",
        choices=["cpu", "gpu", "cuda", "vulkan"],
        default="gpu",
        help="Genesis backend selector. Use cpu for CPU baselines; gpu/cuda for CUDA runs (when available).",
    )
    parser.add_argument("--bench", action="store_true", help="Benchmark mode: disable rendering and print timing stats.")
    parser.add_argument(
        "--bench-mode",
        choices=["full", "physics_only", "python_only"],
        default="full",
        help="Benchmark variant. full=normal loop, physics_only=only sim.step(), python_only=policy/control only. "
        "Only used when --bench.",
    )
    parser.add_argument("--bench-steps", type=int, default=30, help="Number of benchmarked steps (excludes warmup).")
    parser.add_argument("--bench-warmup", type=int, default=10, help="Warmup steps before benchmarking.")
    parser.add_argument(
        "--bench-breakdown",
        action="store_true",
        help="Print timing breakdown (policy/control/sim/render) in benchmark mode.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Run cProfile during the benchmark window and print top entries (sorted by cumulative time).",
    )
    parser.add_argument("--profile-top", type=int, default=30, help="Top N cProfile entries to print.")
    parser.add_argument("--collisions", action="store_true", help="Enable car collision begin/end polling.")
    parser.add_argument(
        "--collision-min-force",
        type=float,
        default=0.0,
        help="Minimum contact force magnitude to count a collision contact (only used when --collisions).",
    )
    parser.add_argument(
        "--control-mode",
        choices=["kinematic", "force_torque"],
        default="kinematic",
        help="Control mode for all blocks.",
    )
    parser.add_argument(
        "--gif",
        nargs="?",
        const="examples/renders/genesis_demo.gif",
        default=None,
        help="If set, save a rendered GIF to this path. If provided without a value, "
        "defaults to examples/renders/genesis_demo.gif",
    )
    parser.add_argument("--gif-fps", type=int, default=30, help="GIF playback FPS.")
    parser.add_argument("--gif-every", type=int, default=2, help="Capture every N sim steps.")
    parser.add_argument("--gif-res", type=int, default=256, help="GIF square resolution (pixels).")
    parser.add_argument(
        "--camera-pos",
        type=float,
        nargs=3,
        default=None,
        metavar=("X", "Y", "Z"),
        help="Camera position. Default: bird's-eye above the map.",
    )
    parser.add_argument(
        "--camera-lookat",
        type=float,
        nargs=3,
        default=None,
        metavar=("X", "Y", "Z"),
        help="Camera look-at target. Default: map center.",
    )
    parser.add_argument(
        "--camera-up",
        type=float,
        nargs=3,
        default=(0.0, 1.0, 0.0),
        metavar=("X", "Y", "Z"),
        help="Camera up vector. For bird's-eye, use (0,1,0) so it's not parallel to look direction.",
    )
    parser.add_argument("--camera-fov", type=float, default=60.0, help="Camera field of view (degrees).")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    control_mode = ControlMode.KINEMATIC if args.control_mode == "kinematic" else ControlMode.FORCE_TORQUE
    bench_mode = args.bench_mode if args.bench else "full"

    # More stable defaults for contact-heavy scenes (fast pedestrians + buildings).
    sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=8, headless=True, seed=args.seed, backend=args.gs_backend))
    sim.create_programmatic_scene()

    # Map bounds (used for camera framing + nav grid later)
    MAP_XY_MIN = (-12.0, -12.0)
    MAP_XY_MAX = (12.0, 12.0)

    # Optional: capture rendered frames to a GIF.
    gif_writer = None
    cam = None
    gif_path: Path | None = None
    if args.gif is not None and (not args.bench):
        import importlib

        # Lazy import; only needed for gif export.
        # Use dynamic import to avoid type-checker issues in environments without imageio installed.
        imageio = importlib.import_module("imageio.v2")

        gif_path = Path(args.gif)
        gif_path.parent.mkdir(parents=True, exist_ok=True)

        if sim.scene is None:
            raise RuntimeError("Genesis scene was not created.")
        # Bird's-eye default if the user didn't specify a camera.
        if args.camera_pos is None:
            h = _camera_height_for_bounds(xy_min=MAP_XY_MIN, xy_max=MAP_XY_MAX, fov_deg=args.camera_fov, margin=1.2)
            cam_pos = (0.0, 0.0, h)
        else:
            cam_pos = tuple(args.camera_pos)

        cam_lookat = (0.0, 0.0, 0.0) if args.camera_lookat is None else tuple(args.camera_lookat)

        # IMPORTANT: Genesis camera defaults to far=20.0. For bird's-eye views the camera height
        # can exceed that, which would clip out the ground/car/pedestrians and make the GIF look static.
        cam_dist = math.dist(cam_pos, cam_lookat)
        cam_far = max(50.0, cam_dist * 3.0)

        cam = sim.scene.add_camera(
            res=(args.gif_res, args.gif_res),
            pos=cam_pos,
            lookat=cam_lookat,
            up=tuple(args.camera_up),
            fov=args.camera_fov,
            GUI=False,
            near=0.1,
            far=cam_far,
        )
        gif_writer = imageio.get_writer(str(gif_path), mode="I", duration=1.0 / float(args.gif_fps))

    # Colors (category-coded)
    car_color = (1.0, 0.1, 0.1)  # red
    npc_color = (0.15, 0.55, 1.0)  # blue (pedestrians)
    building_color = (0.60, 0.60, 0.60)  # gray (buildings)

    # Buildings (static blocks).
    # Procedural "small city": a grid of blocks with roads between them and varied building footprints/heights.
    buildings: list[dict[str, object]] = []
    building_aabbs: list[AABB] = []
    CITY_N = 5  # buildings per axis
    ROAD_W = 1.5
    map_w = MAP_XY_MAX[0] - MAP_XY_MIN[0]
    map_h = MAP_XY_MAX[1] - MAP_XY_MIN[1]
    cell_w = (map_w - (CITY_N + 1) * ROAD_W) / CITY_N
    cell_h = (map_h - (CITY_N + 1) * ROAD_W) / CITY_N
    cell_margin = 0.25  # keep some sidewalk inside each block cell

    building_idx = 0
    for ix in range(CITY_N):
        for iy in range(CITY_N):
            cell_xmin = MAP_XY_MIN[0] + ROAD_W + ix * (cell_w + ROAD_W)
            cell_ymin = MAP_XY_MIN[1] + ROAD_W + iy * (cell_h + ROAD_W)

            # Random footprint within the cell.
            max_bx = max(1.0, cell_w - 2.0 * cell_margin)
            max_by = max(1.0, cell_h - 2.0 * cell_margin)
            bx = rng.uniform(1.2, max_bx)
            by = rng.uniform(1.2, max_by)
            ox = rng.uniform(cell_margin, max( cell_margin, cell_w - cell_margin - bx))
            oy = rng.uniform(cell_margin, max( cell_margin, cell_h - cell_margin - by))

            xmin = cell_xmin + ox
            ymin = cell_ymin + oy
            xmax = xmin + bx
            ymax = ymin + by
            cx = (xmin + xmax) * 0.5
            cy = (ymin + ymax) * 0.5

            # Height (slightly taller near center).
            dist = math.hypot(cx, cy) / max(1e-6, max(abs(MAP_XY_MAX[0]), abs(MAP_XY_MAX[1])))
            sz = rng.uniform(2.0, 5.0) + (1.0 - dist) * rng.uniform(0.0, 3.0)

            ent = sim.add_box(
                name=f"building_{building_idx}",
                size=(bx, by, sz),
                position=(cx, cy, sz / 2.0),
                mass=0.0,
                color=building_color,
            )
            buildings.append({"entity": ent, "cx": cx, "cy": cy, "sx": bx, "sy": by, "sz": sz})
            building_aabbs.append(AABB(xmin, ymin, xmax, ymax))
            building_idx += 1

    # Navigation grid for pedestrians (plans around buildings).
    nav_grid = NavGrid.build(
        xy_min=MAP_XY_MIN,
        xy_max=MAP_XY_MAX,
        cell_size=0.5,
        obstacles=building_aabbs,
        inflate=0.55,  # pedestrian clearance (keep them well away from building walls)
    )

    def sample_free_xy(*, preferred: tuple[float, float] | None = None) -> tuple[float, float]:
        if preferred is not None:
            c = nav_grid.world_to_cell(preferred[0], preferred[1])
            if not nav_grid.is_blocked(c):
                return nav_grid.cell_center_world(c)

        for _ in range(5000):
            ix = rng.randrange(nav_grid.width)
            iy = rng.randrange(nav_grid.height)
            c = (ix, iy)
            if nav_grid.is_blocked(c):
                continue
            return nav_grid.cell_center_world(c)
        raise RuntimeError("Failed to sample a free spawn cell.")

    car = CarBlock(
        sim,
        name="car",
        position=(*sample_free_xy(preferred=(0.0, MAP_XY_MIN[1] + ROAD_W * 0.5)), 0.15),
        config=CarBlockConfig(control_mode=control_mode, color=car_color),
    )

    npcs: list[NPCBlock] = []
    for i in range(args.npcs):
        x, y = sample_free_xy()
        npc = NPCBlock(
            sim,
            name=f"npc_{i}",
            position=(x, y, 0.15),
            config=NPCBlockConfig(
                control_mode=control_mode,
                roam_xy_min=MAP_XY_MIN,
                roam_xy_max=MAP_XY_MAX,
                # Faster pedestrians so pathing/nav can be stress-tested visually.
                cruise_speed=4.0,
                max_speed=6.0,
                speed_delta=1.0,
                turn_rate=3.0,
                heading_threshold=0.25,
                waypoint_tolerance=0.6,
                color=npc_color,
                # Smaller, square footprint (pedestrian-like).
                size=(0.25, 0.25, 0.5),
            ),
            rng=random.Random(args.seed + 1000 + i),
            nav_grid=nav_grid,
        )
        npcs.append(npc)

    # Build once after all entities are added.
    sim.build()

    dt = sim.config.dt

    # Entities are static in this demo; precompute lists to avoid per-step allocations.
    npc_entities = [n.entity for n in npcs]
    dynamic_obstacles = [car.entity] + npc_entities
    if args.collisions:
        tracked = npc_entities + [b["entity"] for b in buildings]
        car.set_collision_targets(tracked_entities=tracked)

    # Print runtime backend info once (helps answer CPU vs GPU questions quickly).
    runtime = sim.runtime_info(sample_contact_entity=car.entity)
    if runtime:
        parts = " ".join(f"{k}={runtime[k]}" for k in sorted(runtime.keys()) if runtime[k] is not None)
        print(f"[runtime] {parts}")

    # Benchmark run configuration.
    warmup_steps = int(args.bench_warmup) if args.bench else 0
    bench_steps = int(args.bench_steps) if args.bench else 0
    total_steps = warmup_steps + bench_steps if args.bench else int(args.steps)

    # Timing accumulators (bench window only; excludes warmup).
    t_policy = 0.0
    t_positions_fetch = 0.0
    t_npc_policy_compute = 0.0
    t_control = 0.0
    t_sim = 0.0
    t_collisions = 0.0
    t_render = 0.0
    t_total = 0.0
    n_collision_begin = 0
    n_collision_end = 0

    predicted_positions_by_id: dict[int, tuple[float, float, float]] | None = None
    if args.bench and bench_mode == "python_only":
        # Seed a simple kinematic position cache so the NPC policy doesn't treat itself as "stuck"
        # when we skip sim.step().
        predicted_positions_by_id = {id(ent): sim.get_position(ent) for ent in dynamic_obstacles}

    prof = None
    if args.bench and args.profile:
        import cProfile

        prof = cProfile.Profile()

    try:
        for step in range(total_steps):
            step_t0 = time.perf_counter()

            if prof is not None and step == warmup_steps:
                prof.enable()

            # Car demo control: accelerate then do a lazy right turn, then repeat.
            if bench_mode != "physics_only":
                phase = step % 240
                if phase < 120:
                    car.apply_action(DiscreteAction.ACCELERATE)
                elif phase < 180:
                    car.apply_action(DiscreteAction.TURN_RIGHT)
                else:
                    car.apply_action(DiscreteAction.DECELERATE)

            # Dynamic obstacle avoidance: car + other pedestrians.
            # Buildings are handled by A* routing on the nav grid.
            policy_t0 = time.perf_counter()
            positions_fetch_t0 = policy_t0
            if bench_mode == "full" or (not args.bench):
                positions_by_id = {id(ent): sim.get_position(ent) for ent in dynamic_obstacles}
                positions_fetch_t1 = time.perf_counter()
            elif bench_mode == "python_only":
                positions_by_id = predicted_positions_by_id or {}
                positions_fetch_t1 = positions_fetch_t0
            else:
                positions_by_id = {}
                positions_fetch_t1 = positions_fetch_t0

            npc_policy_t0 = positions_fetch_t1
            if bench_mode != "physics_only":
                for npc in npcs:
                    a = npc.policy_step(obstacles=dynamic_obstacles, positions_by_id=positions_by_id)
                    npc.apply_action(a)
            npc_policy_t1 = time.perf_counter()
            policy_t1 = npc_policy_t1

            # Apply controls
            control_t0 = policy_t1
            if bench_mode != "physics_only":
                car.step_control(dt)
                for npc in npcs:
                    npc.step_control(dt)
            control_t1 = time.perf_counter()

            sim_t0 = control_t1
            if bench_mode != "python_only":
                sim.step()
            sim_t1 = time.perf_counter()

            collisions_t0 = sim_t1
            if args.collisions and bench_mode == "full":
                evs = car.poll_collision_events(step_idx=step, min_force=float(args.collision_min_force))
                if args.bench and step >= warmup_steps:
                    for e in evs:
                        if e.phase.value == "begin":
                            n_collision_begin += 1
                        elif e.phase.value == "end":
                            n_collision_end += 1
            collisions_t1 = time.perf_counter()

            # Capture a rendered frame (if enabled)
            render_t0 = collisions_t1
            if gif_writer is not None and cam is not None and (step % max(1, args.gif_every) == 0):
                rgb, _, _, _ = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
                gif_writer.append_data(rgb)
            render_t1 = time.perf_counter()

            # In python_only mode we skip sim.step(), so update a simple kinematic position cache
            # so NPC policy remains representative (no artificial "stuck" replans).
            if args.bench and bench_mode == "python_only" and predicted_positions_by_id is not None:
                dtf = float(dt)

                def integrate_actor(ent: object, yaw: float, speed: float) -> tuple[float, float, float]:
                    p = predicted_positions_by_id.get(id(ent))
                    if p is None:
                        return (0.0, 0.0, 0.0)
                    x, y, z = float(p[0]), float(p[1]), float(p[2])
                    x += math.cos(float(yaw)) * float(speed) * dtf
                    y += math.sin(float(yaw)) * float(speed) * dtf
                    return (x, y, z)

                if control_mode == ControlMode.KINEMATIC:
                    predicted_positions_by_id[id(car.entity)] = integrate_actor(car.entity, car._yaw, car._target_speed)  # type: ignore[attr-defined]
                    for npc in npcs:
                        predicted_positions_by_id[id(npc.entity)] = integrate_actor(  # type: ignore[attr-defined]
                            npc.entity, npc._yaw, npc._target_speed
                        )

            if (not args.bench) and (step % 120 == 0):
                c = car.state()
                print(
                    f"[step {step:04d}] car pos=({c.position[0]:+.2f},{c.position[1]:+.2f}) "
                    f"yaw={c.yaw:+.2f} v={c.linear_speed:+.2f}"
                )

            step_t1 = render_t1
            if args.bench and step >= warmup_steps:
                t_policy += (policy_t1 - policy_t0)
                t_positions_fetch += (positions_fetch_t1 - positions_fetch_t0)
                t_npc_policy_compute += (npc_policy_t1 - npc_policy_t0)
                t_control += (control_t1 - control_t0)
                t_sim += (sim_t1 - sim_t0)
                t_collisions += (collisions_t1 - collisions_t0)
                t_render += (render_t1 - render_t0)
                t_total += (step_t1 - step_t0)
    finally:
        if prof is not None:
            try:
                prof.disable()
                import io
                import pstats

                s = io.StringIO()
                pstats.Stats(prof, stream=s).sort_stats("cumtime").print_stats(int(args.profile_top))
                print(f"[profile] top={int(args.profile_top)} sort=cumtime\n{s.getvalue()}")
            except Exception as e:
                print(f"[profile] failed: {e!r}")

        if gif_writer is not None:
            gif_writer.close()
            if gif_path is not None:
                print(f"Wrote GIF: {gif_path}")

    if args.bench:
        steps = max(1, bench_steps)
        ms_per_step = (t_total / steps) * 1000.0
        sps = steps / max(1e-12, t_total)
        print(
            f"[bench] steps={steps} warmup={warmup_steps} total_time={t_total:.6f}s  "
            f"ms/step={ms_per_step:.3f}  steps/s={sps:.2f}"
        )
        if args.bench_breakdown:
            def pct(x: float) -> float:
                return (x / max(1e-12, t_total)) * 100.0

            print(
                "[bench] breakdown:"
                f" policy={t_policy*1000.0:.3f}ms ({pct(t_policy):.1f}%)"
                f" pos_fetch={t_positions_fetch*1000.0:.3f}ms ({pct(t_positions_fetch):.1f}%)"
                f" npc_policy={t_npc_policy_compute*1000.0:.3f}ms ({pct(t_npc_policy_compute):.1f}%)"
                f" control={t_control*1000.0:.3f}ms ({pct(t_control):.1f}%)"
                f" sim={t_sim*1000.0:.3f}ms ({pct(t_sim):.1f}%)"
                f" collisions={t_collisions*1000.0:.3f}ms ({pct(t_collisions):.1f}%)"
                f" render={t_render*1000.0:.3f}ms ({pct(t_render):.1f}%)"
            )
        if args.collisions:
            print(f"[bench] collisions: begin={n_collision_begin} end={n_collision_end}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


