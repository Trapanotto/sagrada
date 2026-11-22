import * as THREE from 'three';
import { CollisionSystem } from '../scene/CollisionSystem';

export interface TeleportTarget {
  position: [number, number, number];
  lookAt: [number, number, number];
  flyMode?: boolean;
}

export class PlayerController {
  public enabled = false;
  public flyMode = false;
  public isPointerLocked = false;
  public isMoving = false;
  public speedMps = 0;

  private keys = new Set<string>();
  private yaw = 0;
  private pitch = 0;
  private velY = 0;
  private onGround = true;
  private coyoteTime = 0;
  private bobPhase = 0;
  private isDragging = false;
  private lastDragX = 0;
  private lastDragY = 0;
  private touchMoveX = 0;
  private touchMoveY = 0;
  private touchFlyY = 0;
  private touchSprint = false;

  // Smooth teleport transition state
  private transition: {
    active: boolean;
    elapsed: number;
    duration: number;
    startPos: THREE.Vector3;
    endPos: THREE.Vector3;
    startYaw: number;
    endYaw: number;
    startPitch: number;
    endPitch: number;
  } = {
    active: false,
    elapsed: 0,
    duration: 0.9,
    startPos: new THREE.Vector3(),
    endPos: new THREE.Vector3(),
    startYaw: 0,
    endYaw: 0,
    startPitch: 0,
    endPitch: 0,
  };

  public onModeChange?: (flyMode: boolean) => void;
  public onStep?: () => void;
  public onPointerLockChange?: (locked: boolean) => void;
  private stepAccum = 0;

  constructor(
    public readonly camera: THREE.PerspectiveCamera,
    private domElement: HTMLElement,
    private collision: CollisionSystem
  ) {
    this.camera.rotation.order = 'YXZ';
    this.bindEvents();
  }

  private bindEvents(): void {
    window.addEventListener('keydown', (e) => {
      if (!this.enabled) return;
      const isTextInput =
        (e.target instanceof HTMLInputElement && e.target.type !== 'range' && e.target.type !== 'button') ||
        e.target instanceof HTMLTextAreaElement;
      if (isTextInput) return;

      const isNavKey =
        e.code === 'ArrowUp' ||
        e.code === 'ArrowDown' ||
        e.code === 'ArrowLeft' ||
        e.code === 'ArrowRight' ||
        e.code === 'Space' ||
        e.code === 'PageUp' ||
        e.code === 'PageDown';

      // If a range slider or HUD button still had focus, release focus on movement keys so arrows/Space always move the player
      if (isNavKey) {
        if (document.activeElement instanceof HTMLElement && document.activeElement !== document.body) {
          document.activeElement.blur();
        }
        e.preventDefault();
      }

      this.keys.add(e.code);
      if (e.code === 'KeyF') {
        this.setFlyMode(!this.flyMode);
      } else if (e.code === 'Space' && !this.flyMode && (this.onGround || this.coyoteTime > 0)) {
        // Crisp 1.65m jump impulse — effortlessly clears 1.15m stone balustrades & railings to leap down!
        this.velY = 7.6;
        this.onGround = false;
        this.coyoteTime = 0;
      }
    });

    window.addEventListener('keyup', (e) => {
      this.keys.delete(e.code);
    });

    window.addEventListener('blur', () => {
      this.keys.clear();
    });

    // True Ego-Shooter FPS control: single left-click on canvas immediately locks mouse pointer!
    this.domElement.addEventListener('mousedown', (e) => {
      if (!this.enabled || e.button !== 0) return;
      if (!this.isPointerLocked) {
        if (this.domElement.requestPointerLock) {
          try {
            const p = this.domElement.requestPointerLock() as unknown as Promise<void> | undefined;
            if (p && typeof p.catch === 'function') {
              p.catch(() => {
                // Graceful fallback if pointer lock is restricted
                this.isDragging = true;
                this.lastDragX = e.clientX;
                this.lastDragY = e.clientY;
              });
            }
          } catch {
            this.isDragging = true;
            this.lastDragX = e.clientX;
            this.lastDragY = e.clientY;
          }
        } else {
          this.isDragging = true;
          this.lastDragX = e.clientX;
          this.lastDragY = e.clientY;
        }
      }
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (this.transition.active) return;
      if (this.isPointerLocked) {
        this.yaw -= e.movementX * 0.0022;
        this.pitch = THREE.MathUtils.clamp(this.pitch - e.movementY * 0.0022, -Math.PI * 0.48, Math.PI * 0.48);
      } else if (this.isDragging) {
        const dx = e.clientX - this.lastDragX;
        const dy = e.clientY - this.lastDragY;
        this.lastDragX = e.clientX;
        this.lastDragY = e.clientY;
        this.yaw -= dx * 0.0042;
        this.pitch = THREE.MathUtils.clamp(this.pitch - dy * 0.0042, -Math.PI * 0.48, Math.PI * 0.48);
      }
    });

    document.addEventListener('pointerlockchange', () => {
      this.isPointerLocked = document.pointerLockElement === this.domElement;
      if (this.isPointerLocked) this.isDragging = false;
      this.onPointerLockChange?.(this.isPointerLocked);
    });
  }

  public requestPointerLock(): void {
    if (this.domElement.requestPointerLock) {
      try {
        const p = this.domElement.requestPointerLock() as unknown as Promise<void> | undefined;
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch {
        // Ignore if blocked by browser
      }
    }
  }

  public setFlyMode(enabled: boolean): void {
    this.flyMode = enabled;
    this.velY = 0;
    this.onModeChange?.(enabled);
  }

  public getYaw(): number {
    return this.yaw;
  }

  public setTouchInput(moveX: number, moveY: number, flyY = 0, sprint = false): void {
    this.touchMoveX = moveX;
    this.touchMoveY = moveY;
    this.touchFlyY = flyY;
    this.touchSprint = sprint;
  }

  public triggerJump(): void {
    if (!this.flyMode && (this.onGround || this.coyoteTime > 0)) {
      this.velY = 7.6;
      this.onGround = false;
      this.coyoteTime = 0;
    }
  }

  public applyLookDelta(dx: number, dy: number): void {
    if (this.transition.active) return;
    this.yaw -= dx * 0.0046;
    this.pitch = THREE.MathUtils.clamp(this.pitch - dy * 0.0046, -Math.PI * 0.48, Math.PI * 0.48);
  }

  public syncFromCamera(): void {
    const euler = new THREE.Euler().setFromQuaternion(this.camera.quaternion, 'YXZ');
    this.yaw = euler.y;
    this.pitch = THREE.MathUtils.clamp(euler.x, -Math.PI * 0.48, Math.PI * 0.48);
    this.velY = 0;
  }

  public teleportTo(target: TeleportTarget, instant = false): void {
    const endPos = new THREE.Vector3(...target.position);
    const lookTarget = new THREE.Vector3(...target.lookAt);
    const dir = lookTarget.clone().sub(endPos).normalize();

    const endYaw = Math.atan2(-dir.x, -dir.z);
    const endPitch = Math.asin(THREE.MathUtils.clamp(dir.y, -0.98, 0.98));

    if (target.flyMode !== undefined) {
      this.setFlyMode(target.flyMode);
    }

    if (instant) {
      this.camera.position.copy(endPos);
      this.yaw = endYaw;
      this.pitch = endPitch;
      this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
      this.transition.active = false;
      return;
    }

    // Shortest angle delta for yaw
    let deltaYaw = endYaw - this.yaw;
    while (deltaYaw > Math.PI) deltaYaw -= Math.PI * 2;
    while (deltaYaw < -Math.PI) deltaYaw += Math.PI * 2;

    this.transition.active = true;
    this.transition.elapsed = 0;
    this.transition.duration = 0.85;
    this.transition.startPos.copy(this.camera.position);
    this.transition.endPos.copy(endPos);
    this.transition.startYaw = this.yaw;
    this.transition.endYaw = this.yaw + deltaYaw;
    this.transition.startPitch = this.pitch;
    this.transition.endPitch = endPitch;
    this.velY = 0;
  }

  public update(dt: number): void {
    if (!this.enabled) {
      this.isMoving = false;
      this.speedMps = 0;
      return;
    }
    const safeDt = Math.min(dt, 0.08);

    // Handle smooth teleport animation
    if (this.transition.active) {
      this.transition.elapsed += safeDt;
      const rawT = Math.min(1, this.transition.elapsed / this.transition.duration);
      const t = rawT < 0.5 ? 4 * rawT * rawT * rawT : 1 - Math.pow(-2 * rawT + 2, 3) / 2;

      this.camera.position.lerpVectors(this.transition.startPos, this.transition.endPos, t);
      this.yaw = THREE.MathUtils.lerp(this.transition.startYaw, this.transition.endYaw, t);
      this.pitch = THREE.MathUtils.lerp(this.transition.startPitch, this.transition.endPitch, t);
      this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');

      if (rawT >= 1) {
        this.transition.active = false;
      }
      this.isMoving = false;
      return;
    }

    // Movement vectors
    const forward = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const right = new THREE.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));

    const move = new THREE.Vector3();
    if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) move.add(forward);
    if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) move.sub(forward);
    if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) move.add(right);
    if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) move.sub(right);
    if (Math.abs(this.touchMoveY) > 0.05) move.addScaledVector(forward, this.touchMoveY);
    if (Math.abs(this.touchMoveX) > 0.05) move.addScaledVector(right, this.touchMoveX);

    const sprinting = this.keys.has('ShiftLeft') || this.keys.has('ShiftRight') || this.touchSprint;

    if (this.flyMode) {
      if (this.keys.has('KeyE') || this.keys.has('Space') || this.keys.has('PageUp') || this.touchFlyY > 0.2) move.y += 1;
      if (
        this.keys.has('KeyQ') ||
        this.keys.has('ControlLeft') ||
        this.keys.has('ControlRight') ||
        this.keys.has('PageDown') ||
        this.touchFlyY < -0.2
      ) {
        move.y -= 1;
      }

      const flySpeed = sprinting ? 48.0 : 22.0;
      if (move.lengthSq() > 0) {
        move.normalize().multiplyScalar(flySpeed * safeDt);
        this.camera.position.add(move);
        this.camera.position.y = THREE.MathUtils.clamp(this.camera.position.y, -4.5, 260);
        this.isMoving = true;
        this.speedMps = flySpeed;
      } else {
        this.isMoving = false;
        this.speedMps = 0;
      }
      this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
      return;
    }

    // Walk mode with realistic speed, gravity, smooth stairs & anti-tunneling sub-stepped 3D BVH collision
    const walkSpeed = sprinting ? 11.5 : 5.4;
    let horizDist = 0;
    const currentFeetY = this.camera.position.y - this.collision.eyeHeight;
    let resolved = this.collision.resolveWalkPosition(this.camera.position.x, currentFeetY, this.camera.position.z);

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(walkSpeed * safeDt);
      horizDist = move.length();
      // Sub-step horizontal motion (<= 0.20m per step) so sprinting can never tunnel through walls/pews/railings
      const subSteps = Math.max(1, Math.ceil(horizDist / 0.20));
      const stepX = move.x / subSteps;
      const stepZ = move.z / subSteps;
      let curX = this.camera.position.x;
      let curZ = this.camera.position.z;
      let curFeet = currentFeetY;
      for (let s = 0; s < subSteps; s++) {
        resolved = this.collision.resolveWalkPosition(curX + stepX, curFeet, curZ + stepZ);
        curX = resolved.clampedX;
        curZ = resolved.clampedZ;
        if (this.onGround && resolved.groundY <= curFeet + 1.45) {
          curFeet = resolved.groundY;
        }
      }
      this.camera.position.x = resolved.clampedX;
      this.camera.position.z = resolved.clampedZ;
      this.isMoving = true;
      this.speedMps = walkSpeed;
    } else {
      this.camera.position.x = resolved.clampedX;
      this.camera.position.z = resolved.clampedZ;
      this.isMoving = false;
      this.speedMps = 0;
    }

    // Vertical gravity, leaping off high ledges/parapets, ceiling headroom & smooth stair stepping!
    const targetEyeY = resolved.groundY + this.collision.eyeHeight;
    if (!this.onGround || this.camera.position.y > targetEyeY + 0.55) {
      if (this.onGround) {
        this.onGround = false;
        this.coyoteTime = 0.14;
      } else {
        this.coyoteTime = Math.max(0, this.coyoteTime - safeDt);
      }
      this.velY = Math.max(this.velY - 17.5 * safeDt, -34.0);
      this.camera.position.y += this.velY * safeDt;
      if (this.velY > 0) {
        const ceilY = this.collision.getCeilingY(
          this.camera.position.x,
          this.camera.position.y - this.collision.eyeHeight,
          this.camera.position.z
        );
        if (ceilY !== null && this.camera.position.y > ceilY - 0.18) {
          this.camera.position.y = ceilY - 0.18;
          this.velY = 0;
        }
      }
      if (this.camera.position.y <= targetEyeY) {
        const impactSpeed = Math.abs(this.velY);
        this.camera.position.y = targetEyeY;
        this.velY = 0;
        this.onGround = true;
        this.coyoteTime = 0.14;
        if (impactSpeed > 4.5) {
          this.onStep?.();
        }
      }
    } else {
      this.camera.position.y = THREE.MathUtils.lerp(this.camera.position.y, targetEyeY, Math.min(1, safeDt * 15));
      this.velY = 0;
      this.onGround = true;
      this.coyoteTime = 0.14;
    }

    // Subtle natural walking head-bob + footstep trigger
    let bobOffset = 0;
    if (this.isMoving && this.onGround) {
      this.bobPhase += safeDt * (sprinting ? 13.5 : 8.8);
      bobOffset = Math.sin(this.bobPhase) * 0.042;
      this.stepAccum += horizDist;
      if (this.stepAccum >= (sprinting ? 2.4 : 1.75)) {
        this.stepAccum = 0;
        this.onStep?.();
      }
    }

    this.camera.position.y += bobOffset * 0.35;
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }
}
