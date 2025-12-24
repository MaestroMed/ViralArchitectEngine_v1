// API Configuration
export const API_VERSION = 'v1';
export const DEFAULT_ENGINE_PORT = 7860;
export const ENGINE_HOST = 'localhost';

// Video Presets
export const VIDEO_PRESETS = {
  TIKTOK: {
    width: 1080,
    height: 1920,
    fps: 30,
    aspect: '9:16',
    maxDuration: 180,
  },
  SHORTS: {
    width: 1080,
    height: 1920,
    fps: 30,
    aspect: '9:16',
    maxDuration: 60,
  },
  REELS: {
    width: 1080,
    height: 1920,
    fps: 30,
    aspect: '9:16',
    maxDuration: 90,
  },
} as const;

// Proxy Settings
export const PROXY_SETTINGS = {
  width: 1280,
  height: 720,
  crf: 28,
  preset: 'ultrafast',
} as const;

// Audio Settings
export const AUDIO_SETTINGS = {
  sampleRate: 16000,
  channels: 1,
  format: 'wav',
} as const;

// Scoring Weights
export const VIRALITY_WEIGHTS = {
  hookStrength: 25,
  payoff: 20,
  humourReaction: 15,
  tensionSurprise: 15,
  clarityAutonomy: 15,
  rhythm: 10,
} as const;

// Segment Duration Limits
export const SEGMENT_DURATION = {
  min: 15,
  max: 60,
  optimal: 30,
} as const;

// Caption Styles
export const CAPTION_STYLES = {
  FORGE_MINIMAL: 'forge_minimal',
  IMPACT_MODERN: 'impact_modern',
  NEON_WHISPER: 'neon_whisper',
} as const;

// Layout Types
export const LAYOUT_TYPES = {
  STREAM_FACECAM: 'stream_facecam',
  TALK_FULLSCREEN: 'talk_fullscreen',
  MONTAGE: 'montage',
  PODCAST_IRL: 'podcast_irl',
} as const;

// Job Status
export const JOB_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

// Variant Labels
export const VARIANT_LABELS = ['A', 'B', 'C'] as const;









