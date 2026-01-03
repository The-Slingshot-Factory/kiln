## Examples

This page covers the example scripts in `examples/`, including:

- `examples/genesis_demo.py`
- `examples/genesis_bundle_demo.py`

### `examples/genesis_demo.py`

This is a general Genesis smoke test (programmatic scene construction).

Run on CPU:

```bash
python examples/genesis_demo.py --gs-backend cpu
```

### `examples/genesis_bundle_demo.py`

This loads an env bundle directory (USD + `env.json`) and steps the simulation headlessly.

Run the included sample bundle on CPU:

```bash
python examples/genesis_bundle_demo.py --bundle examples/env_bundles/basic_v1 --gs-backend cpu --steps 600
```

Expected output is console-only (no window). You should see:

- a `[bundle] ...` line listing entity ids and spawn point names
- a `[runtime] ...` dict with best-effort backend/device info
- a `[run] steps=... wall_time=... steps/s=...` timing summary



