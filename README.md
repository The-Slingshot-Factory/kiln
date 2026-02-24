# Kiln

**A studio for creating reinforcement learning environments with high-fidelity simulation.**

Kiln provides an intuitive interface to design, prototype, and iterate on RL environments.

---

## ⚡ Quick Start

### Option A: Conda env (recommended)

Create a dedicated environment with all UI + USD + Genesis dependencies:

```bash
conda env create -f environment.yml
conda activate kiln-dev
```

If you already have the env and want to update it (recommended when `environment.yml` changes):

```bash
conda env update -n kiln-dev -f environment.yml --prune
conda activate kiln-dev
```

Run the UI:

```bash
python3 kiln.py
```

Run the Genesis smoke test:

```bash
python3 examples/genesis_demo.py
```

---

## 🧩 Backend API (GUI integration)

For in-repo GUI work, prefer the stable import surface in `kiln.api`:

```python
from kiln.api import GenesisSim, GenesisSimConfig, load_env_bundle

sim = GenesisSim(GenesisSimConfig(dt=1 / 60, substeps=8, headless=True, backend="cpu"))
loaded = sim.load_env_bundle("examples/env_bundles/basic_v1")
print(loaded.entities_by_id.keys(), loaded.spawn_points.keys())
```

Activate the dev env first:

```bash
conda activate kiln-dev
```

---

## 📚 Docs (MkDocs)

Kiln includes a MkDocs site (with `mkdocstrings`) for user + developer docs and an API reference.

If you use the conda env from `environment.yml`, docs dependencies are already included.

Serve docs locally:

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```

Build docs (outputs to `site/`):

```bash
mkdocs build
```

---

## 📦 Env bundles (USD + `env.json`) for GUI → Gym workflows

Kiln’s intended pipeline is:

- Author geometry in **USD** (`.usda/.usd`) in the GUI
- Export a **bundle directory** next to the USD file
- Load that bundle at runtime to construct a Genesis-backed env (then `scene.reset()` per episode)

### Bundle layout (v1)

```
my_env.kiln_env/
├── scene.usda   # geometry (copied from your USD file)
└── env.json     # semantics (world import options, primitives, spawn points)
```

### Export from the UI
- Right click a `.usd/.usda` file in the project browser
- Select **“Export Kiln Env Bundle…”**
- Kiln creates `<stem>.kiln_env/` containing `scene.<ext>` and a template `env.json`

### Run the sample bundle (CPU)

```bash
python3 examples/genesis_bundle_demo.py --bundle examples/env_bundles/basic_v1 --gs-backend cpu
```

### Run the sample XML scene (CPU)

```bash
python3 examples/genesis_xml_demo.py --xml examples/env_bundles/basic_v1/env.xml --gs-backend cpu
```

### Notes
- **Versioning**: `env.json` contains `schema_version` (currently `1`). We’ll bump this when the schema evolves.
- **USD deps**: Loading the USD world requires `pxr` (install with `pip install -e \".[usd]\"` or use `environment.yml`).
- **Genesis deps**: Install Genesis via `pip install -e \".[sim]\"` (or use `environment.yml`).
### Option B: Pip (UI-only)

### 1. Install (UI)

You need Python 3, `PyQt6`, and `qdarkstyle`, plus OpenGL bindings:

```bash
python -m pip install PyQt6 qdarkstyle PyOpenGL PyOpenGL_accelerate
```

Or install from this repo (recommended):

```bash
python -m pip install -e .
```

### 2. Optional: USD support

Kiln can create and preview USD scenes (`.usda/.usd`). To enable USD features:

```bash
python -m pip install -e ".[usd]"
```

### 3. Optional: Genesis simulation backend

Kiln’s upcoming simulation layer uses the Genesis physics platform. Install PyTorch first (choose CPU/GPU as needed), then install the optional Genesis extra:

- Genesis docs: [Genesis documentation](https://genesis-world.readthedocs.io/en/latest/)

```bash
python -m pip install -e ".[sim]"
```

### 4. Run (UI)

```bash
python3 kiln.py
```

### 5. Smoke test (Genesis)

After installing the `sim` extra, you can run a simple headless demo:

```bash
python3 examples/genesis_demo.py
```

---

## 🎯 Features

- **Project-based workflow** — Organize your RL environments into projects
- **Modern UI** — Built with `PyQt6` and `qdarkstyle` for a professional, high-performance interface
- **Cross-platform** — Native hardware-accelerated rendering on Linux, Windows, and macOS
- **Robust Architecture** — Uses `QStackedWidget` for smooth screen transitions and `QFileSystemModel` for fast file exploration
- **3D Viewport** — Integrated OpenGL rendering for scene preview

---

## 🗂️ Project Structure

```
kiln/
├── kiln.py               # Main application entry point & controller
├── kiln/
│   ├── __init__.py
│   ├── config.py         # Configuration & recent projects manager
│   ├── constants.py      # Shared constants
│   └── ui/
│       ├── __init__.py
│       ├── viewport.py       # OpenGL rendering widget
│       ├── welcome_screen.py # landing screen (QWidget)
│       └── project_screen.py # workspace (QWidget)
```

### Screen Architecture

Kiln uses a modular system based on `PyQt6` widgets:

- `WelcomeScreen` — Initial landing screen for creating/opening projects
- `ProjectScreen` — Main project workspace with file explorer

---

## 🔧 Linux Troubleshooting

### 1. OpenGL Errors / Window Not Appearing
If you see errors like `libGL error: MESA-LOADER: failed to open...` or the window is transparent/black on Linux, it is likely due to a driver conflict or Wayland incompatibility.

**Common Fix for Conda/Miniconda Users:**
Conda environments often bundle an older version of `libstdc++` that conflicts with system OpenGL drivers. Pre-load your system's library:

```bash
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
python3 kiln.py
```

### 2. Wayland "Invisible Window"
If the application runs but the window is invisible on Wayland compositors (GNOME/KDE on Wayland), force the X11 backend:

```bash
export QT_QPA_PLATFORM=xcb
python3 kiln.py
```

### 3. Missing Drivers
If OpenGL is not initializing at all, ensure you have the Mesa drivers installed:

```bash
sudo apt-get install libgl1-mesa-dri libglx-mesa0 libegl1-mesa mesa-utils
```

### 4. WSL2 + Genesis CUDA backend (`gs.cuda`) fails with `CUDA_ERROR_NO_DEVICE`
On some WSL2 setups, Taichi/Genesis can accidentally load a *non-WSL* `libcuda.so` and fail at init with:

- `CUDA Error CUDA_ERROR_NO_DEVICE: no CUDA-capable device is detected while calling init (cuInit)`

Kiln works around this by ensuring `/usr/lib/wsl/lib` is preferred when you select `--gs-backend cuda`.

If you run into this outside of Kiln’s wrapper, the manual workaround is:

```bash
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH
python3 examples/genesis_demo.py --gs-backend cuda
```

---

## 📄 License

MIT
