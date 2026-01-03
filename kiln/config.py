from __future__ import annotations

"""App configuration and persistence helpers (e.g., recent projects list)."""

import os
from pathlib import Path
from .constants import MAX_RECENT_PROJECTS

class ConfigManager:
    """Manages user-level config files under XDG config dir (or fallbacks)."""

    def __init__(self) -> None:
        self.config_dir = self._get_config_dir()
        self.recent_projects_file = self.config_dir / "recent_projects.txt"
        self.recent_projects: list[Path] = []
        self._load_recent_projects()

    def _get_config_dir(self) -> Path:
        """Return a writable config directory path, creating it if needed."""
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            path = Path(xdg_config) / "kiln"
        else:
            path = Path.home() / ".config" / "kiln"
        
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                path = Path(".") / ".kiln"
                path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_recent_projects(self) -> None:
        """Load recent projects from disk into `self.recent_projects`."""
        self.recent_projects = []
        if self.recent_projects_file.exists():
            try:
                with open(self.recent_projects_file, "r", encoding="utf-8") as f:
                    for line in f:
                        path_str = line.strip()
                        if path_str:
                            path = Path(path_str)
                            if path.exists() and path.is_dir():
                                self.recent_projects.append(path)
            except Exception as e:
                print(f"Error loading recent projects: {e}")

    def save_recent_projects(self) -> None:
        """Persist the current recent project list to disk."""
        try:
            with open(self.recent_projects_file, "w", encoding="utf-8") as f:
                for project in self.recent_projects:
                    f.write(f"{project.absolute()}\n")
        except Exception as e:
            print(f"Error saving recent projects: {e}")

    def add_recent_project(self, path: Path) -> None:
        """Add a project to the MRU list (most-recent-first)."""
        path = path.resolve()
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > MAX_RECENT_PROJECTS:
            self.recent_projects = self.recent_projects[:MAX_RECENT_PROJECTS]
        self.save_recent_projects()

    def remove_recent_project(self, path: Path) -> None:
        """Remove a project from the MRU list."""
        path = path.resolve()
        if path in self.recent_projects:
            self.recent_projects.remove(path)
            self.save_recent_projects()
