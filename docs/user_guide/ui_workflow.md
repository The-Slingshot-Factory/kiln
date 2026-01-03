## UI workflow

This page documents:

- Projects and the project browser
- USD preview in the viewport
- Exporting a `.kiln_env` bundle from a USD file

### Open the UI

```bash
python kiln.py
```

### Create or open a project

- **New Project**: choose a name and directory; Kiln creates a folder and opens it.
- **Open Project**: choose an existing folder; Kiln opens it as the project root.
- **Recent**: quick-open recently used projects.

### Create a new USD scene (optional)

With a project open:

- Use **Project → New Scene**
- Enter a scene name (Kiln will create a `.usda` file)

This requires USD Python bindings (`pxr`). Install with `python -m pip install -e ".[usd]"` or use the conda env.

### Preview a USD file

- Select a `.usd/.usda` file in the project browser.
- The viewport attempts to load the USD stage and render meshes.

Current preview behavior is intentionally simple:

- Meshes are rendered as a point cloud.
- Materials/textures are not interpreted yet.

### Export an env bundle

Right-click a `.usd/.usda/.usdc/.usdz` file and select **Export Kiln Env Bundle…**.

Kiln creates a sibling directory:

```
<scene_stem>.kiln_env/
├── scene.<ext>
└── env.json
```

You can then edit `env.json` to add primitives and spawn points.



