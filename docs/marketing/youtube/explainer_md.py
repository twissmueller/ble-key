#!/usr/bin/env python3
"""Write youtube/explainer.md from explainer.json and the spoken lines: title, description, chapters with times."""
import json, os, re, sys, wave
spec_path = sys.argv[1]
base = os.path.dirname(os.path.abspath(spec_path))
spec = json.load(open(spec_path))
md_path = os.path.join(base, "explainer.md")
old = open(md_path).read() if os.path.exists(md_path) else ""
head = [l for l in old.splitlines() if re.match(r"\*\*(Title|Titel|Description|Beschreibung|Tags)", l)]
t, n, chapters, body = 3.5, 0, [], []
for ch in spec["chapters"]:
    chapters.append((t, ch["title"]))
    body.append(f"\n## {ch['title']}\n")
    for b in ch["beats"]:
        n += 1
        with wave.open(os.path.join(base, "voice", f"{n:02d}.wav")) as w:
            d = w.getnframes() / w.getframerate()
        t += d + 0.65
        body.append(f"- {b['text']} *({os.path.basename(b['image'])})*")
stamp = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"
chap = " · ".join(f"{'0:00' if i == 0 else stamp(s)} {name}" for i, (s, name) in enumerate(chapters))
de = spec.get("language") == "de"
lines = [f"# {spec['app']}: {'Erklärvideo' if de else 'explainer'}", "",
         ("Erzählt von der freigegebenen Frauenstimme (NA17), gerendert mit `explainer.py`; Text und Bilder in `explainer.json`."
          if de else "Narrated by the approved female voice (NA17), rendered with `explainer.py`; lines and pictures in `explainer.json`."),
         "", *head, f"**{'Kapitel' if de else 'Chapters'}:** {chap}", *body,
         "", f"## {'Schluss' if de else 'Closing'}", "", f"- {spec.get('closing', '')}", ""]
open(md_path, "w").write("\n".join(lines))
print(md_path)
