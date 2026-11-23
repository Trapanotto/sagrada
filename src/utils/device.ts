/**
 * Reliable Mobile & Touch capability detection for AAA adaptive performance & touch ergonomics.
 */
export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0 ||
    window.matchMedia('(pointer: coarse)').matches
  );
}

/**
 * True when the on-screen touch UI (thumbstick, action buttons) should be shown up front:
 * the primary pointer is coarse, or the device has touch and no fine pointer at all.
 * Narrow desktop windows with a mouse return false (window width is irrelevant here).
 * Touch laptops with a mouse return false; their touch UI appears on the first real touch.
 */
export function prefersTouchUI(): boolean {
  if (typeof window === 'undefined') return false;
  const mm = (q: string) => (typeof window.matchMedia === 'function' ? window.matchMedia(q).matches : false);
  if (mm('(pointer: coarse)')) return true;
  const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  return hasTouch && !mm('(any-pointer: fine)');
}

export function isMobileDevice(): boolean {
  if (typeof window === 'undefined') return false;
  const uaMobile = /Android|iPhone|iPad|iPod|Mobile|Tablet/i.test(navigator.userAgent);
  const narrowTouch = isTouchDevice() && Math.min(window.innerWidth, window.innerHeight) <= 920;
  return uaMobile || narrowTouch;
}

export function triggerHaptic(ms = 12): void {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
      navigator.vibrate(ms);
    }
  } catch {
    // Ignore on unsupported browsers (iOS Safari)
  }
}
