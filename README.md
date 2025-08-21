---
title: Texture Constellations (Kazmaleje)
emoji: "✨"
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "4.42.0"
app_file: app.py
pinned: false
---

# Texture Constellations (Kazmaleje)

Generate a star map from hair texture attributes + a short message.
- SVG preview + SVG download (no OS dependencies)
- Private by default: the app does not store submissions

## How to use
1. Upload these files to the **root** of your Hugging Face Space (Files tab → *Add file* → *Upload files*).
2. Make sure your Space **SDK** is `gradio`, and **App file** is `app.py` (Settings → Runtime).
3. Click **Factory Rebuild** (top right) and then the **App** tab.

If you want a PNG preview, add a `packages.txt` later with Cairo libs and switch to a PNG-generating version.
