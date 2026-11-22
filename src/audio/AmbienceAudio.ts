import * as THREE from 'three';

/**
 * Procedural Web Audio API Spatial Ambience Engine:
 * - Indoors: Slowly evolving contemplative cathedral pipe-organ chord progression (D maj -> Bm7 -> G maj7 -> Asus4)
 *   + 4.2s stone hall reverb + subtle distant bronze church bell chime
 * - Outdoors: Gentle Mediterranean breeze, spatial Plaça de Gaudí fountain water trickle, & dynamic rain audio!
 */
export class AmbienceAudio {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private indoorGain: GainNode | null = null;
  private outdoorGain: GainNode | null = null;
  private fountainGain: GainNode | null = null;
  private rainGain: GainNode | null = null;
  private rainFilter: BiquadFilterNode | null = null;
  private reverbNode: ConvolverNode | null = null;
  private organOscs: OscillatorNode[] = [];

  public enabled = false;
  public volume = 0.45;
  private currentIndoor = 0;

  // Contemplative cathedral chord progression (4 voices, transitions smoothly every 12s)
  private readonly chords: number[][] = [
    [73.42, 110.0, 146.83, 185.0], // D major (D2, A2, D3, F#3)
    [61.74, 110.0, 146.83, 185.0], // Bm7 (B1, A2, D3, F#3)
    [98.0, 123.47, 146.83, 185.0], // G maj7 (G2, B2, D3, F#3)
    [110.0, 146.83, 164.81, 220.0], // Asus4 (A2, D3, E3, A3)
  ];
  private chordIndex = 0;
  private chordTimer = 0;
  private bellTimer = 18.0;

  public toggle(): boolean {
    if (!this.enabled) {
      this.start();
    } else {
      this.stop();
    }
    return this.enabled;
  }

  public setVolume(v: number): void {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.masterGain && this.ctx && this.enabled) {
      this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.08);
    }
  }

  private start(): void {
    if (!this.ctx) {
      this.initGraph();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      void this.ctx.resume();
    }
    this.enabled = true;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.25);
    }
  }

  private stop(): void {
    this.enabled = false;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(0.0001, this.ctx.currentTime, 0.2);
    }
  }

  private initGraph(): void {
    const AudioCtx =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtx();
    this.ctx = ctx;

    const master = ctx.createGain();
    master.gain.value = 0.0001;
    master.connect(ctx.destination);
    this.masterGain = master;

    // 1. Procedural 4.4s Cathedral Stone Impulse Response Reverb
    const irLen = Math.floor(ctx.sampleRate * 4.4);
    const irBuf = ctx.createBuffer(2, irLen, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const data = irBuf.getChannelData(ch);
      for (let i = 0; i < irLen; i++) {
        const decay = Math.pow(1 - i / irLen, 3.1);
        data[i] = (Math.random() * 2 - 1) * decay * 0.45;
      }
    }
    const convolver = ctx.createConvolver();
    convolver.buffer = irBuf;
    this.reverbNode = convolver;

    // 2. Indoor Cathedral Pipe Organ Bus
    const indoorBus = ctx.createGain();
    indoorBus.gain.value = 0.0;
    indoorBus.connect(master);
    this.indoorGain = indoorBus;

    const organFilter = ctx.createBiquadFilter();
    organFilter.type = 'lowpass';
    organFilter.frequency.value = 480;
    organFilter.connect(convolver);
    convolver.connect(indoorBus);

    const initFreqs = this.chords[0];
    const gains = [0.055, 0.04, 0.032, 0.02];
    this.organOscs = [];
    initFreqs.forEach((f, idx) => {
      const osc = ctx.createOscillator();
      osc.type = idx === 0 ? 'sine' : 'triangle';
      osc.frequency.value = f;

      const lfo = ctx.createOscillator();
      const lfoGain = ctx.createGain();
      lfo.frequency.value = 0.08 + idx * 0.028;
      lfoGain.gain.value = gains[idx] * 0.32;

      const oscGain = ctx.createGain();
      oscGain.gain.value = gains[idx];
      lfo.connect(lfoGain);
      lfoGain.connect(oscGain.gain);

      osc.connect(oscGain);
      oscGain.connect(organFilter);
      osc.start();
      lfo.start();
      this.organOscs.push(osc);
    });

    // Shared Pink Noise Buffer (used for breeze, spatial fountain water, & rain)
    const noiseLen = ctx.sampleRate * 4;
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const nData = noiseBuf.getChannelData(0);
    let b0 = 0,
      b1 = 0,
      b2 = 0;
    for (let i = 0; i < noiseLen; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.997 * b0 + white * 0.029;
      b1 = 0.985 * b1 + white * 0.032;
      b2 = 0.95 * b2 + white * 0.048;
      nData[i] = (b0 + b1 + b2) * 0.34;
    }

    // 3. Outdoor Barcelona Breeze Bus
    const outdoorBus = ctx.createGain();
    outdoorBus.gain.value = 0.0;
    outdoorBus.connect(master);
    this.outdoorGain = outdoorBus;

    const windSrc = ctx.createBufferSource();
    windSrc.buffer = noiseBuf;
    windSrc.loop = true;

    const windFilter = ctx.createBiquadFilter();
    windFilter.type = 'bandpass';
    windFilter.frequency.value = 340;
    windFilter.Q.value = 0.7;

    const windLfo = ctx.createOscillator();
    const windLfoGain = ctx.createGain();
    windLfo.frequency.value = 0.14;
    windLfoGain.gain.value = 130;
    windLfo.connect(windLfoGain);
    windLfoGain.connect(windFilter.frequency);

    const windGain = ctx.createGain();
    windGain.gain.value = 0.22;

    windSrc.connect(windFilter);
    windFilter.connect(windGain);
    windGain.connect(outdoorBus);
    windSrc.start();
    windLfo.start();

    // 4. Spatial Plaça de Gaudí Fountain Water Trickle (scales smoothly with distance to (82.5, 0))
    const fountainSrc = ctx.createBufferSource();
    fountainSrc.buffer = noiseBuf;
    fountainSrc.loop = true;
    const fountainFilter = ctx.createBiquadFilter();
    fountainFilter.type = 'bandpass';
    fountainFilter.frequency.value = 1450;
    fountainFilter.Q.value = 0.9;
    const fGain = ctx.createGain();
    fGain.gain.value = 0.0;
    fountainSrc.connect(fountainFilter);
    fountainFilter.connect(fGain);
    fGain.connect(master);
    fountainSrc.start();
    this.fountainGain = fGain;

    // 5. Dynamic Rain Ambience (crisp outdoors, warm muffled stone-roof patter indoors!)
    const rainSrc = ctx.createBufferSource();
    rainSrc.buffer = noiseBuf;
    rainSrc.loop = true;
    const rFilter = ctx.createBiquadFilter();
    rFilter.type = 'lowpass';
    rFilter.frequency.value = 2600;
    const rGain = ctx.createGain();
    rGain.gain.value = 0.0;
    rainSrc.connect(rFilter);
    rFilter.connect(rGain);
    rGain.connect(master);
    rainSrc.start();
    this.rainFilter = rFilter;
    this.rainGain = rGain;
  }

  private playDistantBell(): void {
    if (!this.ctx || !this.masterGain || !this.reverbNode || !this.enabled) return;
    const ctx = this.ctx;
    const now = ctx.currentTime;
    // Deep bronze cathedral bell harmonics (D3 fundamental + minor third overtone + fifth)
    const partials = [
      { f: 146.83, g: 0.055, d: 5.2 },
      { f: 293.66, g: 0.032, d: 4.1 },
      { f: 349.23, g: 0.018, d: 3.4 },
      { f: 440.0, g: 0.014, d: 2.6 },
    ];
    for (const p of partials) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = p.f;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.linearRampToValueAtTime(p.g, now + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + p.d);
      osc.connect(gain);
      gain.connect(this.reverbNode);
      gain.connect(this.masterGain);
      osc.start(now);
      osc.stop(now + p.d + 0.1);
    }
  }

  public updateSpatial(dt: number, indoorFactor: number, playerPos: THREE.Vector3, rainFactor: number): void {
    this.currentIndoor = indoorFactor;
    if (!this.ctx || !this.indoorGain || !this.outdoorGain || !this.enabled) return;
    const t = this.ctx.currentTime;

    this.indoorGain.gain.setTargetAtTime(indoorFactor * 0.95, t, 0.35);
    this.outdoorGain.gain.setTargetAtTime((1.0 - indoorFactor * 0.85) * 0.82, t, 0.35);

    // Spatial fountain trickle around Plaça de Gaudí Pond (82.5, 0)
    if (this.fountainGain) {
      const distFountain = Math.hypot(playerPos.x - 82.5, playerPos.z);
      const nearness = Math.max(0, 1.0 - distFountain / 48.0);
      const targetF = nearness * nearness * 0.28 * (1.0 - indoorFactor * 0.9);
      this.fountainGain.gain.setTargetAtTime(targetF, t, 0.25);
    }

    // Dynamic rain audio (bright & crisp outside, softly muffled inside the stone cathedral)
    if (this.rainGain && this.rainFilter) {
      const rainVol = rainFactor * (indoorFactor > 0.5 ? 0.14 : 0.34);
      const rainCutoff = THREE.MathUtils.lerp(2800, 460, indoorFactor);
      this.rainGain.gain.setTargetAtTime(rainVol, t, 0.3);
      this.rainFilter.frequency.setTargetAtTime(rainCutoff, t, 0.3);
    }

    // Slowly evolve cathedral pipe-organ chord every 12 seconds
    this.chordTimer += dt;
    if (this.chordTimer >= 12.0 && this.organOscs.length === 4) {
      this.chordTimer = 0;
      this.chordIndex = (this.chordIndex + 1) % this.chords.length;
      const next = this.chords[this.chordIndex];
      for (let i = 0; i < 4; i++) {
        this.organOscs[i].frequency.setTargetAtTime(next[i], t, 2.2);
      }
    }

    // Periodic gentle distant church bell chime every ~42 seconds
    this.bellTimer -= dt;
    if (this.bellTimer <= 0) {
      this.bellTimer = 42.0 + Math.random() * 18.0;
      this.playDistantBell();
    }
  }

  public playFootstep(): void {
    if (!this.enabled || !this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const now = ctx.currentTime;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(115 + Math.random() * 30, now);
    osc.frequency.exponentialRampToValueAtTime(42, now + 0.06);

    gain.gain.setValueAtTime(0.065, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.075);

    osc.connect(gain);
    gain.connect(this.masterGain);
    if (this.reverbNode && this.currentIndoor > 0.35) {
      const wet = ctx.createGain();
      wet.gain.value = this.currentIndoor * 0.45;
      gain.connect(wet);
      wet.connect(this.reverbNode);
    }

    osc.start(now);
    osc.stop(now + 0.09);
  }
}
