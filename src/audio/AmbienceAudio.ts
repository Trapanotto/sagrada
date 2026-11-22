/**
 * Procedural Web Audio API Spatial Ambience Engine:
 * - Indoors: Contemplative cathedral pipe-organ chordal resonance + 4.2s stone hall reverb
 * - Outdoors: Gentle Mediterranean breeze & distant Barcelona plaza ambience
 * - Smooth real-time crossfade based on player indoor/outdoor position + subtle footsteps
 */
export class AmbienceAudio {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private indoorGain: GainNode | null = null;
  private outdoorGain: GainNode | null = null;
  private reverbNode: ConvolverNode | null = null;

  public enabled = false;
  public volume = 0.45;
  private currentIndoor = 0;

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
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtx();
    this.ctx = ctx;

    const master = ctx.createGain();
    master.gain.value = 0.0001;
    master.connect(ctx.destination);
    this.masterGain = master;

    // 1. Procedural 4.2s Cathedral Impulse Response Reverb
    const irLen = Math.floor(ctx.sampleRate * 4.2);
    const irBuf = ctx.createBuffer(2, irLen, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const data = irBuf.getChannelData(ch);
      for (let i = 0; i < irLen; i++) {
        const decay = Math.pow(1 - i / irLen, 3.2);
        data[i] = (Math.random() * 2 - 1) * decay * 0.45;
      }
    }
    const convolver = ctx.createConvolver();
    convolver.buffer = irBuf;
    this.reverbNode = convolver;

    // 2. Indoor Cathedral Layer (soft D-major pipe organ drone + warm stone room resonance)
    const indoorBus = ctx.createGain();
    indoorBus.gain.value = 0.0;
    indoorBus.connect(master);
    this.indoorGain = indoorBus;

    const organFilter = ctx.createBiquadFilter();
    organFilter.type = 'lowpass';
    organFilter.frequency.value = 460;
    organFilter.connect(convolver);
    convolver.connect(indoorBus);

    // Subtle D2, A2, D3, F#3 pipe organ fifth/major harmonic pad
    const freqs = [73.42, 110.0, 146.83, 185.0];
    const gains = [0.055, 0.042, 0.032, 0.018];
    freqs.forEach((f, idx) => {
      const osc = ctx.createOscillator();
      osc.type = idx === 0 ? 'sine' : 'triangle';
      osc.frequency.value = f;

      // Slow organic cathedral air modulation
      const lfo = ctx.createOscillator();
      const lfoGain = ctx.createGain();
      lfo.frequency.value = 0.09 + idx * 0.03;
      lfoGain.gain.value = gains[idx] * 0.35;

      const oscGain = ctx.createGain();
      oscGain.gain.value = gains[idx];
      lfo.connect(lfoGain);
      lfoGain.connect(oscGain.gain);

      osc.connect(oscGain);
      oscGain.connect(organFilter);
      osc.start();
      lfo.start();
    });

    // 3. Outdoor Barcelona Plaza Layer (filtered pink-noise breeze + warm city distance hum)
    const outdoorBus = ctx.createGain();
    outdoorBus.gain.value = 0.0;
    outdoorBus.connect(master);
    this.outdoorGain = outdoorBus;

    const noiseLen = ctx.sampleRate * 4;
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const nData = noiseBuf.getChannelData(0);
    let b0 = 0, b1 = 0, b2 = 0;
    for (let i = 0; i < noiseLen; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.997 * b0 + white * 0.029;
      b1 = 0.985 * b1 + white * 0.032;
      b2 = 0.950 * b2 + white * 0.048;
      nData[i] = (b0 + b1 + b2) * 0.32;
    }

    const noiseSrc = ctx.createBufferSource();
    noiseSrc.buffer = noiseBuf;
    noiseSrc.loop = true;

    const windFilter = ctx.createBiquadFilter();
    windFilter.type = 'bandpass';
    windFilter.frequency.value = 340;
    windFilter.Q.value = 0.7;

    const windLfo = ctx.createOscillator();
    const windLfoGain = ctx.createGain();
    windLfo.frequency.value = 0.14;
    windLfoGain.gain.value = 140;
    windLfo.connect(windLfoGain);
    windLfoGain.connect(windFilter.frequency);

    const windGain = ctx.createGain();
    windGain.gain.value = 0.24;

    noiseSrc.connect(windFilter);
    windFilter.connect(windGain);
    windGain.connect(outdoorBus);
    noiseSrc.start();
    windLfo.start();
  }

  public updateIndoorBlend(indoorFactor: number): void {
    this.currentIndoor = indoorFactor;
    if (!this.ctx || !this.indoorGain || !this.outdoorGain || !this.enabled) return;
    const t = this.ctx.currentTime;
    this.indoorGain.gain.setTargetAtTime(indoorFactor * 0.95, t, 0.35);
    this.outdoorGain.gain.setTargetAtTime((1.0 - indoorFactor * 0.85) * 0.85, t, 0.35);
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
