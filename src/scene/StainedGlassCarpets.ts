import * as THREE from 'three';
import { LAYOUT } from '../data/layout';

/** Just above the nave floor, in the bay the stained-glass projectors light (layout eastProjector). */
const CARPET_Y = LAYOUT.levels.nave + 0.045;
const CARPET_Z = -LAYOUT.lights.eastProjector.pos[1];

/**
 * Projected Joan Vila-Grau Stained-Glass Light Carpets dancing across the Nave marble floor (Y = 1.24m).
 * - East Morning Sun: vibrant turquoise, emerald & sapphire light carpets sweeping westward
 * - West Afternoon / Golden Hour Sun: blazing crimson, amber & molten gold light carpets sweeping eastward!
 * Zero extra shadow casters or PointLights — pure feathered additive GLSL projection (2 draw calls!).
 */
export class StainedGlassCarpets {
  public readonly group = new THREE.Group();
  private eastMesh: THREE.Mesh;
  private westMesh: THREE.Mesh;
  private eastUniforms: { uMap: { value: THREE.Texture }; uIntensity: { value: number }; uTint: { value: THREE.Color } };
  private westUniforms: { uMap: { value: THREE.Texture }; uIntensity: { value: number }; uTint: { value: THREE.Color } };

  constructor() {
    this.group.name = 'Nave_StainedGlassCarpets';
    const texLoader = new THREE.TextureLoader();

    const texEast = texLoader.load('./textures/stained_glass_east.webp');
    texEast.colorSpace = THREE.SRGBColorSpace;
    texEast.wrapS = THREE.RepeatWrapping;
    texEast.wrapT = THREE.ClampToEdgeWrapping;

    const texWest = texLoader.load('./textures/stained_glass_west.webp');
    texWest.colorSpace = THREE.SRGBColorSpace;
    texWest.wrapS = THREE.RepeatWrapping;
    texWest.wrapT = THREE.ClampToEdgeWrapping;

    this.eastUniforms = {
      uMap: { value: texEast },
      uIntensity: { value: 0.0 },
      uTint: { value: new THREE.Color('#5be6ff') },
    };
    this.westUniforms = {
      uMap: { value: texWest },
      uIntensity: { value: 0.0 },
      uTint: { value: new THREE.Color('#ff8c38') },
    };

    const makeCarpetMat = (uniforms: typeof this.eastUniforms) =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms,
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform sampler2D uMap;
          uniform float uIntensity;
          uniform vec3 uTint;
          varying vec2 vUv;

          void main() {
            // Repeat 4 tall Gothic nave window bays along the length of the aisle
            vec2 glassUv = vec2(fract(vUv.y * 4.0), vUv.x);
            vec3 glass = texture2D(uMap, glassUv).rgb;

            // Boost chromatic vibrancy & carve crisp window-bay mullion rhythm
            float bayMask = smoothstep(0.02, 0.11, glassUv.x) * smoothstep(0.98, 0.89, glassUv.x);
            float crossMask = smoothstep(0.0, 0.18, vUv.x) * smoothstep(1.0, 0.72, vUv.x);
            float endFade = smoothstep(0.0, 0.08, vUv.y) * smoothstep(1.0, 0.92, vUv.y);
            float mask = bayMask * crossMask * endFade;

            vec3 col = pow(glass, vec3(1.15)) * mix(vec3(1.0), uTint, 0.28);
            gl_FragColor = vec4(col * uIntensity * mask, mask * uIntensity);
          }
        `,
      });

    // Each carpet covers 16m wide x 32m along the 5-aisle Nave floor (Z = +10 .. +42)
    const geo = new THREE.PlaneGeometry(17.0, 32.0);

    this.eastMesh = new THREE.Mesh(geo, makeCarpetMat(this.eastUniforms));
    this.eastMesh.rotation.x = -Math.PI / 2;
    this.eastMesh.position.set(6.5, CARPET_Y, CARPET_Z);
    this.eastMesh.renderOrder = 2;
    this.group.add(this.eastMesh);

    this.westMesh = new THREE.Mesh(geo, makeCarpetMat(this.westUniforms));
    this.westMesh.rotation.x = -Math.PI / 2;
    this.westMesh.position.set(-6.5, CARPET_Y, CARPET_Z);
    this.westMesh.renderOrder = 2;
    this.group.add(this.westMesh);
  }

  public update(eastSunHit: number, westSunHit: number, sunElevationY: number): void {
    // Low golden-hour sun stretches light carpets far into the central nave; high noon pulls them close to walls
    const elev = THREE.MathUtils.clamp(sunElevationY, 0.08, 0.95);
    const reachOffset = THREE.MathUtils.lerp(4.0, 11.2, elev);

    this.eastMesh.position.x = reachOffset;
    this.eastMesh.scale.x = THREE.MathUtils.lerp(1.28, 0.72, elev);
    this.eastUniforms.uIntensity.value = eastSunHit * 0.36;
    this.eastMesh.visible = eastSunHit > 0.025;

    this.westMesh.position.x = -reachOffset;
    this.westMesh.scale.x = THREE.MathUtils.lerp(1.28, 0.72, elev);
    this.westUniforms.uIntensity.value = westSunHit * 0.44;
    this.westMesh.visible = westSunHit > 0.025;
  }
}
