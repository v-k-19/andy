"""Run on your PC to list inputs and measure five seconds of live signal."""
import argparse
import queue
import time
from microphone_input import audio_levels, input_device


def main():
    parser = argparse.ArgumentParser(description='Check microphone signal locally. No recordings are saved or uploaded.')
    parser.add_argument('--device', help='Input number or name; defaults to ANDY_INPUT_DEVICE or the system default')
    parser.add_argument('--list', action='store_true', help='List devices without opening the microphone')
    args = parser.parse_args()
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print('Available microphone inputs:')
        for index, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"  {index}: {device['name']}")
        if args.list:
            return
        selected = input_device(args.device)
        device = sd.query_devices(selected, 'input')
        rate = int(device['default_samplerate'])
        print(f"\nTesting: {device['name']} at {rate} Hz")
        print('Speak for five seconds. Audio is measured in memory, not saved or uploaded.')
        audio = queue.Queue(maxsize=30)
        dropped = False
        def callback(data, frames, timing, status):
            nonlocal dropped
            if status: dropped = True
            try: audio.put_nowait(bytes(data))
            except queue.Full: dropped = True
        maximum = 0.
        frames = 0
        with sd.RawInputStream(samplerate=rate, blocksize=int(rate / 5), device=selected,
                               dtype='int16', channels=1, callback=callback):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try: data = audio.get(timeout=.3)
                except queue.Empty: continue
                peak, rms = audio_levels(data)
                maximum = max(maximum, peak)
                frames += 1
                print(f'  Signal: {peak * 100:5.1f}% peak, {rms * 100:5.2f}% average')
        if frames == 0:
            print('FAIL: No audio frames arrived. Check the input device and audio service.')
        elif maximum < .005:
            print('Very little signal: check mute, input volume, and whether Pixy is the selected microphone.')
        else:
            print('Audio signal detected. If you were speaking, try Talk now to bypass the wake word.')
        if dropped:
            print('Audio interruptions were reported; close other CPU-heavy apps and retry.')
    except (ImportError, OSError, ValueError) as exc:
        print('Microphone test could not start:', exc)
        print('Run bash install-desktop.sh and check your system input settings.')
    except Exception as exc:
        print('Microphone input error:', exc)
        print('Use --list or --device NUMBER to select another microphone.')


if __name__ == '__main__':
    main()
