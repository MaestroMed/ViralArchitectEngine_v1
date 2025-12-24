import type { z } from 'zod';
import type {
  ProjectSchema,
  SegmentSchema,
  JobSchema,
  TemplateSchema,
  ProfileSchema,
  TimelineDataSchema,
  ExportPackSchema,
  ViralityScoreSchema,
  CaptionStyleSchema,
  LayoutConfigSchema,
  IngestOptionsSchema,
  AnalyzeOptionsSchema,
  ExportOptionsSchema,
  VariantConfigSchema,
} from './schemas';

// Inferred Types from Zod Schemas
export type Project = z.infer<typeof ProjectSchema>;
export type Segment = z.infer<typeof SegmentSchema>;
export type Job = z.infer<typeof JobSchema>;
export type Template = z.infer<typeof TemplateSchema>;
export type Profile = z.infer<typeof ProfileSchema>;
export type TimelineData = z.infer<typeof TimelineDataSchema>;
export type ExportPack = z.infer<typeof ExportPackSchema>;
export type ViralityScore = z.infer<typeof ViralityScoreSchema>;
export type CaptionStyle = z.infer<typeof CaptionStyleSchema>;
export type LayoutConfig = z.infer<typeof LayoutConfigSchema>;
export type IngestOptions = z.infer<typeof IngestOptionsSchema>;
export type AnalyzeOptions = z.infer<typeof AnalyzeOptionsSchema>;
export type ExportOptions = z.infer<typeof ExportOptionsSchema>;
export type VariantConfig = z.infer<typeof VariantConfigSchema>;

// Utility Types
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type VariantLabel = 'A' | 'B' | 'C';
export type CaptionStyleName = 'forge_minimal' | 'impact_modern' | 'neon_whisper';
export type LayoutType = 'stream_facecam' | 'talk_fullscreen' | 'montage' | 'podcast_irl';
export type Platform = 'tiktok' | 'shorts' | 'reels';

// Timeline Layer Types
export interface TimelineLayer {
  id: string;
  name: string;
  type: 'audio_energy' | 'speech_density' | 'scene_changes' | 'hook_likelihood' | 'chat_spikes';
  data: TimelineDataPoint[];
  color: string;
}

export interface TimelineDataPoint {
  time: number;
  value: number;
  metadata?: Record<string, unknown>;
}

// Segment Marker for Timeline
export interface SegmentMarker {
  id: string;
  segmentId: string;
  startTime: number;
  endTime: number;
  score: number;
  label: string;
}

// Rectangle for layout
export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Word-level timestamp for captions
export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

// Transcript segment
export interface TranscriptSegment {
  id: string;
  start: number;
  end: number;
  text: string;
  words?: WordTimestamp[];
  speaker?: string;
  language?: string;
}

// Audio analysis result
export interface AudioAnalysis {
  rmsEnergy: number[];
  peaks: number[];
  silences: Array<{ start: number; end: number }>;
  laughterPatterns: Array<{ time: number; confidence: number }>;
  speechRate: number[];
}

// Scene detection result
export interface SceneChange {
  time: number;
  confidence: number;
  type: 'cut' | 'fade' | 'dissolve';
}

// Face detection result
export interface FaceDetection {
  rect: Rect;
  confidence: number;
  frameTime: number;
}

// Facecam region (stable across video)
export interface FacecamRegion {
  rect: Rect;
  confidence: number;
  stableFrom: number;
  stableTo: number;
}

// API Response wrapper
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// Paginated response
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

// Job progress update
export interface JobProgress {
  jobId: string;
  status: JobStatus;
  progress: number;
  stage?: string;
  message?: string;
  error?: string;
  result?: unknown;
}

// Export artifact
export interface ExportArtifact {
  id: string;
  projectId: string;
  segmentId: string;
  variant: VariantLabel;
  type: 'video' | 'cover' | 'captions_srt' | 'captions_vtt' | 'metadata' | 'post';
  path: string;
  size: number;
  createdAt: string;
}

// IPC Events (Electron)
export type IpcEvents = {
  // Engine communication
  'engine:start': () => void;
  'engine:stop': () => void;
  'engine:status': () => { running: boolean; port: number };
  
  // File operations
  'file:open': () => string | null;
  'file:save': (path: string, data: string) => boolean;
  'file:select-directory': () => string | null;
  
  // Project operations
  'project:import': (path: string) => Project;
  'project:export': (projectId: string) => void;
  
  // System
  'app:get-version': () => string;
  'app:get-library-path': () => string;
  'app:set-library-path': (path: string) => void;
};









