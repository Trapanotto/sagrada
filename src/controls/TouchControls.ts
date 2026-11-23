import { prefersTouchUI, triggerHaptic } from '../utils/device';

/**
 * AAA Mobile & Tablet Multi-Touch Controller (Genshin / PUBG Mobile style):
 * - Left-half FLOATING dynamic analog thumbstick (touch anywhere in bottom-left area -> stick spawns under thumb!)
 *   + Automatic Sprint boost when thumbstick is pushed > 88% to the outer rim!
 * - Right-half smooth touch-drag camera look with subtle inertia damping
 * - Two-finger Pinch-to-Zoom camera FOV (40°..78°)
 * - Ergonomic right-thumb action buttons: Jump, Walk/Fly toggle, Fly Up/Down, & contextual Glass Elevator button!
 */
export class TouchControls {
  public moveX = 0;
  public moveY = 0;
  public flyY = 0;
  public isSprinting = false;

  private joyTouchId: number | null = null;
  private lookTouchId: number | null = null;
  private pinchDist: number | null = null;
  private joyOriginX = 0;
  private joyOriginY = 0;
  private lastLookX = 0;
  private lastLookY = 0;
  private lookVelX = 0;
  private lookVelY = 0;
  private readonly maxRadius = 48;
  private touchActive = false;
  private hiddenByApp = false;

  public onLookDelta?: (dx: number, dy: number) => void;
  public onJump?: () => void;
  public onToggleFly?: () => void;
  public onElevator?: () => void;
  public onPinchZoom?: (deltaFov: number) => void;

  private rootEl: HTMLElement;
  private joyRingEl: HTMLElement;
  private knobEl: HTMLElement;
  private sprintRingEl: HTMLElement;
  private flyBtnsEl: HTMLElement;
  private jumpBtnEl: HTMLElement;
  private flyToggleBtnEl: HTMLElement;
  private elevBtnEl: HTMLElement;

  constructor(canvas: HTMLCanvasElement) {
    this.rootEl = document.getElementById('touch-controls')!;
    this.joyRingEl = document.getElementById('touch-joy-ring')!;
    this.knobEl = document.getElementById('touch-joy-knob')!;
    this.sprintRingEl = document.getElementById('touch-sprint-indicator')!;
    this.flyBtnsEl = document.getElementById('touch-fly-btns')!;
    this.jumpBtnEl = document.getElementById('touch-jump-btn')!;
    this.flyToggleBtnEl = document.getElementById('touch-fly-toggle')!;
    this.elevBtnEl = document.getElementById('touch-elevator-btn')!;

    // Touch UI only for real touch / coarse-pointer devices (never for a narrow desktop window with a mouse)
    this.touchActive = prefersTouchUI();
    if (this.touchActive) {
      this.rootEl.classList.remove('hidden');
    }

    const joyZone = document.getElementById('touch-joy-zone')!;

    // ── 1. Floating Dynamic Left-Thumb Analog Stick ──
    joyZone.addEventListener(
      'touchstart',
      (e) => {
        if (this.joyTouchId !== null) return;
        const t = e.changedTouches[0];
        this.joyTouchId = t.identifier;
        const rect = joyZone.getBoundingClientRect();
        // Spawn joystick ring cleanly centered under the user's thumb (clamped inside touch zone)
        const localX = Math.max(52, Math.min(rect.width - 52, t.clientX - rect.left));
        const localY = Math.max(52, Math.min(rect.height - 52, t.clientY - rect.top));
        this.joyOriginX = rect.left + localX;
        this.joyOriginY = rect.top + localY;
        this.joyRingEl.style.left = `${localX}px`;
        this.joyRingEl.style.top = `${localY}px`;
        this.joyRingEl.classList.add('active');
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
          this.isSprinting = false;
          this.knobEl.style.transform = 'translate3d(0px, 0px, 0)';
          this.joyRingEl.classList.remove('active');
          this.sprintRingEl.classList.remove('active');
        }
      }
    };
    joyZone.addEventListener('touchend', endJoy);
    joyZone.addEventListener('touchcancel', endJoy);

    // ── 2. Smooth Right-Thumb Camera Look + Two-Finger Pinch-to-Zoom ──
    canvas.addEventListener(
      'touchstart',
      (e) => {
        this.touchActive = true;
        if (!this.hiddenByApp) this.rootEl.classList.remove('hidden'); // Auto-reveal touch controls on first touch!
        if (e.touches.length === 2) {
          // Start two-finger pinch zoom
          this.lookTouchId = null;
          this.lookVelX = 0;
          this.lookVelY = 0;
          this.pinchDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          return;
        }
        if (this.lookTouchId !== null) return;
        const t = e.changedTouches[0];
        if (t.identifier === this.joyTouchId) return;
        this.lookTouchId = t.identifier;
        this.lastLookX = t.clientX;
        this.lastLookY = t.clientY;
        this.lookVelX = 0;
        this.lookVelY = 0;
      },
      { passive: true }
    );

    canvas.addEventListener(
      'touchmove',
      (e) => {
        if (e.touches.length === 2 && this.pinchDist !== null) {
          const nextDist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          const delta = this.pinchDist - nextDist;
          this.pinchDist = nextDist;
          this.onPinchZoom?.(delta * 0.08);
          e.preventDefault();
          return;
        }
        for (const t of Array.from(e.changedTouches)) {
          if (t.identifier === this.lookTouchId) {
            const dx = t.clientX - this.lastLookX;
            const dy = t.clientY - this.lastLookY;
            this.lastLookX = t.clientX;
            this.lastLookY = t.clientY;
            this.lookVelX = dx * 0.55;
            this.lookVelY = dy * 0.55;
            this.onLookDelta?.(dx, dy);
            e.preventDefault();
          }
        }
      },
      { passive: false }
    );

    const endLook = (e: TouchEvent) => {
      if (e.touches.length < 2) {
        this.pinchDist = null;
      }
      for (const t of Array.from(e.changedTouches)) {
        if (t.identifier === this.lookTouchId) {
          this.lookTouchId = null;
        }
      }
    };
    canvas.addEventListener('touchend', endLook);
    canvas.addEventListener('touchcancel', endLook);

    // ── 3. Ergonomic Right-Thumb Action Buttons (Jump, Walk/Fly, Fly Up/Down, Glass Elevator!) ──
    const bindTap = (el: HTMLElement, fn: () => void) => {
      const handler = (e: Event) => {
        e.preventDefault();
        e.stopPropagation();
        triggerHaptic(14);
        el.classList.add('pressed');
        setTimeout(() => el.classList.remove('pressed'), 130);
        fn();
      };
      el.addEventListener('touchstart', handler, { passive: false });
      el.addEventListener('click', handler);
    };

    bindTap(this.jumpBtnEl, () => this.onJump?.());
    bindTap(this.flyToggleBtnEl, () => this.onToggleFly?.());
    bindTap(this.elevBtnEl, () => this.onElevator?.());

    const upBtn = document.getElementById('touch-fly-up')!;
    const downBtn = document.getElementById('touch-fly-down')!;
    const bindHold = (el: HTMLElement, val: number) => {
      el.addEventListener(
        'touchstart',
        (e) => {
          this.flyY = val;
          el.classList.add('pressed');
          triggerHaptic(10);
          e.preventDefault();
        },
        { passive: false }
      );
      const release = () => {
        this.flyY = 0;
        el.classList.remove('pressed');
      };
      el.addEventListener('touchend', release);
      el.addEventListener('touchcancel', release);
    };
    bindHold(upBtn, 1);
    bindHold(downBtn, -1);
  }

  private updateJoy(cx: number, cy: number): void {
    let dx = cx - this.joyOriginX;
    let dy = cy - this.joyOriginY;
    const rawLen = Math.hypot(dx, dy);
    // Subtle deadzone (10%) prevents stick drift
    if (rawLen < this.maxRadius * 0.10) {
      this.moveX = 0;
      this.moveY = 0;
      this.isSprinting = false;
      this.knobEl.style.transform = 'translate3d(0px, 0px, 0)';
      this.sprintRingEl.classList.remove('active');
      return;
    }
    const clampedLen = Math.min(rawLen, this.maxRadius);
    dx = (dx / rawLen) * clampedLen;
    dy = (dy / rawLen) * clampedLen;
    this.knobEl.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
    this.moveX = dx / this.maxRadius;
    this.moveY = -dy / this.maxRadius; // Push up -> move forward (+1)

    // Pushing forward past 88% rim activates smooth Auto-Sprint!
    const nextSprint = rawLen >= this.maxRadius * 0.88 && this.moveY > 0.45;
    if (nextSprint && !this.isSprinting) triggerHaptic(8);
    this.isSprinting = nextSprint;
    this.sprintRingEl.classList.toggle('active', nextSprint);
  }

  /**
   * Call once per frame for buttery camera-look inertia after lifting thumb.
   */
  public updateInertia(dt: number): void {
    if (this.lookTouchId === null && (Math.abs(this.lookVelX) > 0.08 || Math.abs(this.lookVelY) > 0.08)) {
      const damping = Math.exp(-11.0 * Math.min(dt, 0.08));
      this.lookVelX *= damping;
      this.lookVelY *= damping;
      this.onLookDelta?.(this.lookVelX, this.lookVelY);
    }
  }

  public setFlyVisible(flyMode: boolean): void {
    this.flyBtnsEl.classList.toggle('hidden', !flyMode);
    this.jumpBtnEl.classList.toggle('hidden', flyMode);
    this.flyToggleBtnEl.classList.toggle('active', flyMode);
    this.flyToggleBtnEl.textContent = flyMode ? '🚶' : '🕊';
    if (!flyMode) this.flyY = 0;
  }

  public setElevatorAvailable(available: boolean): void {
    this.elevBtnEl.classList.toggle('hidden', !available);
  }

  public setVisible(visible: boolean): void {
    this.hiddenByApp = !visible;
    if (!visible) {
      this.rootEl.classList.add('hidden');
    } else if (this.touchActive) {
      this.rootEl.classList.remove('hidden');
    }
  }

  /** True once the touch UI is (or should be) shown: coarse-pointer device or a real touch happened. */
  public get isTouchActive(): boolean {
    return this.touchActive;
  }
}
