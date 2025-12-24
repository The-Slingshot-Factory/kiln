from __future__ import annotations

import argparse
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
    args = parser.parse_args()

    rng = random.Random(args.seed)

    control_mode = ControlMode.KINEMATIC if args.control_mode == "kinematic" else ControlMode.FORCE_TORQUE

    sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=1, headless=True, seed=args.seed))
    sim.create_programmatic_scene()

    # Simple obstacles (static-ish blocks).
    obstacles = []
    for i in range(8):
        x = rng.uniform(-4.0, 4.0)
        y = rng.uniform(-4.0, 4.0)
        try:
            obstacles.append(
                sim.add_box(name=f"obstacle_{i}", size=(0.6, 0.6, 0.6), position=(x, y, 0.3), mass=0.0)
            )
        except Exception:
            # Fallback if this Genesis version doesn't support static bodies via mass=0.
            obstacles.append(
                sim.add_box(name=f"obstacle_{i}", size=(0.6, 0.6, 0.6), position=(x, y, 0.3), mass=1.0)
            )

    car = CarBlock(
        sim,
        name="car",
        position=(0.0, 0.0, 0.15),
        config=CarBlockConfig(control_mode=control_mode),
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
            ),
            rng=random.Random(args.seed + 1000 + i),
        )
        npc.pick_new_goal()
        npcs.append(npc)

    # Build once after all entities are added.
    sim.build()

    dt = sim.config.dt

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

        if step % 120 == 0:
            c = car.state()
            print(
                f"[step {step:04d}] car pos=({c.position[0]:+.2f},{c.position[1]:+.2f}) "
                f"yaw={c.yaw:+.2f} v={c.linear_speed:+.2f}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


