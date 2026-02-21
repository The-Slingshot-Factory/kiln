from __future__ import annotations

"""Runtime types for loaded env bundles."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias

from .bundle import EnvBundleV1, Pose

Entity: TypeAlias = Any


@dataclass(frozen=True)
class LoadedEnvBundle:
    """Runtime representation of a loaded env bundle."""

    bundle_dir: Path
    bundle: EnvBundleV1
    entities_by_id: dict[str, Entity]
    world_entity: Entity | None
    spawn_points: dict[str, Pose]
