# Basílica de la Sagrada Família — Begehbares 3D-Architekturmodell

Ein vollständiges, interaktives und begehbares 3D-Modell der **Basílica de la Sagrada Família** im Webbrowser – erstellt über eine reproduzierbare **Blender-5.2-Python- & Cycles-GI-Pipeline** (Draco + WebP) kombiniert mit **Three.js + TypeScript + Vite**.

👉 **Live-Demo (GitHub Pages):** https://trapanotto.github.io/sagrada/

🇬🇧 *English version below → [English](#english)*

---

## Highlights & Features

* **Vollständiger Entwurf mit allen 18 Türmen:** Turm Jesu Christi (172,5 m inkl. 17-m-Kreuz & begehbarer Aussichtsgalerie auf 136 m), Marien-Turm (138 m mit leuchtendem 12-zackigem Stern), 4 Evangelisten-Türme (135 m), 12 Apostel-Türme (98,4–120 m) sowie Geburts-, Passions- und geplante Glorienfassade mit großer Freitreppe.
* **Maximale Begehbarkeit:** 5-schiffiges Hauptschiff (doppelt verdrehte Säulen in Porphyr, Basalt, Granit & Sandstein), Hyperboloid-Gewölbe, Emporen (*Cantories*), 7 Apsis-Kapellen, Taufbecken, Gaudí-Ausstellung (*Hängemodell*), begehbare **Gaudí-Turm-Wendeltreppe** (156 Stufen), 65-m-Turmbrücken, umlaufender Kreuzgang, 2 Sakristei-Kuppeln, unterirdische **Krypta (-9 m, über zwei Wendeltreppen erreichbar) mit Gaudís Grab** sowie der umgebende Barcelona-Eixample-Stadtblock inkl. **Plaça de Gaudí mit Echtzeit-Spiegelteich & Springbrunnen**.
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
* **Grafikstufen (Auto / Niedrig / Mittel / Hoch / Ultra):** Auswahlfeld in der oberen Leiste. *Auto* wählt die Stufe anhand von GPU, Arbeitsspeicher, CPU-Kernen und Gerätetyp; eine manuelle Wahl wird im Browser gespeichert. Die meisten Einstellungen greifen sofort, einige erst nach dem Neuladen.
* **Zweisprachig (Deutsch / English):** `DE | EN`-Umschalter in der oberen Leiste und auf dem Ladebildschirm – die gesamte Oberfläche inklusive Hotspot-Texten, Tour-Kapiteln und Bauzeit-Zeitleiste wechselt live, ohne Neuladen. Startsprache: gespeicherte Wahl, sonst Browsersprache; per URL erzwingbar mit `?lang=de` bzw. `?lang=en`.

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
| `L` | Glas-Aufzug im Turm Jesu Christi rufen / fahren |
| `DE` / `EN` (obere Leiste) | Sprache umschalten |

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

---

<a id="english"></a>

## English

**Basílica de la Sagrada Família — a walkable 3D architectural model in the browser.** The complete design of Gaudí's basilica — all 18 towers, the Nativity, Passion and planned Glory façades, the forest of columns, the crypt with Gaudí's tomb and the surrounding Eixample block — built with a reproducible **Blender 5.2 Python & Cycles GI pipeline** (Draco + WebP) and rendered with **Three.js + TypeScript + Vite**.

👉 **Live demo (GitHub Pages):** https://trapanotto.github.io/sagrada/ — append `?lang=en` to open it in English.

**Highlights**

* Walk through the five-aisle nave with its double-twisted columns, hyperboloid vaults, choir galleries (*Cantories*), apse chapels, the crypt (-9 m, reached by two spiral staircases), cloister, sacristy domes and a walkable spiral staircase; ride the glass elevator up the Tower of Jesus Christ.
* Baked Cycles global-illumination lightmaps, a 24-hour Barcelona sun (41.4° N) with projected stained-glass light, weather presets and HDR bloom.
* Construction time-lapse from the crypt (1882) to the completed Glory façade, architectural hotspots with background texts, a four-level interactive plan, a five-chapter cinematic tour, a photo studio with depth of field and PNG export, and procedural spatial audio.
* **Graphics quality tiers (Auto / Low / Medium / High / Ultra)** in the top bar: *Auto* picks a tier from the GPU, memory, CPU cores and device type; a manual choice is remembered. Most settings apply immediately, a few after a reload.
* **Bilingual UI (Deutsch / English):** the `DE | EN` switch in the top bar and on the loading screen changes the entire interface live, without a reload. The start language is your saved choice, otherwise the browser language; `?lang=de` / `?lang=en` forces one.
* Desktop (WASD + mouse / pointer lock, flight mode) and mobile/touch (virtual thumbstick, touch drag).

**Controls**

| Key / input | Action |
| --- | --- |
| `W A S D` / arrow keys / joystick | Move (`Shift` to sprint, `Space` to jump) |
| Mouse drag / double-click / touch drag | Look around (`ESC` releases pointer lock) |
| `F` | Walk ↔ free flight (`Q`/`E` up/down) |
| `B` | Open the *Timeline 1882–2034* tab |
| `G` / `H` / `M` | Geometry overlay / architectural hotspots / plan |
| `T` / `P` / `U` / `O` | Cinematic tour / photo studio / audio / FPS diagnostics |
| `L` | Call / ride the glass elevator in the Tower of Jesus Christ |
| `DE` / `EN` (top bar) | Switch language |

**Local development**

```bash
npm install
npm run dev       # local dev server (Vite)
npm run build     # TypeScript check + production build (dist/)
```

Regenerating the 3D modules is optional and requires Blender 5.2+ (see the German section above for the commands). UI strings live in `src/i18n/` (`de.ts`, `en.ts`); long-form content such as hotspot texts is kept bilingual next to its data in `src/data/`.

**Credits:** photo-scanned materials and PureSky HDRIs by **Poly Haven** (CC0); 3D engine **Three.js** with the Draco WASM decoder.