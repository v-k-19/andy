"""Small, local microphone diagnostics. No recordings are written."""
from array import array
import math
import os
import sys


def input_device(value=None):
    value = os.getenv('ANDY_INPUT_DEVICE') if value is None else value
    return int(value) if value and value.isdecimal() else value or None


def audio_levels(pcm):
    samples = array('h')
    samples.frombytes(pcm[:len(pcm) // 2 * 2])
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples:
        return 0., 0.
    peak = max(abs(sample) for sample in samples) / 32768
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
    return peak, rms
