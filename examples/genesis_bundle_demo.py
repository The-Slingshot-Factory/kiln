from __future__ import annotations

import argparse
import time
from pathlib import Path

from kiln.sim.genesis import GenesisSim, GenesisSimConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Load a Kiln env bundle (USD + env.json) into Genesis and step it.")
    parser.add_argument(
        "--bundle",
        type=str,
        default="examples/env_bundles/basic_v1",
        help="Path to the env bundle directory (contains scene.usd(a) and env.json).",
    )
    parser.add_argument("--steps", type=int, default=600, help="Number of simulation steps to run.")
    parser.add_argument(
        "--gs-backend",
        choices=["cpu", "gpu", "cuda", "vulkan"],
        default="cpu",
        help="Genesis backend selector.",
    )
    args = parser.parse_args()

    bundle_dir = Path(args.bundle)
    sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=8, headless=True, backend=args.gs_backend))
    entities, spawn_points = sim.load_env_bundle(bundle_dir)
    print(f"[bundle] dir={bundle_dir} entities={list(entities.keys())} spawn_points={list(spawn_points.keys())}")
    print(f"[runtime] {sim.runtime_info()}")

    # Quick step loop for smoke testing.
    t0 = time.perf_counter()
    for _ in range(int(args.steps)):
        sim.step()
    dt = time.perf_counter() - t0
    sps = float(args.steps) / max(1e-9, dt)
    print(f"[run] steps={args.steps} wall_time={dt:.3f}s steps/s={sps:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


