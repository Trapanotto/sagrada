import * as THREE from 'three';

export interface ElevatorFloor {
  label: string;
  y: number;
}

export const ELEVATOR_FLOORS: ElevatorFloor[] = [
  { label: 'Vierung (1,2 m)', y: 1.2 },
  { label: 'Gewölbe-Galerie (56 m)', y: 56.0 },
  { label: 'Jesus-Turm Aussicht (136 m)', y: 136.0 },
];

/**
 * Interactive Glass & Gilded-Brass Panoramic Elevator inside the central Tower of Jesus Christ (0, Y, 0).
 * Connects the Nave Crossing (1.2m) <-> Crossing Vault Gallery (56m) <-> Jesus Tower Viewpoint (136m).
 */
export class JesusElevator {
  public readonly group = new THREE.Group();
  public currentY = 1.2;
  public targetFloorIdx = 0;
  public isMoving = false;
  public lastDeltaY = 0;

  private readonly maxSpeed = 10.5; // m/s smooth panoramic ascent
  private currentVel = 0;
  private glowRingMat: THREE.MeshBasicMaterial;

  constructor() {
    this.group.name = 'JesusTower_PanoramaElevator';

    const goldMat = new THREE.MeshStandardMaterial({
      color: '#cfa34e',
      metalness: 0.85,
      roughness: 0.24,
    });
    const floorMat = new THREE.MeshStandardMaterial({
      color: '#dfd5c3',
      metalness: 0.12,
      roughness: 0.35,
    });
    const glassMat = new THREE.MeshStandardMaterial({
      color: '#dff2ff',
      metalness: 0.15,
      roughness: 0.06,
      transparent: true,
      opacity: 0.24,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.glowRingMat = new THREE.MeshBasicMaterial({
      color: '#ffe5a8',
      transparent: true,
      opacity: 0.85,
    });

    // 1. Circular Marble & Brass Cabin Floor Deck (r = 1.92m)
    const floorDisk = new THREE.Mesh(new THREE.CylinderGeometry(1.92, 1.85, 0.22, 24), floorMat);
    floorDisk.position.y = -0.11;
    floorDisk.receiveShadow = true;
    this.group.add(floorDisk);

    const floorRim = new THREE.Mesh(new THREE.TorusGeometry(1.93, 0.065, 10, 28), goldMat);
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

    // 3. 4 Slender Gilded Vertical Structural Ribs
    const ribAngles = [Math.PI * 0.22, Math.PI * 0.74, Math.PI * 1.26, Math.PI * 1.78];
    const ribGeo = new THREE.CylinderGeometry(0.045, 0.045, 2.75, 8);
    for (const ang of ribAngles) {
      const rib = new THREE.Mesh(ribGeo, goldMat);
      rib.position.set(Math.sin(ang) * 1.9, 1.38, Math.cos(ang) * 1.9);
      this.group.add(rib);
    }

    // 4. Gilded Handrail inside the glass cabin
    const handrail = new THREE.Mesh(
      new THREE.TorusGeometry(1.76, 0.032, 8, 24, Math.PI * 1.54),
      goldMat
    );
    handrail.rotation.x = Math.PI / 2;
    handrail.rotation.z = -Math.PI * 0.27;
    handrail.position.y = 1.02;
    this.group.add(handrail);

    // 5. Crown Canopy Ring + Warm Architectural LED Halo (zero dynamic PointLight cost!)
    const roofRing = new THREE.Mesh(new THREE.TorusGeometry(1.91, 0.08, 10, 28), goldMat);
    roofRing.rotation.x = Math.PI / 2;
    roofRing.position.y = 2.72;
    this.group.add(roofRing);

    const roofGlass = new THREE.Mesh(new THREE.CircleGeometry(1.86, 24), glassMat);
    roofGlass.rotation.x = Math.PI / 2;
    roofGlass.position.y = 2.74;
    this.group.add(roofGlass);

    const lightHalo = new THREE.Mesh(new THREE.TorusGeometry(1.52, 0.035, 8, 28), this.glowRingMat);
    lightHalo.rotation.x = Math.PI / 2;
    lightHalo.position.y = 2.66;
    this.group.add(lightHalo);

    this.group.position.set(0, this.currentY, 0);
  }

  public isPlayerInside(pos: THREE.Vector3): boolean {
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
