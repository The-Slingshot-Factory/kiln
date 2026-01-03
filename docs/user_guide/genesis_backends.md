## Genesis backends

Kiln’s Genesis adapter supports selecting a backend via `GenesisSimConfig(backend=...)`.

This page documents:

- CPU vs GPU/CUDA backends
- common performance pitfalls (data transfer)
- WSL2 CUDA quirks and the `LD_LIBRARY_PATH` shim behavior

### Backend selection

Most entrypoints accept a string backend selector:

- `cpu`
- `gpu` / `cuda` (platform-dependent; Genesis/Taichi decides what’s available)
- `vulkan` (if supported by your Genesis build)

Example (headless):

```bash
python examples/genesis_bundle_demo.py --bundle examples/env_bundles/basic_v1 --gs-backend cpu
```

### Troubleshooting: WSL2 + CUDA

On some WSL2 setups, Taichi/Genesis may accidentally load a non-WSL `libcuda.so` and fail at init with:

- `CUDA_ERROR_NO_DEVICE: no CUDA-capable device is detected while calling init (cuInit)`

Kiln works around this when you select a CUDA-ish backend:

- It prepends `/usr/lib/wsl/lib` to `LD_LIBRARY_PATH`
- It may **re-exec the process once** so the dynamic loader sees the path at process start

### Performance notes

For small scenes, GPU backends can be slower due to overheads:

- kernel launch overhead
- CPU↔GPU synchronization when extracting Python floats

Kiln’s adapter uses a small helper to avoid per-element sync when reading tensors:

- see `_to_cpu_once(...)` in `kiln/sim/genesis/sim.py`


