# Kiln

A minimal Dear ImGui desktop application using GLFW + OpenGL3 backend.

## Requirements

- CMake 3.20+
- C++17 compiler (GCC, Clang, MSVC)
- OpenGL 3.3+ capable GPU
- Linux: `libgl1-mesa-dev`, `libxrandr-dev`, `libxinerama-dev`, `libxcursor-dev`, `libxi-dev`

### Install dependencies (Linux)

```bash
sudo apt install build-essential cmake libgl1-mesa-dev libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev
```

## Build

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

## Run

```bash
./build/kiln
```

## Project Structure

```
src/
├── main.cpp    # Application entry point
└── config.h    # App name and window settings
```

## IDE Support

A `.clangd` file is included that points to `build/compile_commands.json` for proper IntelliSense. Run `cmake -B build` first to generate it.

## Features

- Dear ImGui v1.91.6
- GLFW 3.4 for window/input handling
- OpenGL 3.3 rendering
