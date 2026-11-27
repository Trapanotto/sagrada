/**
 * Frame hooks used only by bench mode (`?bench`, see ./bench.ts). Empty in normal use, so the
 * render loop pays nothing beyond an optional-call check.
 */
export const frameHooks: {
  /** When set, replaces the real rAF delta (seconds) so time-based simulations repeat exactly. */
  fixedDt?: number;
  beforeFrame?: () => void;
  afterFrame?: () => void;
} = {};
