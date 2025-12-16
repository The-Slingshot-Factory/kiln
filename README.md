# Kiln

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
    libstdc++-dev \
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
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
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
- **Modular screen architecture** — Clean separation of UI concerns for scalable development

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
│   ├── main.cpp              # Application entry point & main loop
│   ├── core/
│   │   └── config.h          # Window settings and app configuration
│   ├── renderer/             # Rendering + camera
│   ├── scene/                # Scene data + primitive tools
│   └── ui/
│       ├── dialogs/          # UI dialogs (new scene/folder, etc.)
│       └── screens/          # Modular screen system
│           ├── screen.h          # Base screen interface
│           ├── welcome_screen.h  # Welcome screen header
│           ├── welcome_screen.cpp# Welcome screen implementation
│           ├── project_screen.h  # Project screen header
│           └── project_screen.cpp# Project screen implementation
├── CMakeLists.txt            # Build configuration (auto-fetches dependencies)
└── build/                    # Generated build artifacts
    ├── kiln                  # Executable
    └── fonts/                # Bundled Inter font
```

### Screen Architecture

Kiln uses a **modular screen system** where each screen is a self-contained class:

```cpp
class Screen
{
public:
    virtual void onEnter() {}   // Called when screen becomes active
    virtual void onExit() {}    // Called when screen is deactivated
    virtual void update() = 0;  // Draw and handle UI each frame
};
```

**Current screens:**
- `WelcomeScreen` — Initial landing screen for creating/opening projects
- `ProjectScreen` — Main project workspace with menu bar

**Adding a new screen:**
1. Create `my_screen.h` and `my_screen.cpp` in `src/ui/screens/`
2. Inherit from `Screen` and implement `update()`
3. Use `switchTo<MyScreen>(args...)` to transition between screens
4. Add the `.cpp` file to `CMakeLists.txt`

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
- [GLM 1.0.1](https://github.com/g-truc/glm) — OpenGL math (vectors/matrices)
- [Inter Font](https://rsms.me/inter/) — Modern, readable UI typography

---

## 📄 License

MIT
