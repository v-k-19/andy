"""Persist device choices only. Camera permission is never stored."""
import json
import os
from pathlib import Path
import tempfile


class DevicePreferences:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.getenv('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'andy' / 'devices.json'
        self.state = {}
        try:
            if self.path.exists() and self.path.stat().st_size <= 4096:
                data = json.loads(self.path.read_text())
                if isinstance(data, dict):
                    self.state = {key: value for key, value in data.items()
                                  if key in ('microphone', 'camera') and isinstance(value, str) and len(value) <= 512}
        except (OSError, ValueError):
            pass

    def apply(self):
        for key, variable in [('microphone', 'ANDY_INPUT_DEVICE'), ('camera', 'ANDY_CAMERA_DEVICE')]:
            if self.state.get(key):
                os.environ.setdefault(variable, self.state[key])

    def save(self, microphone=None, camera=None):
        state = self.state.copy()
        for key, value in [('microphone', microphone), ('camera', camera)]:
            if value is not None:
                state[key] = str(value)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.devices-', suffix='.json')
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(state, output)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.state = state
