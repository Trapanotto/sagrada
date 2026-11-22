export type FloorLevel = 'crypt' | 'ground' | 'gallery' | 'towers';

export interface TeleportPreset {
  id: string;
  label: string;
  shortLabel: string;
  level: FloorLevel;
  position: [number, number, number];
  lookAt: [number, number, number];
  flyMode?: boolean;
}

export const TELEPORT_PRESETS: TeleportPreset[] = [
  {
    id: 'placa-gaudi',
    label: 'Plaça de Gaudí (Teich & Geburtsfassade)',
    shortLabel: 'Geburtsfassade',
    level: 'ground',
    position: [103.5, 2.35, 5.5],
    lookAt: [31, 29, 0],
    flyMode: false,
  },
  {
    id: 'main-nave',
    label: 'Hauptschiff — Säulenwald',
    shortLabel: 'Hauptschiff',
    level: 'ground',
    position: [0, 2.95, 34],
    lookAt: [0, 21, -14],
    flyMode: false,
  },
  {
    id: 'crossing-altar',
    label: 'Vierung & Hochaltar',
    shortLabel: 'Vierung/Altar',
    level: 'ground',
    position: [0, 2.95, 6],
    lookAt: [0, 14, -22],
    flyMode: false,
  },
  {
    id: 'gallery-east',
    label: 'Empore (Cantoria 14,5 m)',
    shortLabel: 'Empore',
    level: 'gallery',
    position: [19.2, 16.25, 28],
    lookAt: [-4, 18, -8],
    flyMode: false,
  },
  {
    id: 'crypt-gaudi',
    label: 'Krypta & Gaudís Grab',
    shortLabel: 'Krypta',
    level: 'crypt',
    position: [0, -3.75, -14.5],
    lookAt: [-8.5, -4.5, -23.5],
    flyMode: false,
  },
  {
    id: 'cloister-east',
    label: 'Kreuzgang & Sakristei',
    shortLabel: 'Kreuzgang',
    level: 'ground',
    position: [26.2, 2.95, 36],
    lookAt: [26.2, 5.2, 14],
    flyMode: false,
  },
  {
    id: 'passion-facade',
    label: 'Passionsfassade (West)',
    shortLabel: 'Passionsfassade',
    level: 'ground',
    position: [-58, 1.75, 5],
    lookAt: [-31, 24, 0],
    flyMode: false,
  },
  {
    id: 'glory-facade',
    label: 'Glorienfassade & Freitreppe (Süd)',
    shortLabel: 'Glorienfassade',
    level: 'ground',
    position: [0, 1.75, 86],
    lookAt: [0, 34, 48],
    flyMode: false,
  },
  {
    id: 'spiral-stair',
    label: 'Gaudí-Wendeltreppe (Ostturm, begehbar)',
    shortLabel: 'Ost-Treppe',
    level: 'towers',
    position: [33.12, 34.0, 3.6],
    lookAt: [31.5, 42.0, 3.6],
    flyMode: false,
  },
  {
    id: 'west-spiral-stair',
    label: 'Passions-Wendeltreppe (Westturm, begehbar)',
    shortLabel: 'West-Treppe',
    level: 'towers',
    position: [-29.85, 32.0, 3.6],
    lookAt: [-31.5, 40.0, 3.6],
    flyMode: false,
  },
  {
    id: 'jesus-elevator',
    label: 'Glas-Panorama-Aufzug (Turm Jesu Christi)',
    shortLabel: 'Aufzug [L]',
    level: 'ground',
    position: [0.0, 2.95, 6.2],
    lookAt: [0.0, 3.35, 0.0],
    flyMode: false,
  },
  {
    id: 'tower-bridge',
    label: 'Turm-Brücke Ost (65 m)',
    shortLabel: 'Turm-Brücke',
    level: 'towers',
    position: [31.5, 66.85, 0.0],
    lookAt: [95, 22, 0],
    flyMode: false,
  },
  {
    id: 'jesus-viewpoint',
    label: 'Jesus-Turm Aussicht (136 m)',
    shortLabel: 'Jesus-Turm',
    level: 'towers',
    position: [3.6, 137.9, -3.6],
    lookAt: [0, 122, -48],
    flyMode: false,
  },
  {
    id: 'aerial-overview',
    label: 'Vogelperspektive (Flug)',
    shortLabel: 'Luftbild',
    level: 'towers',
    position: [172, 114, 152],
    lookAt: [0, 74, -4],
    flyMode: true,
  },
];
