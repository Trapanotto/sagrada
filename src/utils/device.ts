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
