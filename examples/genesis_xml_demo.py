from __future__ import annotations

import argparse
import time
from pathlib import Path

from kiln.sim.genesis import GenesisSim, GenesisSimConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Load a Kiln MuJoCo-style XML scene into Genesis and step it.")
    parser.add_argument(
        "--xml",
        type=str,
        default="examples/env_bundles/basic_v1/env.xml",
        help="Path to the XML scene file.",
    )
    parser.add_argument("--steps", type=int, default=600, help="Number of simulation steps to run.")
    parser.add_argument(
        "--gs-backend",
        choices=["cpu", "gpu", "cuda", "vulkan"],
        default="cpu",
        help="Genesis backend selector.",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml)
    sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=8, headless=True, backend=args.gs_backend))
    loaded = sim.load_env_xml_bundle(xml_path)
    print(
        f"[xml] path={xml_path} entities={list(loaded.entities_by_id.keys())} "
        f"spawn_points={list(loaded.spawn_points.keys())}"
    )
    print(f"[runtime] {sim.runtime_info()}")

    t0 = time.perf_counter()
    for _ in range(int(args.steps)):
        sim.step()
    dt = time.perf_counter() - t0
    sps = float(args.steps) / max(1e-9, dt)
    print(f"[run] steps={args.steps} wall_time={dt:.3f}s steps/s={sps:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

