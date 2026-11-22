import * as THREE from 'three';

export interface ElevatorFloor {
  label: string;
  y: number;
}

export const ELEVATOR_FLOORS: ElevatorFloor[] = [
  { label: 'Turmbasis · Gewölbe-Galerie (56 m)', y: 56.0 },
  { label: 'Aussichtsplattform · Unter dem Kreuz (136 m)', y: 136.0 },
];

/**
 * Authentic Suspended Panoramic Glass & Brushed-Stainless-Steel Elevator inside the hollow stone core
 * of the Tower of Jesus Christ (0, Y, 0).
 * Real-life fidelity: Runs strictly INSIDE the central tower core ABOVE the 60m crossing vault
 * (56m Tower Base Gallery <-> 136m Panoramic Viewpoint below the 17m four-armed Cross),
 * leaving the sacred 60m Nave Crossing below 100% open and unobstructed.
 */
export class JesusElevator {
  public readonly group = new THREE.Group();
  public currentY = 56.0;
  public targetFloorIdx = 0;
  public isMoving = false;
  public lastDeltaY = 0;

  private readonly maxSpeed = 10.0; // m/s smooth panoramic ascent inside tower core
  private currentVel = 0;
  private glowRingMat: THREE.MeshBasicMaterial;

  constructor() {
    this.group.name = 'JesusTower_PanoramaElevator';

    // Authentic minimalist brushed stainless steel + clear panoramic glass (real Tower of Jesus Christ lift design)
    const steelMat = new THREE.MeshStandardMaterial({
      color: '#cfd5dc',
      metalness: 0.88,
      roughness: 0.22,
    });
    const floorMat = new THREE.MeshStandardMaterial({
      color: '#d9d3c8',
      metalness: 0.10,
      roughness: 0.38,
    });
    const glassMat = new THREE.MeshStandardMaterial({
      color: '#e6f4ff',
      metalness: 0.10,
      roughness: 0.05,
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.glowRingMat = new THREE.MeshBasicMaterial({
      color: '#fff4dc',
      transparent: true,
      opacity: 0.85,
    });

    // 1. Circular Stone & Brushed-Steel Cabin Floor Deck (r = 1.92m)
    const floorDisk = new THREE.Mesh(new THREE.CylinderGeometry(1.92, 1.85, 0.22, 24), floorMat);
    floorDisk.position.y = -0.11;
    floorDisk.receiveShadow = true;
    this.group.add(floorDisk);

    const floorRim = new THREE.Mesh(new THREE.TorusGeometry(1.93, 0.055, 10, 28), steelMat);
    floorRim.rotation.x = Math.PI / 2;
    floorRim.position.y = 0.02;
    this.group.add(floorRim);

    // 2. Curved Panoramic Crystal Glass Enclosure (leaves wide doorway open toward South +Z!)
    const glassWall = new THREE.Mesh(
      new THREE.CylinderGeometry(1.88, 1.88, 2.55, 24, 1, true, Math.PI * 0.22, Math.PI * 1.56),
      glassMat
    );
    glassWall.position.y = 1.32;
    this.group.add(glassWall);

    // 3. 4 Slender Brushed-Steel Structural Ribs
    const ribAngles = [Math.PI * 0.22, Math.PI * 0.74, Math.PI * 1.26, Math.PI * 1.78];
    const ribGeo = new THREE.CylinderGeometry(0.038, 0.038, 2.75, 8);
    for (const ang of ribAngles) {
      const rib = new THREE.Mesh(ribGeo, steelMat);
      rib.position.set(Math.sin(ang) * 1.9, 1.38, Math.cos(ang) * 1.9);
      this.group.add(rib);
    }

    // 4. Minimalist Brushed-Steel Handrail inside the glass cabin
    const handrail = new THREE.Mesh(
      new THREE.TorusGeometry(1.76, 0.026, 8, 24, Math.PI * 1.54),
      steelMat
    );
    handrail.rotation.x = Math.PI / 2;
    handrail.rotation.z = -Math.PI * 0.27;
    handrail.position.y = 1.02;
    this.group.add(handrail);

    // 5. Crown Canopy Ring + Suspension Spider & Architectural Warm-White LED Halo
    const roofRing = new THREE.Mesh(new THREE.TorusGeometry(1.91, 0.065, 10, 28), steelMat);
    roofRing.rotation.x = Math.PI / 2;
    roofRing.position.y = 2.72;
    this.group.add(roofRing);

    const roofGlass = new THREE.Mesh(new THREE.CircleGeometry(1.86, 24), glassMat);
    roofGlass.rotation.x = Math.PI / 2;
    roofGlass.position.y = 2.74;
    this.group.add(roofGlass);

    const suspensionHub = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.34, 0.36, 12), steelMat);
    suspensionHub.position.y = 2.94;
    this.group.add(suspensionHub);

    const lightHalo = new THREE.Mesh(new THREE.TorusGeometry(1.52, 0.03, 8, 28), this.glowRingMat);
    lightHalo.rotation.x = Math.PI / 2;
    lightHalo.position.y = 2.66;
    this.group.add(lightHalo);

    this.group.position.set(0, this.currentY, 0);
  }

  public isPlayerInside(pos: THREE.Vector3): boolean {
    if (pos.y < 54.0) return false;
    const r = Math.hypot(pos.x, pos.z);
    const feetY = pos.y - 1.75;
    return r < 2.05 && Math.abs(feetY - this.currentY) < 1.6;
  }

  public getNearestFloorIndex(y: number): number {
    let bestIdx = 0;
    let bestDist = Infinity;
    for (let i = 0; i < ELEVATOR_FLOORS.length; i++) {
      const d = Math.abs(y - ELEVATOR_FLOORS[i].y);
      if (d < bestDist) {
        bestDist = d;
        bestIdx = i;
      }
    }
    return bestIdx;
  }

  /**
   * Triggers elevator movement when user presses [L] near the shaft or inside the cabin.
   */
  public triggerAction(playerPos: THREE.Vector3): string | null {
    const r = Math.hypot(playerPos.x, playerPos.z);
    if (r > 7.5) return null;

    const feetY = playerPos.y - 1.75;
    if (this.isPlayerInside(playerPos)) {
      this.targetFloorIdx = (this.targetFloorIdx + 1) % ELEVATOR_FLOORS.length;
      return `Panorama-Aufzug fährt zu: ${ELEVATOR_FLOORS[this.targetFloorIdx].label}`;
    }

    // Player is on one of the boarding landings — summon the cabin to their floor!
    const nearIdx = this.getNearestFloorIndex(feetY);
    if (Math.abs(feetY - ELEVATOR_FLOORS[nearIdx].y) < 3.5) {
      if (Math.abs(this.currentY - ELEVATOR_FLOORS[nearIdx].y) < 0.8) {
        // Cabin is already here — send it to the next floor
        this.targetFloorIdx = (nearIdx + 1) % ELEVATOR_FLOORS.length;
        return `Panorama-Aufzug fährt zu: ${ELEVATOR_FLOORS[this.targetFloorIdx].label}`;
      }
      this.targetFloorIdx = nearIdx;
      return `Panorama-Aufzug wird gerufen: ${ELEVATOR_FLOORS[nearIdx].label}`;
    }
    return null;
  }

  public getPromptText(playerPos: THREE.Vector3, isMobile = false): string | null {
    const r = Math.hypot(playerPos.x, playerPos.z);
    if (r > 6.8) return null;
    const feetY = playerPos.y - 1.75;

    if (this.isPlayerInside(playerPos)) {
      const nextFloor = ELEVATOR_FLOORS[(this.targetFloorIdx + 1) % ELEVATOR_FLOORS.length];
      if (this.isMoving) {
        return `Panorama-Aufzug (${this.currentY.toFixed(0)} m) → ${ELEVATOR_FLOORS[this.targetFloorIdx].label}`;
      }
      return isMobile
        ? `Aufzug · Tippen → ${nextFloor.label}`
        : `Panorama-Aufzug · <strong>[L]</strong> Fahren zu ${nextFloor.label}`;
    }

    const nearIdx = this.getNearestFloorIndex(feetY);
    if (Math.abs(feetY - ELEVATOR_FLOORS[nearIdx].y) < 3.0) {
      if (Math.abs(this.currentY - ELEVATOR_FLOORS[nearIdx].y) < 0.8) {
        return isMobile
          ? `Glas-Aufzug bereit · Einsteigen &amp; <strong>Aufzug</strong> tippen`
          : `Glas-Aufzug Jesu Christi bereit · Einsteigen &amp; <strong>[L]</strong> drücken`;
      }
      return isMobile
        ? `Aufzug auf ${this.currentY.toFixed(0)} m · Tippen zum Rufen`
        : `Glas-Aufzug auf ${this.currentY.toFixed(0)} m · <strong>[L]</strong> Aufzug rufen`;
    }
    return null;
  }

  public update(dt: number): number {
    const safeDt = Math.min(dt, 0.08);
    const targetY = ELEVATOR_FLOORS[this.targetFloorIdx].y;
    const diff = targetY - this.currentY;
    const prevY = this.currentY;

    if (Math.abs(diff) < 0.025) {
      this.currentY = targetY;
      this.currentVel = 0;
      this.isMoving = false;
    } else {
      this.isMoving = true;
      // Smooth ramp up and soft ease-out arrival within 8m of target floor
      const desiredSpeed = Math.sign(diff) * Math.min(this.maxSpeed, Math.max(1.2, Math.abs(diff) * 1.55));
      this.currentVel = THREE.MathUtils.lerp(this.currentVel, desiredSpeed, Math.min(1, safeDt * 3.8));
      const step = this.currentVel * safeDt;
      if (Math.abs(step) >= Math.abs(diff)) {
        this.currentY = targetY;
        this.currentVel = 0;
        this.isMoving = false;
      } else {
        this.currentY += step;
      }
    }

    this.group.position.y = this.currentY;
    this.glowRingMat.opacity = this.isMoving ? 0.98 : 0.72;
    this.lastDeltaY = this.currentY - prevY;
    return this.lastDeltaY;
  }
}
