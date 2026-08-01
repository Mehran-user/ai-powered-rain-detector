import os

import yaml


class Config:
    def __init__(self, data, base_dir):
        self._data = data
        self.base_dir = base_dir
        self.schedule = data["schedule"]
        self.ai = data["ai"]
        self.camera = data["camera"]
        self.image = data["image"]
        self.sound = data["sound"]
        self.paths = data["paths"]

    def path(self, key):
        return os.path.join(self.base_dir, self.paths[key])

    @classmethod
    def load(cls, path, start_at=None, stop_at=None):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if start_at:
            data["schedule"]["start_at"] = start_at
        if stop_at:
            data["schedule"]["stop_at"] = stop_at
        base_dir = os.path.dirname(os.path.abspath(path))
        return cls(data, base_dir)
