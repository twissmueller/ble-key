#!/usr/bin/env python3
"""Render store preview videos from real app screenshots (knowledge P9 step 8.3).

Usage: python3 render.py shots.json [target ...]
Targets: iphone (886x1920), ipad (1200x1600), mac (1920x1080), play (1920x1080, 16:9 for YouTube).

Each shot shows one real app screen with one line of text, slowly zooming in; shots cross-fade.
The end card shows icon, name, a tagline, the platforms and the ramuslabs.com link. The soundtrack
is synthesized here (soft chords, no licensing). Needs ffmpeg and ImageMagick (`magick`).
"""
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave

import numpy as np

TARGETS = {
    "iphone": (886, 1920),
    "ipad": (1200, 1600),
    "mac": (1920, 1080),
    "play": (1920, 1080),
}
FPS = 30
FADE = 0.4


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def image_size(path):
    out = subprocess.run(["magick", "identify", "-format", "%w %h", path + "[0]"],
                         check=True, capture_output=True, text=True).stdout
    w, h = out.split()
    return int(w), int(h)


def rounded(src, w, h, radius, dst, crop=None):
    """Scale src into w x h (after an optional fractional crop) with rounded corners and a soft shadow."""
    pre = []
    if crop:
        iw, ih = image_size(src)
        x0, y0, x1, y1 = crop
        pre = ["-crop", f"{int((x1 - x0) * iw)}x{int((y1 - y0) * ih)}+{int(x0 * iw)}+{int(y0 * ih)}", "+repage"]
    run(["magick", src, *pre, "-resize", f"{w}x{h}!", "-alpha", "off",
         "(", "-size", f"{w}x{h}", "xc:black", "-fill", "white",
         "-draw", f"roundrectangle 0,0 {w - 1},{h - 1} {radius},{radius}", ")",
         "-compose", "CopyOpacity", "-composite", "-compose", "over",
         "(", "+clone", "-background", "#00000040", "-shadow", f"60x{max(6, radius // 3)}+0+{radius // 4}", ")",
         "+swap", "-background", "none", "-layers", "merge", "+repage", dst])


def caption(text, font, size, color, width, dst, gravity="center"):
    run(["magick", "-background", "none", "-fill", color, "-font", font, "-pointsize", str(size),
         "-size", f"{width}x", "-gravity", gravity, f"caption:{text}", "-trim", "+repage", dst])


def compose_shot(spec, shot, target, tmp, idx):
    W, H = TARGETS[target]
    images = shot["image"]
    src = images.get(target) or images.get("default")
    src = os.path.join(spec["_dir"], src)
    crop = shot.get("crop", {}).get(target) if isinstance(shot.get("crop"), dict) else shot.get("crop")
    iw, ih = image_size(src)
    if crop:
        iw, ih = (crop[2] - crop[0]) * iw, (crop[3] - crop[1]) * ih
    aspect = iw / ih
    font_b, font_r = spec["font_bold"], spec["font_regular"]
    fg, sub = spec["fg"], spec.get("fg_secondary", spec["fg"])
    canvas = os.path.join(tmp, f"{target}-{idx}.png")
    screen = os.path.join(tmp, f"{target}-{idx}-screen.png")
    head = os.path.join(tmp, f"{target}-{idx}-head.png")
    subl = os.path.join(tmp, f"{target}-{idx}-sub.png")
    landscape = W > H
    side = landscape and aspect < 1.0
    if side:
        sh = int(H * 0.86)
        sw = int(sh * aspect)
        hs = int(H * 0.075)
        caption(shot["headline"], font_b, hs, fg, int(W * 0.46), head, "west")
        if shot.get("sub"):
            caption(shot["sub"], font_r, int(hs * 0.6), sub, int(W * 0.46), subl, "west")
        rounded(src, sw, sh, int(sw * 0.07), screen, crop)
        sx, sy = int(W * 0.08), (H - sh) // 2
        tx = sx + sw + int(W * 0.08)
        layers = [(screen, sx, sy - int(sh * 0.01))]
        hh = image_size(head)[1]
        block = hh + (image_size(subl)[1] + int(hs * 0.5) if shot.get("sub") else 0)
        ty = (H - block) // 2
        layers.append((head, tx, ty))
        if shot.get("sub"):
            layers.append((subl, tx, ty + hh + int(hs * 0.5)))
    else:
        cap_h = int(H * (0.2 if not landscape else 0.2))
        avail_h = H - cap_h - int(H * 0.06)
        sw = min(int(W * 0.86), int(avail_h * aspect))
        sh = int(sw / aspect)
        if sh > avail_h:
            sh = avail_h
            sw = int(sh * aspect)
        hs = int(min(W, H) * (0.058 if not landscape else 0.06))
        caption(shot["headline"], font_b, hs, fg, int(W * 0.9), head)
        if shot.get("sub"):
            caption(shot["sub"], font_r, int(hs * 0.66), sub, int(W * 0.9), subl)
        rounded(src, sw, sh, int(min(sw, sh) * 0.06), screen, crop)
        sy = int(H * 0.05)
        layers = [(screen, (W - sw) // 2 - int(sw * 0.0), sy)]
        cy = sy + sh + int(H * 0.035)
        hw, hh = image_size(head)
        layers.append((head, (W - hw) // 2, cy))
        if shot.get("sub"):
            sw2, _ = image_size(subl)
            layers.append((subl, (W - sw2) // 2, cy + hh + int(hs * 0.35)))
        # Centre the whole block vertically when the screen leaves room below.
        bottom = max(y + image_size(path)[1] for path, _, y in layers)
        shift = (H - (bottom - sy)) // 2 - sy
        if shift > 0:
            layers = [(path, x, y + shift) for path, x, y in layers]
    cmd = ["magick", "-size", f"{W}x{H}", f"xc:{spec['bg']}"]
    for path, x, y in layers:
        cmd += [path, "-geometry", f"+{x}+{y}", "-composite"]
    run(cmd + ["-alpha", "off", canvas])
    return canvas


def compose_end(spec, target, tmp):
    W, H = TARGETS[target]
    end = spec["endcard"]
    fg, sub = spec["fg"], spec.get("fg_secondary", spec["fg"])
    icon = os.path.join(tmp, f"{target}-icon.png")
    s = int(min(W, H) * 0.26)
    rounded(os.path.join(spec["_dir"], spec["icon"]), s, s, int(s * 0.225), icon)
    parts = [(icon, int(min(W, H) * 0.05))]
    base = int(min(W, H) * 0.075)
    lines = [(spec["app"], spec["font_bold"], base, fg)]
    if end.get("tagline"):
        lines.append((end["tagline"], spec["font_regular"], int(base * 0.56), sub))
    platforms = end.get("platforms_" + target) or end.get("platforms")
    if platforms:
        lines.append((platforms, spec["font_regular"], int(base * 0.5), sub))
    lines.append((end["url"], spec["font_bold"], int(base * 0.55), spec.get("accent", fg)))
    for i, (text, font, size, color) in enumerate(lines):
        p = os.path.join(tmp, f"{target}-end-{i}.png")
        caption(text, font, size, color, int(W * 0.9), p)
        parts.append((p, int(size * 0.45)))
    heights = [image_size(p)[1] + gap for p, gap in parts]
    y = (H - sum(heights)) // 2
    canvas = os.path.join(tmp, f"{target}-end.png")
    cmd = ["magick", "-size", f"{W}x{H}", f"xc:{spec['bg']}"]
    for (p, gap), h in zip(parts, heights):
        w = image_size(p)[0]
        cmd += [p, "-geometry", f"+{(W - w) // 2}+{y}", "-composite"]
        y += h
    run(cmd + ["-alpha", "off", canvas])
    return canvas


def clip(png, dur, target, dst, zoom=0.035):
    W, H = TARGETS[target]
    total = dur + FADE
    # Slow zoom in; rendering at 2x and scaling down keeps the motion smooth.
    vf = (f"scale={W * 2}:{H * 2},"
          f"scale=w='trunc({W * 2}*(1+{zoom}*t/{total})/2)*2':h=-2:eval=frame,"
          f"crop={W * 2}:{H * 2},scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{total:.3f}", "-i", png,
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(FPS), dst])


def soundtrack(seconds, dst, seed=1):
    """Soft synthesized chords with a gentle pluck, quiet enough to sit under the pictures."""
    sr = 44100
    n = int(seconds * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    bpm = 84
    beat = 60 / bpm
    bar = beat * 4
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]]

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    out = np.zeros((n, 2))
    for b in range(int(seconds / bar) + 1):
        start = int(b * bar * sr)
        if start >= n:
            break
        seg = np.arange(min(n - start, int(bar * sr * 1.3)))
        st = seg / sr
        env = np.minimum(st / 0.6, 1) * np.exp(-st / 3.0)
        for i, m in enumerate(chords[b % 4]):
            f = hz(m - 12)
            v = (np.sin(2 * np.pi * f * st) + 0.3 * np.sin(2 * np.pi * f * 2.003 * st)) * env * 0.05
            pan = 0.35 + 0.1 * i
            out[start:start + len(seg), 0] += v * (1 - pan)
            out[start:start + len(seg), 1] += v * pan
        for k in range(8):
            ps = start + int(k * beat / 2 * sr)
            if ps >= n:
                break
            m = chords[b % 4][[0, 2, 1, 3, 2, 1, 3, 2][k]] + 12
            pl = np.arange(min(n - ps, int(0.9 * sr)))
            pt = pl / sr
            v = np.sin(2 * np.pi * hz(m) * pt) * np.exp(-pt / 0.25) * 0.035 * (0.8 + 0.4 * rng.random())
            pan = 0.3 + 0.4 * rng.random()
            out[ps:ps + len(pl), 0] += v * (1 - pan)
            out[ps:ps + len(pl), 1] += v * pan
    fade = np.minimum(1, np.minimum(t / 1.0, (seconds - t) / 1.5))[:, None]
    out = np.clip(out * fade / max(1e-9, np.abs(out).max()) * 0.35, -1, 1)
    with wave.open(dst, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype("<i2").tobytes())


MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....",
         "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.",
         "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
         "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
         "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----."}


def add_morse(path, cues):
    """Mix a sidetone (sine with soft keying) for each cue {at, text, wpm, hz} into the wav at path."""
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2).astype(float) / 32767
    data = data.copy()
    for cue in cues:
        unit = 1.2 / cue.get("wpm", 20)
        f = cue.get("hz", 600)
        pos = cue["at"]
        for word in cue["text"].upper().split():
            for ch in word:
                for sym in MORSE.get(ch, ""):
                    d = unit * (3 if sym == "-" else 1)
                    n0, n = int(pos * sr), int(d * sr)
                    tt = np.arange(n) / sr
                    ramp = np.minimum(1, np.minimum(tt / 0.005, (d - tt) / 0.005))
                    tone = np.sin(2 * np.pi * f * tt) * ramp * cue.get("gain", 0.22)
                    end = min(len(data), n0 + n)
                    data[n0:end] += tone[:end - n0, None]
                    pos += d + unit
                pos += 2 * unit
            pos += 4 * unit
    data = np.clip(data, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((data * 32767).astype("<i2").tobytes())


def render(spec, target, outdir):
    with tempfile.TemporaryDirectory() as tmp:
        clips, durs, cues = [], [], []
        for i, shot in enumerate(spec["shots"]):
            if target in shot.get("skip", []):
                continue
            for cue in shot.get("morse", []):
                text = cue["text"] if isinstance(cue["text"], str) else cue["text"].get(target, cue["text"]["default"])
                cues.append(dict(cue, text=text, at=sum(durs) + cue.get("at", 0.5)))
            png = compose_shot(spec, shot, target, tmp, i)
            c = os.path.join(tmp, f"{target}-{i}.mp4")
            clip(png, shot["duration"], target, c)
            clips.append(c)
            durs.append(shot["duration"])
        png = compose_end(spec, target, tmp)
        c = os.path.join(tmp, f"{target}-end.mp4")
        end_d = spec["endcard"]["duration"]
        clip(png, end_d, target, c, zoom=0.0)
        clips.append(c)
        durs.append(end_d)
        total = sum(durs) + FADE  # every clip carries FADE extra; the transitions use it up
        filt, last, offset = [], "0:v", 0.0
        for i in range(1, len(clips)):
            offset += durs[i - 1]
            filt.append(f"[{last}][{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[v{i}]")
            last = f"v{i}"
        audio = os.path.join(tmp, "music.wav")
        length = sum(durs)
        soundtrack(length, audio, seed=spec.get("seed", 1))
        if cues:
            add_morse(audio, cues)
        name = spec["slug"] + "-" + target
        dst = os.path.join(outdir, f"{name}-{TARGETS[target][0]}x{TARGETS[target][1]}.mp4")
        cmd = ["ffmpeg", "-y"]
        for c in clips:
            cmd += ["-i", c]
        cmd += ["-i", audio, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", f"{len(clips)}:a",
                "-t", f"{length:.3f}", "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "256k", "-ar", "44100",
                "-movflags", "+faststart", dst]
        run(cmd)
        return dst


def main():
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path))
    spec["_dir"] = os.path.dirname(os.path.abspath(spec_path))
    targets = sys.argv[2:] or spec.get("targets", ["iphone"])
    outdir = os.path.join(spec["_dir"])
    for t in targets:
        print(render(spec, t, outdir))


if __name__ == "__main__":
    main()
