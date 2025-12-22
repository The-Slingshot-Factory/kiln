import os
from pathlib import Path
from .constants import MAX_RECENT_PROJECTS

class ConfigManager:
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.recent_projects_file = self.config_dir / "recent_projects.txt"
        self.recent_projects = []
        self._load_recent_projects()

    def _get_config_dir(self):
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
                path.mkdir(exist_ok=True)
        return path

    def _load_recent_projects(self):
        self.recent_projects = []
        if self.recent_projects_file.exists():
            try:
                with open(self.recent_projects_file, 'r') as f:
                    for line in f:
                        path_str = line.strip()
                        if path_str:
                            path = Path(path_str)
                            if path.exists() and path.is_dir():
                                self.recent_projects.append(path)
            except Exception as e:
                print(f"Error loading recent projects: {e}")

    def save_recent_projects(self):
        try:
            with open(self.recent_projects_file, 'w') as f:
                for project in self.recent_projects:
                    f.write(f"{project.absolute()}\n")
        except Exception as e:
            print(f"Error saving recent projects: {e}")

    def add_recent_project(self, path):
        path = path.resolve()
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        if len(self.recent_projects) > MAX_RECENT_PROJECTS:
            self.recent_projects = self.recent_projects[:MAX_RECENT_PROJECTS]
        self.save_recent_projects()

    def remove_recent_project(self, path):
        path = path.resolve()
        if path in self.recent_projects:
            self.recent_projects.remove(path)
            self.save_recent_projects()
