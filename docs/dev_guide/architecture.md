## Architecture

This page describes the major subsystems:

- UI (`kiln/ui/*`)
- Env bundles (`kiln/envio/*`)
- Genesis backend (`kiln/sim/genesis/*`)
- Actors (`kiln/actors/*`)

### High-level flow

```mermaid
flowchart LR
  UI[KilnUI] --> USD[USD_File]
  USD --> Export[EnvBundleExport]
  Export --> Bundle[BundleDir]
  Bundle --> Loader[GenesisSim_load_env_bundle]
  Loader --> Scene[GenesisScene]
  Scene --> Actors[Actors_Car_NPC]
```

### Design principles

- **Optional dependencies**: Genesis and USD are optional extras (`.[sim]`, `.[usd]`).
- **Version tolerance**: Genesis APIs change; the adapter uses permissive introspection.
- **Stable bundles**: USD carries geometry, `env.json` carries semantics.


