## Env bundles (USD + env.json)

An **env bundle** is a small directory that contains:

- a USD file for geometry (`scene.usda/.usd/.usdc/.usdz`)
- an `env.json` sidecar for simulation semantics (world import options, primitives, spawn points)

Env bundles enable the “author once in the GUI, load later as a Gym env” workflow:

- The GUI (or any DCC tool) authors geometry in USD.
- Kiln exports a bundle directory containing the USD + a semantic `env.json`.
- Runtime code loads the bundle and constructs a simulator scene from it.

### Bundle layout

```
my_env.kiln_env/
├── scene.usda   # geometry (copied from your USD file)
└── env.json     # semantics (world import options, primitives, spawn points)
```

### `env.json` schema (v1)

The v1 schema is defined in `kiln/envio/bundle.py` as `EnvBundleV1`.

#### Top-level

- `schema_version` (int): must be `1`
- `scene_file` (str): relative path to the USD file within the bundle
- `world` (object): how to import the USD file as a single world entity
- `primitives` (list): additional primitive entities defined in JSON
- `spawn_points` (object): named poses used by higher-level env code for resets/spawns

#### `Pose`

Poses are stored as:

- `pos`: `[x, y, z]`
- `quat`: `[w, x, y, z]` (quaternion, Genesis convention)

#### `world`

`world` controls importing the USD file as one entity:

- `enabled` (bool): if false, USD is not imported
- `pose` (Pose): transform applied to the imported world mesh
- `fixed` (bool): world is typically static (true)
- `collision` (bool): enable collisions on the world mesh
- `visualization` (bool): enable rendering/visualization
- `scale` (float): uniform scale applied to the imported world mesh

#### `primitives[]`

Each primitive has:

- `id` (str): unique identifier (must not collide with other ids; `world` is reserved)
- `shape` (str): one of `plane`, `box`, `sphere`, `cylinder`
- `pose` (Pose)
- `fixed` (bool, optional)
- `mass` (float, optional)
- `collision` (bool, optional; default true)
- `visualization` (bool, optional; default true)
- `color` (RGB or RGBA list, optional)

Shape-specific fields:

- `box`: `size: [sx, sy, sz]`
- `sphere`: `radius: r`
- `cylinder`: `radius: r`, `height: h`
- `plane`: optional `normal: [nx, ny, nz]` (defaults to `[0, 0, 1]`)

Defaulting rules (when loading JSON):

- If `fixed` is explicitly set, it is respected.
- Else if `mass` is provided and `mass > 0`, the primitive is treated as dynamic.
- Else default to `fixed = true` (safer for v1).

#### `spawn_points`

`spawn_points` is a mapping:

```json
{
  "default": { "pos": [0, 0, 0.5], "quat": [1, 0, 0, 0] }
}
```

If `spawn_points` is missing or empty, Kiln inserts a default spawn point.

### Loading a bundle at runtime

Use `GenesisSim.load_env_bundle(...)`:

```bash
python examples/genesis_bundle_demo.py --bundle examples/env_bundles/basic_v1 --gs-backend cpu
```

Internally, the loader:

- imports the USD world as `gs.morphs.Mesh(...)` (when `world.enabled`)
- spawns the JSON `primitives` using `GenesisSim.add_box/add_sphere/add_cylinder/add_ground_plane`
- returns `(entities_by_id, spawn_points)`



