/**
 * Mobile & Tablet Multi-Touch Controls:
 * - Left thumb floating analog virtual joystick (moveX, moveY)
 * - Right-side touch drag for smooth camera yaw/pitch look
 * - Vertical Ascend / Descend touch buttons when in Fly Mode
 */
export class TouchControls {
  public moveX = 0;
  public moveY = 0;
  public flyY = 0;

  private joyTouchId: number | null = null;
  private lookTouchId: number | null = null;
  private joyOriginX = 0;
  private joyOriginY = 0;
  private lastLookX = 0;
  private lastLookY = 0;
  private readonly maxRadius = 46;

  public onLookDelta?: (dx: number, dy: number) => void;

  private rootEl: HTMLElement;
  private knobEl: HTMLElement;
  private flyBtnsEl: HTMLElement;

  constructor(canvas: HTMLCanvasElement) {
    this.rootEl = document.getElementById('touch-controls')!;
    this.knobEl = document.getElementById('touch-joy-knob')!;
    this.flyBtnsEl = document.getElementById('touch-fly-btns')!;

    const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0 || window.innerWidth <= 900;
    if (isTouch) {
      this.rootEl.classList.remove('hidden');
    }

    const joyZone = document.getElementById('touch-joy-zone')!;

    joyZone.addEventListener(
      'touchstart',
      (e) => {
        if (this.joyTouchId !== null) return;
        const t = e.changedTouches[0];
        this.joyTouchId = t.identifier;
        const rect = joyZone.getBoundingClientRect();
        this.joyOriginX = rect.left + rect.width * 0.5;
        this.joyOriginY = rect.top + rect.height * 0.5;
        this.updateJoy(t.clientX, t.clientY);
        e.preventDefault();
      },
      { passive: false }
    );

    joyZone.addEventListener(
      'touchmove',
      (e) => {
        for (const t of Array.from(e.changedTouches)) {
          if (t.identifier === this.joyTouchId) {
            this.updateJoy(t.clientX, t.clientY);
            e.preventDefault();
          }
        }
      },
      { passive: false }
    );

    const endJoy = (e: TouchEvent) => {
      for (const t of Array.from(e.changedTouches)) {
        if (t.identifier === this.joyTouchId) {
          this.joyTouchId = null;
          this.moveX = 0;
          this.moveY = 0;
          this.knobEl.style.transform = 'translate3d(0px, 0px, 0)';
        }
      }
    };
    joyZone.addEventListener('touchend', endJoy);
    joyZone.addEventListener('touchcancel', endJoy);

    // Right-side canvas touch-drag to look around
    canvas.addEventListener(
      'touchstart',
      (e) => {
        if (this.lookTouchId !== null) return;
        const t = e.changedTouches[0];
        this.lookTouchId = t.identifier;
        this.lastLookX = t.clientX;
        this.lastLookY = t.clientY;
        this.rootEl.classList.remove('hidden'); // Reveal touch controls on first real touch!
      },
      { passive: true }
    );

    canvas.addEventListener(
      'touchmove',
      (e) => {
        for (const t of Array.from(e.changedTouches)) {
          if (t.identifier === this.lookTouchId) {
            const dx = t.clientX - this.lastLookX;
            const dy = t.clientY - this.lastLookY;
            this.lastLookX = t.clientX;
            this.lastLookY = t.clientY;
            this.onLookDelta?.(dx, dy);
            e.preventDefault();
          }
        }
      },
      { passive: false }
    );

    const endLook = (e: TouchEvent) => {
      for (const t of Array.from(e.changedTouches)) {
        if (t.identifier === this.lookTouchId) {
          this.lookTouchId = null;
        }
      }
    };
    canvas.addEventListener('touchend', endLook);
    canvas.addEventListener('touchcancel', endLook);

    // Vertical Fly Up / Down buttons
    const upBtn = document.getElementById('touch-fly-up')!;
    const downBtn = document.getElementById('touch-fly-down')!;
    const bindHold = (el: HTMLElement, val: number) => {
      el.addEventListener('touchstart', (e) => { this.flyY = val; e.preventDefault(); }, { passive: false });
      el.addEventListener('touchend', () => { this.flyY = 0; });
      el.addEventListener('touchcancel', () => { this.flyY = 0; });
    };
    bindHold(upBtn, 1);
    bindHold(downBtn, -1);
  }

  private updateJoy(cx: number, cy: number): void {
    let dx = cx - this.joyOriginX;
    let dy = cy - this.joyOriginY;
    const len = Math.hypot(dx, dy);
    if (len > this.maxRadius) {
      dx = (dx / len) * this.maxRadius;
      dy = (dy / len) * this.maxRadius;
    }
    this.knobEl.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
    this.moveX = dx / this.maxRadius;
    this.moveY = -dy / this.maxRadius; // Push up -> move forward (+1)
  }

  public setFlyVisible(flyMode: boolean): void {
    this.flyBtnsEl.classList.toggle('hidden', !flyMode);
    if (!flyMode) this.flyY = 0;
  }

  public setVisible(visible: boolean): void {
    if (!visible) {
      this.rootEl.classList.add('hidden');
    } else if ('ontouchstart' in window || navigator.maxTouchPoints > 0 || window.innerWidth <= 900) {
      this.rootEl.classList.remove('hidden');
    }
  }
}
