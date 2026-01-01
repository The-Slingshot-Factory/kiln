from __future__ import annotations

import shutil
from pathlib import Path

from .bundle import EnvBundleError, EnvBundleV1, save_env_bundle


USD_EXTS = {".usd", ".usda", ".usdc", ".usdz"}


def export_bundle_from_usd(
    source_usd_path: str | Path,
    bundle_dir: str | Path,
    *,
    env_filename: str = "env.json",
    scene_filename: str | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Create an env bundle directory from a USD file.

    This is intended for GUI use (author in USD, export bundle for Gym/env runtime).
    """
    src = Path(source_usd_path)
    if not src.exists():
        raise EnvBundleError(f"USD file does not exist: {src}")
    if src.suffix.lower() not in USD_EXTS:
        raise EnvBundleError(f"Unsupported USD extension {src.suffix!r}. Expected one of {sorted(USD_EXTS)}.")

    out_dir = Path(bundle_dir)
    if out_dir.exists():
        if not overwrite:
            raise EnvBundleError(f"Bundle dir already exists: {out_dir}")
        if not out_dir.is_dir():
            raise EnvBundleError(f"Bundle path exists but is not a directory: {out_dir}")
        # overwrite=True: clear dir contents
        for p in out_dir.iterdir():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    dst_scene_name = scene_filename or f"scene{src.suffix.lower()}"
    if Path(dst_scene_name).is_absolute():
        raise EnvBundleError(f"scene_filename must be relative, got {dst_scene_name!r}")
    dst_scene = out_dir / dst_scene_name
    shutil.copy2(src, dst_scene)

    bundle = EnvBundleV1(scene_file=dst_scene_name)
    save_env_bundle(out_dir, bundle, env_filename=env_filename)
    return out_dir


