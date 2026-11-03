#!/usr/bin/env python3
"""Render the YouTube explainer (1920x1080) from explainer.json and the voice-over in voice/.

Usage: python3 explainer.py explainer.json [--draft]
Each beat is one spoken line over one real app screen (or product photo); the line also runs as a subtitle.
The voice-over files voice/NN.wav come from tts.py (one natural female voice, approved by Tobi, NA17).
--draft renders without voice, timing each line at speaking pace, to check the pictures.
Uses the helpers of the store preview renderer (render.py), named in the spec as "renderer".
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

W, H, FPS = 1920, 1080, 30
GAP = 0.5  # silence after each line


def load_renderer(path):
    spec = importlib.util.spec_from_file_location("render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wav_seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


def read_wav(path, sr=44100):
    """Read any wav as stereo float at sr (resampled with ffmpeg)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2)


def compose_beat(r, spec, beat, chapter, tmp, idx):
    src = os.path.join(spec["_dir"], beat["image"])
    crop = beat.get("crop")
    iw, ih = r.image_size(src)
    if crop:
        iw, ih = (crop[2] - crop[0]) * iw, (crop[3] - crop[1]) * ih
    aspect = iw / ih
    fg, sub, accent = spec["fg"], spec.get("fg_secondary", spec["fg"]), spec.get("accent", spec["fg"])
    screen = os.path.join(tmp, f"b{idx}-screen.png")
    label = os.path.join(tmp, f"b{idx}-label.png")
    line = os.path.join(tmp, f"b{idx}-line.png")
    r.caption(chapter.upper(), spec["font_bold"], 26, accent, 800, label, "west" if aspect < 1.2 else "center")
    layers = []
    if aspect < 1.2:
        sh = int(H * 0.86)
        sw = int(sh * aspect)
        if sw > W * 0.5:
            sw = int(W * 0.5)
            sh = int(sw / aspect)
        r.rounded(src, sw, sh, int(min(sw, sh) * 0.05), screen, crop)
        sx, sy = int(W * 0.07), (H - sh) // 2
        tx = sx + sw + int(W * 0.07)
        tw = W - tx - int(W * 0.07)
        r.caption(beat["text"], spec["font_bold"], 54, fg, tw, line, "west")
        lh = r.image_size(label)[1]
        th = r.image_size(line)[1]
        ty = (H - (lh + 28 + th)) // 2
        layers = [(screen, sx, sy), (label, tx, ty), (line, tx, ty + lh + 28)]
    else:
        avail_h = int(H * 0.66)
        sw = min(int(W * 0.84), int(avail_h * aspect))
        sh = int(sw / aspect)
        r.rounded(src, sw, sh, int(min(sw, sh) * 0.035), screen, crop)
        r.caption(beat["text"], spec["font_bold"], 42, fg, int(W * 0.8), line)
        lw, lh = r.image_size(label)
        tw, th = r.image_size(line)
        top = (H - (lh + 22 + sh + 36 + th)) // 2
        layers = [(label, (W - lw) // 2, top), (screen, (W - sw) // 2, top + lh + 22),
                  (line, (W - tw) // 2, top + lh + 22 + sh + 36)]
    canvas = os.path.join(tmp, f"b{idx}.png")
    cmd = ["magick", "-size", f"{W}x{H}", f"xc:{spec['bg']}"]
    for path, x, y in layers:
        cmd += [path, "-geometry", f"+{x}+{y}", "-composite"]
    r.run(cmd + ["-alpha", "off", canvas])
    return canvas


def compose_title(r, spec, tmp):
    icon = os.path.join(tmp, "t-icon.png")
    s = 260
    r.rounded(os.path.join(spec["_dir"], spec["icon"]), s, s, int(s * 0.225), icon)
    title = os.path.join(tmp, "t-title.png")
    r.caption(spec["title_card"], spec["font_bold"], 64, spec["fg"], int(W * 0.8), title)
    tw, th = r.image_size(title)
    top = (H - (s + 50 + th)) // 2
    canvas = os.path.join(tmp, "title.png")
    r.run(["magick", "-size", f"{W}x{H}", f"xc:{spec['bg']}", icon, "-geometry", f"+{(W - s) // 2}+{top}",
           "-composite", title, "-geometry", f"+{(W - tw) // 2}+{top + s + 50}", "-composite", "-alpha", "off", canvas])
    return canvas


def main():
    spec_path = sys.argv[1]
    draft = "--draft" in sys.argv
    spec = json.load(open(spec_path))
    spec["_dir"] = os.path.dirname(os.path.abspath(spec_path))
    r = load_renderer(os.path.join(spec["_dir"], spec["renderer"]))
    r.TARGETS["explainer"] = (W, H)
    voice_dir = os.path.join(spec["_dir"], spec.get("voice_dir", "voice"))
    beats = [(ch["title"], b) for ch in spec["chapters"] for b in ch["beats"]]
    end_text = spec.get("closing")
    with tempfile.TemporaryDirectory() as tmp:
        clips, durs, voices = [], [], []
        title = compose_title(r, spec, tmp)
        c = os.path.join(tmp, "title.mp4")
        r.clip(title, 3.5, "explainer", c, zoom=0.0)
        clips.append(c)
        durs.append(3.5)
        t = 3.5
        for i, (chapter, beat) in enumerate(beats):
            wav = os.path.join(voice_dir, f"{i + 1:02d}.wav")
            if draft or not os.path.exists(wav):
                if not draft:
                    sys.exit(f"missing {wav}; run tts.py first or use --draft")
                length = len(beat["text"].split()) / 2.6
            else:
                length = wav_seconds(wav)
                voices.append((t + 0.15, wav))
            d = round(length + 0.15 + GAP, 3)
            png = compose_beat(r, spec, beat, chapter, tmp, i)
            c = os.path.join(tmp, f"b{i}.mp4")
            r.clip(png, d, "explainer", c, zoom=0.025)
            clips.append(c)
            durs.append(d)
            t += d
        end = r.compose_end(spec, "explainer", tmp)
        end_d = 5.0
        if end_text:
            wav = os.path.join(voice_dir, "end.wav")
            if os.path.exists(wav) and not draft:
                voices.append((t + 0.3, wav))
                end_d = max(end_d, wav_seconds(wav) + 1.5)
        c = os.path.join(tmp, "end.mp4")
        r.clip(end, end_d, "explainer", c, zoom=0.0)
        clips.append(c)
        durs.append(end_d)
        length = sum(durs)

        sr = 44100
        music = os.path.join(tmp, "music.wav")
        r.soundtrack(length, music, seed=spec.get("seed", 1))
        mix = read_wav(music, sr) * spec.get("music_level", 0.35)
        for at, wav in voices:
            v = read_wav(wav, sr) * spec.get("voice_level", 0.9)
            n0 = int(at * sr)
            n1 = min(len(mix), n0 + len(v))
            mix[n0:n1] += v[:n1 - n0]
        mix = np.clip(mix, -1, 1)
        audio = os.path.join(tmp, "mix.wav")
        with wave.open(audio, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((mix * 32767).astype("<i2").tobytes())

        filt, last, offset = [], "0:v", 0.0
        for i in range(1, len(clips)):
            offset += durs[i - 1]
            filt.append(f"[{last}][{i}:v]xfade=transition=fade:duration={r.FADE}:offset={offset:.3f}[v{i}]")
            last = f"v{i}"
        suffix = "-draft" if draft else ""
        dst = os.path.join(spec["_dir"], f"{spec['slug']}-explainer{suffix}-1920x1080.mp4")
        cmd = ["ffmpeg", "-y"]
        for c in clips:
            cmd += ["-i", c]
        # Loudness for YouTube: about -14 LUFS integrated, peaks below -1.5 dBTP.
        filt.append(f"[{len(clips)}:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        cmd += ["-i", audio, "-filter_complex", ";".join(filt), "-map", f"[{last}]", "-map", "[a]",
                "-t", f"{length:.3f}", "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", dst]
        r.run(cmd)
        print(dst, f"{length:.1f}s")


if __name__ == "__main__":
    main()
