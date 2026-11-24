import type { Localized } from '../i18n';
import { LAYOUT, teleportRuntime, type Vec3 } from './layout';
import { settleEyeOnSpiral } from '../scene/walkModel';

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

/**
 * Eye position + look target of a layout teleport (runtime frame). Walk-mode presets that stand inside a
 * spiral stair are settled onto the tread at that azimuth (the layout heights are not tied to the stair phase).
 */
function at(id: string, walk = true): { position: Vec3; lookAt: Vec3 } {
  const { position, lookAt } = teleportRuntime(id);
  if (walk) position[1] = settleEyeOnSpiral(position[0], position[1], position[2]);
  return { position, lookAt };
}

export const TELEPORT_PRESETS: TeleportPreset[] = [
  {
    id: 'placa-gaudi',
    label: { de: 'Plaça de Gaudí (Teich & Geburtsfassade)', en: 'Plaça de Gaudí (pond & Nativity façade)' },
    shortLabel: { de: 'Geburtsfassade', en: 'Nativity' },
    level: 'ground',
    ...at('placa-gaudi'),
    flyMode: false,
  },
  {
    id: 'main-nave',
    label: { de: 'Hauptschiff — Säulenwald', en: 'Nave — forest of columns' },
    shortLabel: { de: 'Hauptschiff', en: 'Nave' },
    level: 'ground',
    ...at('main-nave'),
    flyMode: false,
  },
  {
    id: 'crossing-altar',
    label: { de: 'Vierung & Hochaltar', en: 'Crossing & high altar' },
    shortLabel: { de: 'Vierung/Altar', en: 'Crossing/Altar' },
    level: 'ground',
    ...at('crossing-altar'),
    flyMode: false,
  },
  {
    id: 'gallery-east',
    label: { de: 'Empore (Cantoria 16,2 m)', en: 'Choir gallery (Cantoria, 16.2 m)' },
    shortLabel: { de: 'Empore', en: 'Gallery' },
    level: 'gallery',
    ...at('gallery-east'),
    flyMode: false,
  },
  {
    id: 'crypt-gaudi',
    label: { de: 'Krypta & Gaudís Grab', en: "Crypt & Gaudí's tomb" },
    shortLabel: { de: 'Krypta', en: 'Crypt' },
    level: 'crypt',
    ...at('crypt-gaudi'),
    flyMode: false,
  },
  {
    id: 'cloister-east',
    label: { de: 'Kreuzgang & Sakristei', en: 'Cloister & sacristy' },
    shortLabel: { de: 'Kreuzgang', en: 'Cloister' },
    level: 'ground',
    ...at('cloister-east'),
    flyMode: false,
  },
  {
    id: 'passion-facade',
    label: { de: 'Passionsfassade (West)', en: 'Passion façade (west)' },
    shortLabel: { de: 'Passionsfassade', en: 'Passion' },
    level: 'ground',
    ...at('passion-facade'),
    flyMode: false,
  },
  {
    id: 'glory-facade',
    label: { de: 'Glorienfassade & Freitreppe (Süd)', en: 'Glory façade & staircase (south)' },
    shortLabel: { de: 'Glorienfassade', en: 'Glory' },
    level: 'ground',
    ...at('glory-facade'),
    flyMode: false,
  },
  {
    id: 'spiral-stair',
    label: { de: 'Gaudí-Wendeltreppe (Ostturm, begehbar)', en: 'Gaudí spiral staircase (east tower, walkable)' },
    shortLabel: { de: 'Ost-Treppe', en: 'East stair' },
    level: 'towers',
    ...at('spiral-stair'),
    flyMode: false,
  },
  {
    id: 'west-spiral-stair',
    label: { de: 'Passions-Wendeltreppe (Westturm, begehbar)', en: 'Passion spiral staircase (west tower, walkable)' },
    shortLabel: { de: 'West-Treppe', en: 'West stair' },
    level: 'towers',
    ...at('west-spiral-stair'),
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
    ...at('jesus-elevator'),
    flyMode: false,
  },
  {
    id: 'tower-bridge',
    label: { de: 'Turm-Brücke Ost (65 m)', en: 'East tower bridge (65 m)' },
    shortLabel: { de: 'Turm-Brücke', en: 'Tower bridge' },
    level: 'towers',
    ...at('tower-bridge'),
    flyMode: false,
  },
  {
    id: 'jesus-viewpoint',
    label: { de: 'Jesus-Turm Aussicht (136 m)', en: 'Tower of Jesus viewpoint (136 m)' },
    shortLabel: { de: 'Jesus-Turm', en: 'Jesus tower' },
    level: 'towers',
    ...at('jesus-viewpoint'),
    flyMode: false,
  },
  {
    id: 'aerial-overview',
    label: { de: 'Vogelperspektive (Flug)', en: "Bird's-eye view (flight)" },
    shortLabel: { de: 'Luftbild', en: 'Aerial' },
    level: 'towers',
    ...at('aerial-overview', false),
    flyMode: true,
  },
];

/** Start position (layout `spawn`: east bank of the pond, facing the Nativity façade). */
export const SPAWN_PRESET: TeleportPreset = TELEPORT_PRESETS.find((p) => p.id === LAYOUT.spawn) ?? TELEPORT_PRESETS[0];
