#!/usr/bin/env python3
"""Speak every line of explainer.json into voice/NN.wav (and voice/end.wav) with the approved female voice.

Usage: python3 tts.py explainer.json [--only N]
       python3 tts.py --say en|de "text" out.wav
English: Kokoro-82M, voice af_heart, via mlx-audio. German: Chatterbox Multilingual (Resemble AI) with the
Piper voice de_DE-kerstin as the timbre template, exaggeration 0.95, cfg 0.25 (approved by Tobi 2026-11-03, "w2").
Both run locally from the venvs in ~/.local/share/ramus-tts (NA17: one natural female voice per language,
approved by Tobi; never the system text-to-speech voice).

Only one model runs at a time, and a watchdog kills it when free memory drops below MIN_FREE percent:
on 2026-11-03 the Mac hung while both models were loaded beside two VMs and the simulators.
"""
import json
import os
import subprocess
import sys
import time

VENVS = os.path.expanduser("~/.local/share/ramus-tts")
MIN_FREE = 25  # percent, kern.memorystatus_level
KOKORO = """
import sys, wave, numpy as np
from mlx_audio.tts.utils import load_model
model = load_model("mlx-community/Kokoro-82M-bf16")
for text, path in zip(sys.argv[1::2], sys.argv[2::2]):
    a = np.concatenate([np.array(r.audio).reshape(-1) for r in model.generate(text=text, voice="af_heart", speed=1.0, lang_code="a")])
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
"""
CHATTERBOX = """
import os, sys, wave, torch, numpy as np
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
device = "mps" if torch.backends.mps.is_available() else "cpu"
model = ChatterboxMultilingualTTS.from_pretrained(device=device)
for text, path in zip(sys.argv[1::2], sys.argv[2::2]):
    with torch.inference_mode():
        a = model.generate(text, language_id="de", audio_prompt_path=os.environ.get("VOICE_REF") or os.path.expanduser("~/.local/share/ramus-tts/voice-ref-kerstin.wav"),
                           exaggeration=float(os.environ.get("VOICE_EXAGGERATION", "0.95")),
                           cfg_weight=float(os.environ.get("VOICE_CFG", "0.25"))).cpu().numpy().reshape(-1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(model.sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
    if device == "mps":
        torch.mps.empty_cache()
"""


def free_percent():
    out = subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True, text=True).stdout
    return int(out.strip() or 0)


def speak(language, pairs):
    if free_percent() < MIN_FREE + 20:
        sys.exit(f"only {free_percent()}% memory free; close something before loading a voice model")
    if language == "de":
        python, code = os.path.join(VENVS, "chatterbox/bin/python"), CHATTERBOX
    else:
        python, code = os.path.join(VENVS, "kokoro/bin/python"), KOKORO
    env = dict(os.environ, PYTORCH_MPS_HIGH_WATERMARK_RATIO="0.4", PYTORCH_MPS_LOW_WATERMARK_RATIO="0.3", OMP_NUM_THREADS="4")
    args = [x for text, path in pairs for x in (text, path)]
    proc = subprocess.Popen([python, "-c", code, *args], env=env)
    lowest = 100
    while proc.poll() is None:
        level = free_percent()
        lowest = min(lowest, level)
        if level < MIN_FREE:
            proc.kill()
            proc.wait()
            sys.exit(f"stopped: free memory fell to {level}%")
        time.sleep(0.5)
    if proc.returncode:
        sys.exit(f"voice model failed with exit code {proc.returncode}")
    print(f"lowest free memory during the run: {lowest}%")


def main():
    if sys.argv[1] == "--say":
        speak(sys.argv[2], [(sys.argv[3], sys.argv[4])])
        return
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path))
    base = os.path.dirname(os.path.abspath(spec_path))
    out = os.path.join(base, spec.get("voice_dir", "voice"))
    os.makedirs(out, exist_ok=True)
    lines = [b["text"] for ch in spec["chapters"] for b in ch["beats"]]
    pairs = [(text, os.path.join(out, f"{i + 1:02d}.wav")) for i, text in enumerate(lines)]
    if spec.get("closing"):
        pairs.append((spec["closing"], os.path.join(out, "end.wav")))
    if "--only" in sys.argv:
        n = int(sys.argv[sys.argv.index("--only") + 1])
        pairs = pairs[n - 1:n]
    speak(spec.get("language", "en"), pairs)
    print(f"{len(pairs)} lines spoken into {out}")


if __name__ == "__main__":
    main()
