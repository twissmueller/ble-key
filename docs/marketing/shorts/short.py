#!/usr/bin/env python3
"""Render a YouTube Short / Instagram Reel (1080x1920) from shorts/NN-name.json and its voice-over.

Usage: python3 short.py NN-name.json [--draft]
Each beat is one spoken line over one real app screen (or product photo); the line runs as a large caption
below the picture, inside the area that Shorts and Reels leave free of their own buttons. The first beat is the
hook, shown bigger. The voice-over (voice_dir/NN.wav, end.wav) comes from tts.py with the approved female voice
(NA17). Uses the helpers of the store preview renderer (render.py), named in the spec as "renderer".
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

W, H, FPS = 1080, 1920, 30
GAP = 0.35
TOP, BOTTOM = 170, 1560  # keep clear of the Shorts/Reels header and the buttons at the bottom


def load(path):
    spec = importlib.util.spec_from_file_location("render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def read_wav(path, sr=44100):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2)


def compose(r, spec, beat, hook, tmp, idx):
    src = os.path.join(spec["_dir"], beat["image"])
    crop = beat.get("crop")
    iw, ih = r.image_size(src)
    if crop:
        iw, ih = (crop[2] - crop[0]) * iw, (crop[3] - crop[1]) * ih
    aspect = iw / ih
    line = os.path.join(tmp, f"s{idx}-line.png")
    r.caption(beat["text"], spec["font_bold"], 88 if hook else 66, spec["fg"], 940, line)
    lw, lh = r.image_size(line)
    room = BOTTOM - TOP - lh - 60
    sw = 940
    sh = int(sw / aspect)
    if sh > room:
        sh = room
        sw = int(sh * aspect)
    screen = os.path.join(tmp, f"s{idx}-screen.png")
    r.rounded(src, sw, sh, int(min(sw, sh) * 0.05), screen, crop)
    block = sh + 60 + lh
    top = TOP + (BOTTOM - TOP - block) // 2
    if hook:  # the hook reads first: text above the picture
        layers = [(line, (W - lw) // 2, top), (screen, (W - sw) // 2, top + lh + 60)]
    else:
        layers = [(screen, (W - sw) // 2, top), (line, (W - lw) // 2, top + sh + 60)]
    canvas = os.path.join(tmp, f"s{idx}.png")
    cmd = ["magick", "-size", f"{W}x{H}", f"xc:{spec['bg']}"]
    for path, x, y in layers:
        cmd += [path, "-geometry", f"+{x}+{y}", "-composite"]
    r.run(cmd + ["-alpha", "off", canvas])
    return canvas


def main():
    spec_path = sys.argv[1]
    draft = "--draft" in sys.argv
    spec = json.load(open(spec_path))
    spec["_dir"] = os.path.dirname(os.path.abspath(spec_path))
    r = load(os.path.join(spec["_dir"], spec["renderer"]))
    r.TARGETS["short"] = (W, H)
    voice = os.path.join(spec["_dir"], spec["voice_dir"])
    beats = [b for ch in spec["chapters"] for b in ch["beats"]]
    with tempfile.TemporaryDirectory() as tmp:
        clips, durs, voices, t = [], [], [], 0.0
        for i, beat in enumerate(beats):
            wav = os.path.join(voice, f"{i + 1:02d}.wav")
            if draft:
                length = len(beat["text"].split()) / 2.6
            else:
                length = seconds(wav)
                voices.append((t + 0.15, wav))
            d = round(length + 0.15 + GAP, 3)
            png = compose(r, spec, beat, i == 0, tmp, i)
            c = os.path.join(tmp, f"s{i}.mp4")
            r.clip(png, d, "short", c, zoom=0.03)
            clips.append(c)
            durs.append(d)
            t += d
        end_d = 3.0
        wav = os.path.join(voice, "end.wav")
        if spec.get("closing") and not draft:
            voices.append((t + 0.25, wav))
            end_d = max(end_d, seconds(wav) + 0.9)
        c = os.path.join(tmp, "end.mp4")
        r.clip(r.compose_end(spec, "short", tmp), end_d, "short", c, zoom=0.0)
        clips.append(c)
        durs.append(end_d)
        length = sum(durs)

        sr = 44100
        music = os.path.join(tmp, "music.wav")
        r.soundtrack(length, music, seed=spec.get("seed", 1))
        mix = read_wav(music, sr) * spec.get("music_level", 0.35)
        for at, path in voices:
            v = read_wav(path, sr) * 0.9
            n0 = int(at * sr)
            n1 = min(len(mix), n0 + len(v))
            mix[n0:n1] += v[:n1 - n0]
        audio = os.path.join(tmp, "mix.wav")
        with wave.open(audio, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())

        filt, last, offset = [], "0:v", 0.0
        for i in range(1, len(clips)):
            offset += durs[i - 1]
            filt.append(f"[{last}][{i}:v]xfade=transition=fade:duration={r.FADE}:offset={offset:.3f}[v{i}]")
            last = f"v{i}"
        filt.append(f"[{len(clips)}:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        name = os.path.splitext(os.path.basename(spec_path))[0]
        dst = os.path.join(spec["_dir"], f"{spec['slug']}-short-{name}{'-draft' if draft else ''}-1080x1920.mp4")
        cmd = ["ffmpeg", "-y"]
        for c in clips:
            cmd += ["-i", c]
        cmd += ["-i", audio, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "[a]",
                "-t", f"{length:.3f}", "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", dst]
        r.run(cmd)
        print(dst, f"{length:.1f}s")


if __name__ == "__main__":
    main()
