/**
 * Site-scale atmosphere constants shared by LightingSystem and WeatherSystem, derived from the layout
 * so they follow the site size (the true-layout site spans about ±215 m instead of ±130 m).
 */
import { LAYOUT } from '../data/layout';

/**
 * Exponential fog density by day / at night. Unchanged on purpose: the distant city and hills keep their
 * radius (370–560 m), and at the new spawn distance (~120 m to the Nativity façade) this fog costs < 2 %
 * contrast, so the larger plazas need no lighter fog.
 */
export const FOG_DENSITY_DAY = 0.0012;
export const FOG_DENSITY_NIGHT = 0.0019;

/**
 * Half size of the sun's orthographic shadow box around its target (0, 12, 0): reaches the Glory stair foot
 * and the inner halves of both plazas, where the towers' long morning / evening shadows fall.
 */
export const SUN_SHADOW_HALF_EXTENT = Math.ceil(-LAYOUT.glory.stair.y0 * 1.5);

/** Sun light distance from its target is ~185-200 m; the far plane must clear the box diagonal behind it. */
export const SUN_SHADOW_FAR = Math.ceil(200 + SUN_SHADOW_HALF_EXTENT * Math.SQRT2);
