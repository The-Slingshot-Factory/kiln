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

Run the UI:

```bash
python3 kiln.py
```

Run the Genesis smoke test:

```bash
python3 examples/genesis_demo.py
```

---

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

---

## 📄 License

MIT
