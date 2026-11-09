"""Verify the device picker is reachable without hunting through submenus."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest


class DeviceMenuTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Optional Qt dependency is not installed')
    def test_direct_launch_and_top_level_menu(self):
        script = textwrap.dedent('''
            import sys
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QTimer, QPoint
            from PySide6.QtGui import QContextMenuEvent
            from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QMenu
            import desktop
            failures = []
            original = QApplication.exec
            def root_window():
                return next(w for w in QApplication.topLevelWidgets() if w.windowTitle() == 'Andy — Personal AI')
            def fail(exc):
                failures.append(exc)
                for w in QApplication.topLevelWidgets():
                    if isinstance(w, QDialog): w.reject()
                root_window().close()
            def inspect_menu():
                try:
                    menu = next(w for w in QApplication.topLevelWidgets() if isinstance(w,QMenu) and w.isVisible())
                    assert menu.actions()[0].text() == 'Camera and microphone…'
                    assert root_window().device_action.shortcut().toString() == 'Ctrl+,'
                    menu.close()
                    root_window().close()
                except BaseException as exc: fail(exc)
            def open_menu():
                QTimer.singleShot(50, inspect_menu)
                event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(100,100), QPoint(100,100))
                root_window().contextMenuEvent(event)
            def inspect_picker():
                try:
                    dialog = next(w for w in QApplication.topLevelWidgets() if w.windowTitle() == 'Andy — Camera and microphone' and w.isVisible())
                    combos = dialog.findChildren(QComboBox)
                    assert len(combos) == 2
                    assert any('Pixy' in combos[0].itemText(i) for i in range(combos[0].count()))
                    assert any('Pixy' in combos[1].itemText(i) for i in range(combos[1].count()))
                    assert root_window().worker is None
                    dialog.reject()
                    QTimer.singleShot(50, open_menu)
                except BaseException as exc: fail(exc)
            def run(self):
                QTimer.singleShot(50, inspect_picker)
                QTimer.singleShot(3000, lambda: fail(AssertionError('UI check timed out')))
                return original()
            sounddevice = Mock()
            sounddevice.query_devices.return_value = [{'name':'Pixy microphone','max_input_channels':1}]
            sys.argv = ['desktop.py','--devices']
            with patch.dict('sys.modules', {'sounddevice':sounddevice}), patch.object(desktop,'camera_devices',return_value=[('/dev/video0','Pixy camera')]), patch.object(QApplication,'exec',run):
                try: desktop.main()
                except SystemExit as exc: assert exc.code == 0
            if failures: raise failures[0]
            print('Device picker and main-menu access verified.')
        ''')
        with TemporaryDirectory() as data:
            env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_DATA_HOME=data)
            result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1],
                                    env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Device picker and main-menu access verified.', result.stdout)


if __name__ == '__main__':
    unittest.main()
