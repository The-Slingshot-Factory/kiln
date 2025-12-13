# 🔥 Kiln

**A studio for creating reinforcement learning environments with high-fidelity simulation.**

Kiln provides an intuitive interface to design, prototype, and iterate on RL environments—all backed by performant OpenGL rendering for real-time visualization.

---

## ⚡ Quick Start

### 1. Install Dependencies

<details>
<summary><b>Ubuntu / Debian</b></summary>

```bash
sudo apt update && sudo apt install -y \
    build-essential \
    cmake \
    libgl1-mesa-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev
```
</details>

<details>
<summary><b>Fedora</b></summary>

```bash
sudo dnf install -y gcc-c++ cmake mesa-libGL-devel libXrandr-devel libXinerama-devel libXcursor-devel libXi-devel
```
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -S base-devel cmake mesa libxrandr libxinerama libxcursor libxi
```
</details>

### 2. Build

```bash
git clone https://github.com/your-username/kiln.git
cd kiln
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

### 3. Run

```bash
./build/kiln
```

---

## 🎯 Features

- **Project-based workflow** — Organize your RL environments into projects
- **Real-time visualization** — OpenGL 3.3 rendering for smooth, high-fidelity simulation previews
- **Cross-platform** — Runs on Linux (Windows/macOS support planned)
- **Native look & feel** — Built with Dear ImGui for responsive, GPU-accelerated UI

---

## 📋 Requirements

| Component | Minimum Version |
|-----------|-----------------|
| CMake     | 3.20+           |
| C++ Compiler | C++17 (GCC 8+, Clang 7+) |
| OpenGL    | 3.3+            |

---

## 🗂️ Project Structure

```
kiln/
├── src/
│   ├── main.cpp      # Application entry point & UI
│   └── config.h      # Window settings and app configuration
├── CMakeLists.txt    # Build configuration (auto-fetches dependencies)
└── build/            # Generated build artifacts
    ├── kiln          # Executable
    └── fonts/        # Bundled Inter font
```

---

## 🔧 Development

### IDE Setup

For IntelliSense/autocomplete, configure your editor to use the generated `compile_commands.json`:

```bash
# Generate compile commands
cmake -B build

# For VS Code: .vscode/settings.json
{ "clangd.arguments": ["--compile-commands-dir=build"] }

# For Neovim/other LSP clients: symlink or set in .clangd
```

### Build Types

```bash
# Debug build (with symbols, no optimization)
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# Release build (optimized)
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

---

## 📦 Dependencies (auto-fetched)

These are automatically downloaded during the CMake configure step:

- [GLFW 3.4](https://github.com/glfw/glfw) — Window & input handling
- [Dear ImGui v1.91.6](https://github.com/ocornut/imgui) — Immediate-mode GUI
- [tinyfiledialogs](https://github.com/native-toolkit/tinyfiledialogs) — Native file dialogs
- [Inter Font](https://rsms.me/inter/) — Modern, readable UI typography

---

## 📄 License

MIT
