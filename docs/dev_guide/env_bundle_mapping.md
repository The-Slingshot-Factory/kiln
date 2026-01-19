## Env bundle → Genesis entity mapping

This page documents how `env.json` fields map into Genesis entities created by `GenesisSim.load_env_bundle()`.

### World mesh

When `world.enabled` is true, Kiln imports the referenced USD file as a single mesh entity:

- Genesis morph: `gs.morphs.Mesh(file=..., pos=..., quat=..., fixed=..., collision=..., visualization=..., scale=...)`
- Stored in the returned entity mapping under the reserved key: `world`

### Primitives

Each entry in `primitives[]` becomes one Genesis entity, keyed by `id`.

Shape mapping:

- `plane` → `GenesisSim.add_ground_plane(...)`
- `box` → `GenesisSim.add_box(...)`
- `sphere` → `GenesisSim.add_sphere(...)`
- `cylinder` → `GenesisSim.add_cylinder(...)`

Physics mapping (v1):

- If a primitive is fixed, the loader forces `mass=0.0` when calling the helper.
- Otherwise:
  - `mass=None` means “dynamic with Genesis default material”
  - `mass>0` means “dynamic; density is computed from mass/volume”

Visual mapping (v1):

- `color` is passed through to a Genesis `surface` when supported.

### Spawn points

`spawn_points` are not instantiated as entities. They are returned on the typed result:

```python
loaded = sim.load_env_bundle(bundle_dir)
spawn_points = loaded.spawn_points
```

Each spawn point is a `Pose` with `pos` and `quat`.


