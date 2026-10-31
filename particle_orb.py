"""Dependency-free particle geometry, shared by the native window and preview."""
import math
import random


class ParticleCloud:
    def __init__(self, count=3200):
        randomizer = random.Random(19)
        self.points = []
        for index in range(count):
            y = randomizer.uniform(-1, 1)
            radius = math.sqrt(max(0, 1 - y * y))
            angle = randomizer.uniform(0, math.tau)
            self.points.append((radius * math.cos(angle), y, radius * math.sin(angle),
                                randomizer.random(), randomizer.random()))

    def frame(self, elapsed, mode='idle'):
        """Yield x, y, dot diameter and RGBA, in units of the cloud radius."""
        activity = {'idle': .0, 'waiting': .15, 'listening': .5,
                    'thinking': .3, 'speaking': .8, 'paused': -.15}.get(mode, .0)
        t = elapsed * .32
        turn = elapsed * .12
        ca, sa = math.cos(turn), math.sin(turn)
        tilt = -.28 + .22 * math.sin(t * .43)
        cb, sb = math.cos(tilt), math.sin(tilt)
        pulse = 1 + .025 * math.sin(elapsed * (3.5 if activity > .4 else 1.1)) * (1 + activity)
        for x, y, z, seed, shimmer in self.points:
            # Fold an irregular spherical surface into gently moving ribbons.
            wave = math.sin(3.0 * y + 2.4 * z + t)
            ripple = math.sin(4.0 * x - 2.0 * y - t * .8)
            radius = (1 + .22 * wave + .12 * ripple) * pulse
            xx = x * radius + .16 * math.sin(3 * y + t * .7) * (1 - x * x)
            yy = y * radius + .18 * math.sin(3 * z - t * .8) * (1 - y * y)
            zz = z * radius + .20 * math.sin(3 * x + t) * (1 - z * z)
            rx, rz = xx * ca + zz * sa, zz * ca - xx * sa
            ry, rz = yy * cb - rz * sb, yy * sb + rz * cb
            perspective = 3.8 / (3.8 - rz)
            edge = (abs(x) ** 2 + abs(y) ** 2) ** .5
            ridge = (.5 + .5 * math.sin(7 * y + 4 * z + t)) ** 7
            depth = max(.08, min(1., .48 + .35 * rz))
            sparkle = .78 + .22 * math.sin(elapsed * .7 + shimmer * 40)
            light = max(.08, min(1., (depth * .55 + ridge * .55 + edge * .12) * sparkle))
            alpha = int(min(230, (22 + light * 190) * (.25 + seed * .75)))
            if mode == 'paused':
                alpha = int(alpha * .55)
            red = int(90 + 130 * light)
            green = int(115 + 125 * light)
            diameter = (.45 + seed * .55 + ridge * .25) * perspective
            yield rx * perspective, ry * perspective, diameter, (red, green, 255, alpha)
