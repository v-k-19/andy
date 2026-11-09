from contextlib import closing
import io
import json
from pathlib import Path
import queue
from tempfile import TemporaryDirectory
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import camera_input
import desktop


class CameraTests(unittest.TestCase):
    def test_visual_intent_does_not_hijack_ordinary_questions(self):
        for question in ['What do you see?', 'Look at this and describe it', 'What am I holding?', 'Please use the camera to read this']:
            self.assertTrue(camera_input.is_visual_request(question))
        for question in ['What time is it?', 'Explain how cameras work', 'Open Firefox', 'Search the web for cameras']:
            self.assertFalse(camera_input.is_visual_request(question))

    def test_enumeration_reads_names_without_opening_hardware(self):
        with TemporaryDirectory() as directory, patch.dict('sys.modules', {'cv2': Mock()}) as modules:
            path = Path(directory) / 'video2'
            path.mkdir(); (path / 'name').write_text('Pixy USB Camera\n')
            self.assertEqual(camera_input.camera_devices(Path(directory)), [('/dev/video2', 'Pixy USB Camera')])
            modules['cv2'].VideoCapture.assert_not_called()

    def test_no_open_without_current_consent(self):
        access=camera_input.CameraAccess()
        pending=camera_input.CameraPermission('What do you see?', '/dev/video0', threading.Event())
        with patch.dict('sys.modules', {'cv2':Mock()}) as modules:
            with self.assertRaisesRegex(RuntimeError,'permission'):
                access.snapshot(pending)
            modules['cv2'].VideoCapture.assert_not_called()

    def test_denied_consent_never_captures_or_contacts_model(self):
        access=camera_input.CameraAccess()
        result=[]
        with patch.object(access,'snapshot') as capture, patch.object(camera_input,'build_opener') as model:
            thread=threading.Thread(target=lambda:result.append(access.answer('What do you see?')))
            thread.start()
            request=access.requests.get(timeout=2)
            capture.assert_not_called()
            request.decide(False)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            capture.assert_not_called(); model.assert_not_called()
        self.assertIn('denied',result[0])

    def test_approval_is_one_use_and_camera_released_before_model_call(self):
        access=camera_input.CameraAccess()
        cv=Mock()
        cv.CAP_V4L2=200;cv.CAP_PROP_FRAME_WIDTH=3;cv.CAP_PROP_FRAME_HEIGHT=4;cv.IMWRITE_JPEG_QUALITY=1
        cv.VideoCapture.return_value.isOpened.return_value=True
        cv.VideoCapture.return_value.read.return_value=(True,SimpleNamespace(shape=(720,1280,3)))
        cv.imencode.return_value=(True,SimpleNamespace(tobytes=lambda:b'jpeg'))
        response=closing(io.BytesIO(b'{"message":{"content":"A blue mug."}}'))
        result=[]
        def open_model(*args,**kwargs):
            cv.VideoCapture.return_value.release.assert_called_once()
            payload=json.loads(args[0].data)
            self.assertEqual(payload['messages'][-1]['images'],['anBlZw=='])
            return response
        with patch.dict('sys.modules',{'cv2':cv}), patch.object(camera_input,'build_opener') as model:
            model.return_value.open.side_effect=open_model
            thread=threading.Thread(target=lambda:result.append(access.answer('What am I holding?')))
            thread.start()
            request=access.requests.get(timeout=2)
            cv.VideoCapture.assert_not_called()
            request.decide(True)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            with self.assertRaisesRegex(RuntimeError,'permission'):access.snapshot(request)
        self.assertEqual(result,['A blue mug.'])
        cv.VideoCapture.assert_called_once()

    def test_camera_is_released_when_frame_capture_fails(self):
        access=camera_input.CameraAccess()
        request=camera_input.CameraPermission('Look at this','/dev/video0',threading.Event())
        request.decide(True)
        cv=Mock();cv.VideoCapture.return_value.read.return_value=(False,None)
        with patch.dict('sys.modules',{'cv2':cv}):
            with self.assertRaisesRegex(RuntimeError,'provide a picture'):access.snapshot(request)
        cv.VideoCapture.return_value.release.assert_called_once()

    def test_expired_or_cancelled_approval_cannot_open_camera(self):
        access=camera_input.CameraAccess()
        request=camera_input.CameraPermission('Look at this','/dev/video0',threading.Event())
        request.decide(True);request.expires=time.monotonic()-1
        with patch.dict('sys.modules',{'cv2':Mock()}) as modules:
            with self.assertRaises(RuntimeError):access.snapshot(request)
            modules['cv2'].VideoCapture.assert_not_called()

    def test_turning_camera_off_cancels_pending_permission(self):
        access=camera_input.CameraAccess();result=[]
        thread=threading.Thread(target=lambda:result.append(access.request_permission('Look at this',threading.Event())))
        thread.start();request=access.requests.get(timeout=2)
        access.set_enabled(False);request.decide(True)
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertEqual(result,[None])
        self.assertFalse(request.consume())

    def test_new_question_needs_new_dialog(self):
        access=camera_input.CameraAccess();seen=[]
        for _ in range(2):
            result=[]
            thread=threading.Thread(target=lambda:result.append(access.request_permission('Look at this',threading.Event())))
            thread.start();request=access.requests.get(timeout=2)
            self.assertFalse(request.allowed)
            request.decide(False);thread.join(timeout=2);seen.append(request)
        self.assertIsNot(seen[0],seen[1])

    def test_camera_never_uses_cloud_mode(self):
        camera=Mock();camera.answer.return_value='A keyboard.'
        router=Mock();router.choose.return_value=('cloud','What do you see?')
        with patch.object(desktop,'build_opener') as local_model:
            reply,history=desktop.ask_ollama([], 'What do you see?',camera=camera,router=router)
        self.assertEqual(reply,'A keyboard.')
        router.cloud_answer.assert_not_called();local_model.assert_not_called()
        self.assertNotIn('images',history[-1])

    def test_remote_ollama_refused_before_permission_request(self):
        access=camera_input.CameraAccess()
        with patch.dict('os.environ',{'OLLAMA_URL':'https://example.com'}),patch.object(access,'request_permission') as permission:
            with self.assertRaisesRegex(RuntimeError,'on this PC'):
                access.answer('What do you see?')
            permission.assert_not_called()


if __name__=='__main__':unittest.main()
