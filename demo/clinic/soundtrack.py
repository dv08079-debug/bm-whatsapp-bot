"""Build a royalty-free soundtrack for the demo video.

Synthesizes a calm background track and messenger-style sound cues timed
from the events JSON written by rec.js.

Usage: python3 soundtrack.py events-lv.json <duration_s> <trim_s> out.wav
"""
import json
import sys
import wave

import numpy as np

SR = 44100
BPM = 92
BEAT = 60 / BPM
BAR = 4 * BEAT


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, attack, decay_tau):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / decay_tau)


def tone(freq, dur, harmonics=(1.0, 0.35, 0.15), attack=0.005, tau=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = sum(h * np.sin(2 * np.pi * freq * (k + 1) * t) for k, h in enumerate(harmonics))
    return sig * env(n, attack, tau)


def lowpass(x, cutoff):
    # One-pole low-pass filter, good enough for softening pads and noise.
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def place(buf, sig, at, gain):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


# I–vi–IV–V in C major, two bars per chord.
CHORDS = [
    (48, [60, 64, 67, 72]),  # C
    (45, [57, 60, 64, 69]),  # Am
    (41, [57, 60, 65, 69]),  # F
    (43, [55, 59, 62, 67]),  # G
]


def music(duration):
    buf = np.zeros(int(duration * SR) + SR)
    pad = np.zeros_like(buf)
    bar_i, t = 0, 0.0
    while t < duration:
        root, notes = CHORDS[(bar_i // 2) % len(CHORDS)]
        # Pad: detuned sines held for the bar.
        n = int(BAR * SR)
        tt = np.arange(n) / SR
        shape = np.clip(tt / 0.6, 0, 1) * np.clip((BAR - tt) / 0.6, 0, 1)
        for note in notes[:3]:
            f = midi(note)
            pad_sig = (np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(2 * np.pi * f * 1.003 * tt)) * shape
            place(pad, pad_sig, t, 0.10)
        # Bass on beats 1 and 3.
        for b in (0, 2):
            place(buf, tone(midi(root), BEAT * 1.8, (1.0, 0.25), 0.01, 0.5), t + b * BEAT, 0.32)
        # Plucked arpeggio in eighth notes.
        pattern = [0, 1, 2, 3, 2, 1, 2, 3]
        for k, idx in enumerate(pattern):
            place(buf, tone(midi(notes[idx] + 12), 0.5, (1.0, 0.3, 0.1), 0.004, 0.22), t + k * BEAT / 2, 0.12)
        # Soft shaker on off-beats.
        for b in range(4):
            noise = np.random.default_rng(bar_i * 4 + b).standard_normal(int(0.06 * SR))
            noise *= env(len(noise), 0.002, 0.02)
            place(buf, np.diff(noise, prepend=0), t + b * BEAT + BEAT / 2, 0.025)
        t += BAR
        bar_i += 1
    buf += lowpass(pad, 1800)
    return buf[: int(duration * SR)]


def sfx(kind):
    if kind == 'sent':
        n = int(0.09 * SR)
        tt = np.arange(n) / SR
        f = np.linspace(700, 1300, n)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.003, 0.03)
    if kind == 'recv':
        a = tone(1318.5, 0.35, (1.0, 0.2), 0.002, 0.08)
        b = tone(1760.0, 0.4, (1.0, 0.2), 0.002, 0.1)
        out = np.zeros(int(0.5 * SR))
        out[: len(a)] += a
        i = int(0.07 * SR)
        out[i : i + len(b)] += b
        return out
    if kind == 'tap':
        return tone(2400, 0.04, (1.0,), 0.001, 0.008)
    if kind == 'stamp':
        return tone(980, 0.12, (1.0,), 0.002, 0.03) * 0.5
    if kind == 'whoosh':
        n = int(0.6 * SR)
        noise = np.random.default_rng(7).standard_normal(n)
        shape = np.sin(np.linspace(0, np.pi, n)) ** 2
        return lowpass(noise * shape, 2500) * 1.5
    if kind == 'chime':
        out = np.zeros(int(1.6 * SR))
        for k, note in enumerate((84, 88, 91, 96)):
            s = tone(midi(note), 1.2, (1.0, 0.4, 0.2), 0.003, 0.45)
            i = int(k * 0.09 * SR)
            out[i : i + len(s)] += s
        return out * 0.6
    return np.zeros(1)


SFX_GAIN = {'sent': 0.35, 'recv': 0.3, 'tap': 0.3, 'stamp': 0.25, 'whoosh': 0.12, 'chime': 0.3}


def main():
    events_path, duration, trim, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    events = json.load(open(events_path))
    mix = music(duration) * 0.55
    for e in events:
        at = e['t'] - trim
        if e['type'] in SFX_GAIN and at >= 0:
            place(mix, sfx(e['type']), at, SFX_GAIN[e['type']])
    # Fade in and out.
    fi, fo = int(1.5 * SR), int(3.0 * SR)
    mix[:fi] *= np.linspace(0, 1, fi)
    mix[-fo:] *= np.linspace(1, 0, fo)
    mix /= max(1e-9, np.abs(mix).max()) / 0.85
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(out, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    main()
