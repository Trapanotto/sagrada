import type { Localized } from '../i18n';

export type FloorLevel = 'crypt' | 'ground' | 'gallery' | 'towers';

export interface TeleportPreset {
  id: string;
  label: Localized;
  shortLabel: Localized;
  level: FloorLevel;
  position: [number, number, number];
  lookAt: [number, number, number];
  flyMode?: boolean;
}

export const TELEPORT_PRESETS: TeleportPreset[] = [
  {
    id: 'placa-gaudi',
    label: { de: 'Plaça de Gaudí (Teich & Geburtsfassade)', en: 'Plaça de Gaudí (pond & Nativity façade)' },
    shortLabel: { de: 'Geburtsfassade', en: 'Nativity' },
    level: 'ground',
    position: [103.5, 2.35, 5.5],
    lookAt: [31, 29, 0],
    flyMode: false,
  },
  {
    id: 'main-nave',
    label: { de: 'Hauptschiff — Säulenwald', en: 'Nave — forest of columns' },
    shortLabel: { de: 'Hauptschiff', en: 'Nave' },
    level: 'ground',
    position: [0, 2.95, 34],
    lookAt: [0, 21, -14],
    flyMode: false,
  },
  {
    id: 'crossing-altar',
    label: { de: 'Vierung & Hochaltar', en: 'Crossing & high altar' },
    shortLabel: { de: 'Vierung/Altar', en: 'Crossing/Altar' },
    level: 'ground',
    position: [0, 2.95, 6],
    lookAt: [0, 14, -22],
    flyMode: false,
  },
  {
    id: 'gallery-east',
    label: { de: 'Empore (Cantoria 14,5 m)', en: 'Choir gallery (Cantoria, 14.5 m)' },
    shortLabel: { de: 'Empore', en: 'Gallery' },
    level: 'gallery',
    position: [19.2, 16.25, 28],
    lookAt: [-4, 18, -8],
    flyMode: false,
  },
  {
    id: 'crypt-gaudi',
    label: { de: 'Krypta & Gaudís Grab', en: "Crypt & Gaudí's tomb" },
    shortLabel: { de: 'Krypta', en: 'Crypt' },
    level: 'crypt',
    position: [0, -3.75, -14.5],
    lookAt: [-8.5, -4.5, -23.5],
    flyMode: false,
  },
  {
    id: 'cloister-east',
    label: { de: 'Kreuzgang & Sakristei', en: 'Cloister & sacristy' },
    shortLabel: { de: 'Kreuzgang', en: 'Cloister' },
    level: 'ground',
    position: [26.2, 2.95, 36],
    lookAt: [26.2, 5.2, 14],
    flyMode: false,
  },
  {
    id: 'passion-facade',
    label: { de: 'Passionsfassade (West)', en: 'Passion façade (west)' },
    shortLabel: { de: 'Passionsfassade', en: 'Passion' },
    level: 'ground',
    position: [-58, 1.75, 5],
    lookAt: [-31, 24, 0],
    flyMode: false,
  },
  {
    id: 'glory-facade',
    label: { de: 'Glorienfassade & Freitreppe (Süd)', en: 'Glory façade & staircase (south)' },
    shortLabel: { de: 'Glorienfassade', en: 'Glory' },
    level: 'ground',
    position: [0, 1.75, 86],
    lookAt: [0, 34, 48],
    flyMode: false,
  },
  {
    id: 'spiral-stair',
    label: { de: 'Gaudí-Wendeltreppe (Ostturm, begehbar)', en: 'Gaudí spiral staircase (east tower, walkable)' },
    shortLabel: { de: 'Ost-Treppe', en: 'East stair' },
    level: 'towers',
    position: [32.88, 34.0, 3.6],
    lookAt: [31.5, 42.0, 3.6],
    flyMode: false,
  },
  {
    id: 'west-spiral-stair',
    label: { de: 'Passions-Wendeltreppe (Westturm, begehbar)', en: 'Passion spiral staircase (west tower, walkable)' },
    shortLabel: { de: 'West-Treppe', en: 'West stair' },
    level: 'towers',
    position: [-30.12, 32.0, 3.6],
    lookAt: [-31.5, 40.0, 3.6],
    flyMode: false,
  },
  {
    id: 'jesus-elevator',
    label: {
      de: 'Glas-Aufzug im Turm Jesu Christi (ab 56 m über Gewölbe)',
      en: 'Glass elevator in the Tower of Jesus Christ (from 56 m, above the vault)',
    },
    shortLabel: { de: 'Aufzug [L]', en: 'Elevator [L]' },
    level: 'towers',
    position: [0.0, 57.75, 4.9],
    lookAt: [0.0, 58.2, 0.0],
    flyMode: false,
  },
  {
    id: 'tower-bridge',
    label: { de: 'Turm-Brücke Ost (65 m)', en: 'East tower bridge (65 m)' },
    shortLabel: { de: 'Turm-Brücke', en: 'Tower bridge' },
    level: 'towers',
    position: [31.5, 66.85, 0.0],
    lookAt: [95, 22, 0],
    flyMode: false,
  },
  {
    id: 'jesus-viewpoint',
    label: { de: 'Jesus-Turm Aussicht (136 m)', en: 'Tower of Jesus viewpoint (136 m)' },
    shortLabel: { de: 'Jesus-Turm', en: 'Jesus tower' },
    level: 'towers',
    position: [3.6, 137.9, -3.6],
    lookAt: [0, 122, -48],
    flyMode: false,
  },
  {
    id: 'aerial-overview',
    label: { de: 'Vogelperspektive (Flug)', en: "Bird's-eye view (flight)" },
    shortLabel: { de: 'Luftbild', en: 'Aerial' },
    level: 'towers',
    position: [172, 114, 152],
    lookAt: [0, 74, -4],
    flyMode: true,
  },
];
