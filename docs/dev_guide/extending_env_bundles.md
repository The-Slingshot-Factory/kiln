## Extending env bundles

This page documents how to evolve the env-bundle schema and keep backward compatibility.

### Guidelines

- **Bump `schema_version`** when changing semantics in a non-backward-compatible way.
- Prefer **additive changes** (new optional fields with safe defaults).
- Keep JSON **human-editable** and stable for diffs (indentation, sorted keys where possible).

### Recommended process

1. Add a new schema type in `kiln/envio/bundle.py` (e.g., `EnvBundleV2`).
2. Update `load_env_bundle(...)` to parse and validate the new schema version.
3. Update `save_env_bundle(...)` (and exporters) to write the correct version.
4. Update the Genesis loader mapping in `kiln/sim/genesis/sim.py`.
5. Add/adjust an example bundle under `examples/env_bundles/`.
6. Update docs to describe the new fields and migration notes.


