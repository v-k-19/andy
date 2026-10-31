#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-desktop.txt
.venv/bin/python download_voice_model.py
.venv/bin/python - <<'PY'
import os
from pathlib import Path
root = Path.cwd()
applications = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'applications'
applications.mkdir(parents=True, exist_ok=True)
def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
content = '\n'.join([
    '[Desktop Entry]', 'Type=Application', 'Name=Andy',
    'Comment=Local voice assistant with Ollama and the Andy wake word',
    'Exec=' + quote(root / '.venv/bin/python') + ' ' + quote(root / 'desktop.py'),
    'Terminal=false', 'Icon=audio-input-microphone', 'Categories=Utility;', '',
])
(applications / 'andy.desktop').write_text(content)
print('Andy is installed. Open Andy from your application menu, or run .venv/bin/python desktop.py')
PY
