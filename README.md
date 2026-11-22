# Basílica de la Sagrada Família — Begehbares 3D-Architekturmodell

Ein vollständiges, interaktives und begehbares 3D-Modell der **Basílica de la Sagrada Família** im Webbrowser – erstellt über eine reproduzierbare **Blender-5.2-Python- & Cycles-GI-Pipeline** (Draco + WebP) kombiniert mit **Three.js + TypeScript + Vite**.

👉 **Live-Demo (GitHub Pages):** https://trapanotto.github.io/sagrada/

---

## Highlights & Features

* **Vollständiger Entwurf mit allen 18 Türmen:** Turm Jesu Christi (172,5 m inkl. 17-m-Kreuz & begehbarer Aussichtsgalerie auf 136 m), Marien-Turm (138 m mit leuchtendem 12-zackigem Stern), 4 Evangelisten-Türme (135 m), 12 Apostel-Türme (98,4–120 m) sowie Geburts-, Passions- und geplante Glorienfassade mit großer Freitreppe.
* **Maximale Begehbarkeit:** 5-schiffiges Hauptschiff (doppelt verdrehte Säulen in Porphyr, Basalt, Granit & Sandstein), Hyperboloid-Gewölbe, Emporen (*Cantories*), 7 Apsis-Kapellen, Taufbecken, Gaudí-Ausstellung (*Hängemodell*), begehbare **Gaudí-Turm-Wendeltreppe** (156 Stufen), 65-m-Turmbrücken, umlaufender Kreuzgang, 2 Sakristei-Kuppeln, unterirdische **Krypta (-5,5 m) mit Gaudís Grab** sowie der umgebende Barcelona-Eixample-Stadtblock inkl. **Plaça de Gaudí mit Echtzeit-Spiegelteich & Springbrunnen**.
* **AAA-Licht, Cycles-GI & 1K-PureSky-HDRIs:**
  * Gebackene **Blender-Cycles-Global-Illumination-Lightmaps** (`TEXCOORD_1`) für Gewölbe, Boden, Wände & Krypta + raytraced BVH Ambient Occlusion (`COLOR_0`).
  * Dynamischer 24h-Sonnenstand für Barcelona (41,4° N) mit echten **`SpotLight.map`-Buntglas-Projektionen** (kühles Blau/Smaragd im Morgenlicht, warmes Rubin/Gold im Abendrot), weichen GLSL-Sonnenstrahlen, schwebenden Lichtpartikeln, gespiegeltem Marmorboden (`CubeCamera`-Probe) und HDR-Bloom (`AgXToneMapping`).
* **Interaktiver Bauzeit-Zeitraffer (1882 → Final):** Sieh per Regler oder Zeitraffer (`B`) live zu, wie die Kathedrale von der Krypta (1882) über Gaudís Tod (1926), Passionsfassade (1976), Kirchweihe (2010) und Jesus-Turm (2026) bis zur vollendeten Glorienfassade wächst.
* **Architektur- & Erlebnis-Modi:**
  * **`Geometrie [G]`**: Gaudís 7,5-m-Raster, Hyperboloid-Regellinien, Doppel-Helix-Führungen & Kettenlinien-Kraftbögen.
  * **`Plan [M]`**: Interaktiver 4-Ebenen-Grundriss (*Krypta / EG / Empore / Türme*) mit Klick-zum-Teleportieren.
  * **`Tour [T]`**: 5-Kapitel-Cinematic-Kamerafahrt mit Tageszeit-Zeitraffer.
  * **`Foto [P]`**: Pro Foto-Studio mit Brennweite, Tiefenunschärfe (DoF), Belichtung & 1-Klick-PNG-Screenshot.
  * **`Audio [U]`**: Prozedurale Web-Audio-Kirchenakustik mit 4,2-s-Kathedralen-Hall & Außenatmosphäre.
  * **Desktop + Mobile/Touch:** WASD + Maus/Pointer-Lock + Flugmodus (`F`), sowie virtueller Daumen-Joystick & Touch-Drag auf Smartphones/Tablets.

---

## Steuerung

| Taste / Eingabe | Funktion |
| --- | --- |
| `W A S D` / Pfeiltasten / Joystick | Bewegen (`Shift` für Sprint, `Space` Sprung) |
| Maus ziehen / Doppelklick / Touch-Drag | Umschauen (`ESC` löst Pointer Lock) |
| `F` | Gehen ↔ Freier Flugmodus (`Q`/`E` hoch/runter) |
| `B` | Tab *Bauzeit 1882–2034* öffnen |
| `G` / `H` / `M` | Geometrie-Overlay / Architektur-Hotspots / Grundriss |
| `T` / `P` / `U` / `O` | Cinematic Tour / Foto-Studio / Audio / FPS-Diagnose |

---

## Lokale Entwicklung & Asset-Pipeline

```bash
npm install
npm run dev       # Lokaler Entwicklungsserver (Vite)
npm run build     # TypeScript-Check + Produktionsbuild (dist/)
```

Optional zur kompletten Neugenerierung der 3D-Module (benötigt Blender 5.2+):
```bash
python3 scripts/fetch_cc0_assets.py
npm run build:assets
blender --background --python blender/bake_cycles_gi.py
```

### Credits & Lizenzen
* Realistische Stein-, Marmor-, Holz-, Rinden-, Rasen- & Asphalt-Fotoscans sowie PureSky-HDRIs: **Poly Haven** (CC0 Public Domain).
* 3D-Engine: **Three.js** + Draco WASM Decoder.
