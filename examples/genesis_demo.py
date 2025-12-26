from __future__ import annotations

import argparse
from pathlib import Path
import random

from kiln.actors import CarBlock, CarBlockConfig, ControlMode, DiscreteAction, NPCBlock, NPCBlockConfig
from kiln.sim.genesis import GenesisSim, GenesisSimConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiln + Genesis smoke test (headless).")
    parser.add_argument("--steps", type=int, default=600, help="Number of simulation steps to run.")
    parser.add_argument("--npcs", type=int, default=5, help="Number of NPC blocks.")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed.")
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
        default=(6.0, 6.0, 4.0),
        metavar=("X", "Y", "Z"),
        help="Camera position.",
    )
    parser.add_argument(
        "--camera-lookat",
        type=float,
        nargs=3,
        default=(0.0, 0.0, 0.2),
        metavar=("X", "Y", "Z"),
        help="Camera look-at target.",
    )
    parser.add_argument("--camera-fov", type=float, default=60.0, help="Camera field of view (degrees).")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    control_mode = ControlMode.KINEMATIC if args.control_mode == "kinematic" else ControlMode.FORCE_TORQUE

    sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=1, headless=True, seed=args.seed))
    sim.create_programmatic_scene()

    # Optional: capture rendered frames to a GIF.
    gif_writer = None
    cam = None
    gif_path: Path | None = None
    if args.gif is not None:
        import importlib

        # Lazy import; only needed for gif export.
        # Use dynamic import to avoid type-checker issues in environments without imageio installed.
        imageio = importlib.import_module("imageio.v2")

        gif_path = Path(args.gif)
        gif_path.parent.mkdir(parents=True, exist_ok=True)

        if sim.scene is None:
            raise RuntimeError("Genesis scene was not created.")
        cam = sim.scene.add_camera(
            res=(args.gif_res, args.gif_res),
            pos=tuple(args.camera_pos),
            lookat=tuple(args.camera_lookat),
            fov=args.camera_fov,
            GUI=False,
        )
        gif_writer = imageio.get_writer(str(gif_path), mode="I", duration=1.0 / float(args.gif_fps))

    # Colors (category-coded)
    car_color = (1.0, 0.2, 0.2)  # red
    npc_color = (0.2, 0.6, 1.0)  # blue
    obstacle_color = (0.75, 0.75, 0.75)  # light gray

    # Simple obstacles (static-ish blocks).
    obstacles = []
    for i in range(8):
        x = rng.uniform(-4.0, 4.0)
        y = rng.uniform(-4.0, 4.0)
        try:
            obstacles.append(
                sim.add_box(
                    name=f"obstacle_{i}",
                    size=(0.6, 0.6, 0.6),
                    position=(x, y, 0.3),
                    mass=0.0,
                    color=obstacle_color,
                )
            )
        except Exception:
            # Fallback if this Genesis version doesn't support static bodies via mass=0.
            obstacles.append(
                sim.add_box(
                    name=f"obstacle_{i}",
                    size=(0.6, 0.6, 0.6),
                    position=(x, y, 0.3),
                    mass=1.0,
                    color=obstacle_color,
                )
            )

    car = CarBlock(
        sim,
        name="car",
        position=(0.0, 0.0, 0.15),
        config=CarBlockConfig(control_mode=control_mode, color=car_color),
    )

    npcs: list[NPCBlock] = []
    for i in range(args.npcs):
        x = rng.uniform(-3.0, 3.0)
        y = rng.uniform(-3.0, 3.0)
        npc = NPCBlock(
            sim,
            name=f"npc_{i}",
            position=(x, y, 0.15),
            config=NPCBlockConfig(
                control_mode=control_mode,
                roam_xy_min=(-5.0, -5.0),
                roam_xy_max=(5.0, 5.0),
                cruise_speed=2.0,
                color=npc_color,
            ),
            rng=random.Random(args.seed + 1000 + i),
        )
        npc.pick_new_goal()
        npcs.append(npc)

    # Build once after all entities are added.
    sim.build()

    dt = sim.config.dt

    try:
        for step in range(args.steps):
            # Car demo control: accelerate then do a lazy right turn, then repeat.
            phase = step % 240
            if phase < 120:
                car.apply_action(DiscreteAction.ACCELERATE)
            elif phase < 180:
                car.apply_action(DiscreteAction.TURN_RIGHT)
            else:
                car.apply_action(DiscreteAction.DECELERATE)

            # NPC roaming
            world_obstacles = obstacles + [car.entity] + [n.entity for n in npcs]
            for npc in npcs:
                a = npc.policy_step(obstacles=world_obstacles)
                npc.apply_action(a)

            # Apply controls
            car.step_control(dt)
            for npc in npcs:
                npc.step_control(dt)

            sim.step()

            # Capture a rendered frame (if enabled)
            if gif_writer is not None and cam is not None and (step % max(1, args.gif_every) == 0):
                rgb, _, _, _ = cam.render(rgb=True, depth=False, segmentation=False, normal=False)
                gif_writer.append_data(rgb)

            if step % 120 == 0:
                c = car.state()
                print(
                    f"[step {step:04d}] car pos=({c.position[0]:+.2f},{c.position[1]:+.2f}) "
                    f"yaw={c.yaw:+.2f} v={c.linear_speed:+.2f}"
                )
    finally:
        if gif_writer is not None:
            gif_writer.close()
            if gif_path is not None:
                print(f"Wrote GIF: {gif_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


