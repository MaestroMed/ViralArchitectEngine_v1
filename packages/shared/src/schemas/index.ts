import { z } from 'zod';

// ============================================
// Core Schemas
// ============================================

export const ProjectSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(255),
  sourcePath: z.string(),
  sourceFilename: z.string(),
  duration: z.number().positive().optional(),
  resolution: z.object({
    width: z.number().int().positive(),
    height: z.number().int().positive(),
  }).optional(),
  fps: z.number().positive().optional(),
  audioTracks: z.number().int().nonnegative().default(1),
  proxyPath: z.string().optional(),
  audioPath: z.string().optional(),
  status: z.enum(['created', 'ingesting', 'ingested', 'analyzing', 'analyzed', 'ready', 'error']),
  errorMessage: z.string().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  profileId: z.string().uuid().optional(),
  metadata: z.record(z.unknown()).optional(),
});

export const ViralityScoreSchema = z.object({
  total: z.number().min(0).max(100),
  hookStrength: z.number().min(0).max(25),
  payoff: z.number().min(0).max(20),
  humourReaction: z.number().min(0).max(15),
  tensionSurprise: z.number().min(0).max(15),
  clarityAutonomy: z.number().min(0).max(15),
  rhythm: z.number().min(0).max(10),
  reasons: z.array(z.string()),
  tags: z.array(z.string()),
});

export const SegmentSchema = z.object({
  id: z.string().uuid(),
  projectId: z.string().uuid(),
  startTime: z.number().nonnegative(),
  endTime: z.number().positive(),
  duration: z.number().positive(),
  topicLabel: z.string().optional(),
  hookText: z.string().optional(),
  score: ViralityScoreSchema,
  transcript: z.string().optional(),
  transcriptSegments: z.array(z.object({
    start: z.number(),
    end: z.number(),
    text: z.string(),
  })).optional(),
  coldOpenRecommended: z.boolean().default(false),
  coldOpenStartTime: z.number().optional(),
  layoutType: z.enum(['stream_facecam', 'talk_fullscreen', 'montage', 'podcast_irl']).optional(),
  facecamRect: z.object({
    x: z.number(),
    y: z.number(),
    width: z.number(),
    height: z.number(),
  }).optional(),
  contentRect: z.object({
    x: z.number(),
    y: z.number(),
    width: z.number(),
    height: z.number(),
  }).optional(),
  variants: z.array(z.object({
    label: z.enum(['A', 'B', 'C']),
    config: z.record(z.unknown()),
    proxyPath: z.string().optional(),
    finalPath: z.string().optional(),
  })).optional(),
  createdAt: z.string().datetime(),
});

export const JobSchema = z.object({
  id: z.string().uuid(),
  projectId: z.string().uuid().optional(),
  type: z.enum(['ingest', 'analyze', 'render_proxy', 'render_final', 'generate_variants', 'export']),
  status: z.enum(['pending', 'running', 'completed', 'failed', 'cancelled']),
  progress: z.number().min(0).max(100),
  stage: z.string().optional(),
  message: z.string().optional(),
  error: z.string().optional(),
  result: z.record(z.unknown()).optional(),
  createdAt: z.string().datetime(),
  startedAt: z.string().datetime().optional(),
  completedAt: z.string().datetime().optional(),
});

export const CaptionStyleSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  fontFamily: z.string().default('Inter'),
  fontSize: z.number().int().min(12).max(120).default(48),
  fontWeight: z.enum(['normal', 'bold', 'black']).default('bold'),
  primaryColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#FFFFFF'),
  outlineColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#000000'),
  outlineWidth: z.number().min(0).max(10).default(3),
  shadowColor: z.string().regex(/^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$/).optional(),
  shadowOffset: z.object({ x: z.number(), y: z.number() }).optional(),
  highlightColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
  highlightStyle: z.enum(['none', 'background', 'underline', 'karaoke']).default('karaoke'),
  alignment: z.enum(['left', 'center', 'right']).default('center'),
  verticalPosition: z.number().min(0).max(100).default(75), // percentage from top
  maxLines: z.number().int().min(1).max(3).default(2),
  wordsPerLine: z.number().int().min(3).max(10).default(6),
  animation: z.enum(['none', 'pop', 'fade', 'slide']).default('pop'),
});

export const LayoutConfigSchema = z.object({
  type: z.enum(['stream_facecam', 'talk_fullscreen', 'montage', 'podcast_irl']),
  facecamPosition: z.enum(['top', 'bottom', 'none']).default('top'),
  facecamRatio: z.number().min(0.2).max(0.6).default(0.4), // ratio of height
  contentFit: z.enum(['cover', 'contain', 'fill']).default('cover'),
  backgroundBlur: z.boolean().default(true),
  backgroundColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#000000'),
  safeMargins: z.object({
    top: z.number().min(0).max(200).default(60),
    bottom: z.number().min(0).max(200).default(100),
    left: z.number().min(0).max(100).default(20),
    right: z.number().min(0).max(100).default(20),
  }),
});

export const TemplateSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  description: z.string().max(500).optional(),
  captionStyle: CaptionStyleSchema.omit({ id: true }),
  layout: LayoutConfigSchema,
  hookCardStyle: z.object({
    enabled: z.boolean().default(true),
    duration: z.number().min(1).max(10).default(3),
    backgroundColor: z.string().regex(/^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$/).default('#000000CC'),
    textColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default('#FFFFFF'),
    fontSize: z.number().int().min(24).max(72).default(42),
    animation: z.enum(['none', 'fade', 'slide', 'zoom']).default('fade'),
  }).optional(),
  brandKit: z.object({
    primaryColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
    secondaryColor: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
    logoPath: z.string().optional(),
    watermarkPath: z.string().optional(),
    watermarkOpacity: z.number().min(0).max(1).default(0.3),
    watermarkPosition: z.enum(['top-left', 'top-right', 'bottom-left', 'bottom-right']).default('bottom-right'),
  }).optional(),
  isDefault: z.boolean().default(false),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const ProfileSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  description: z.string().max(500).optional(),
  customDictionary: z.array(z.string()).default([]),
  preferredCaptionStyle: z.string().uuid().optional(),
  preferredLayout: z.enum(['stream_facecam', 'talk_fullscreen', 'montage', 'podcast_irl']).optional(),
  targetDuration: z.object({
    min: z.number().min(10).max(60).default(15),
    max: z.number().min(30).max(180).default(60),
    optimal: z.number().min(15).max(120).default(30),
  }),
  hookPatterns: z.array(z.string()).optional(),
  contentTags: z.array(z.string()).optional(),
  isDefault: z.boolean().default(false),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

// ============================================
// Timeline Data Schemas
// ============================================

export const TimelineDataPointSchema = z.object({
  time: z.number().nonnegative(),
  value: z.number(),
  metadata: z.record(z.unknown()).optional(),
});

export const TimelineLayerSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(['audio_energy', 'speech_density', 'scene_changes', 'hook_likelihood', 'chat_spikes']),
  data: z.array(TimelineDataPointSchema),
  color: z.string(),
});

export const TimelineDataSchema = z.object({
  projectId: z.string().uuid(),
  duration: z.number().positive(),
  layers: z.array(TimelineLayerSchema),
  segments: z.array(z.object({
    id: z.string().uuid(),
    startTime: z.number(),
    endTime: z.number(),
    score: z.number(),
    label: z.string().optional(),
  })),
  sceneChanges: z.array(z.object({
    time: z.number(),
    confidence: z.number(),
  })).optional(),
});

// ============================================
// Export Schemas
// ============================================

export const ExportPackSchema = z.object({
  id: z.string().uuid(),
  projectId: z.string().uuid(),
  segmentId: z.string().uuid(),
  variant: z.enum(['A', 'B', 'C']),
  videoPath: z.string(),
  coverPath: z.string().optional(),
  captionsSrtPath: z.string().optional(),
  captionsVttPath: z.string().optional(),
  captionsAssPath: z.string().optional(),
  postPath: z.string().optional(),
  metadataPath: z.string().optional(),
  title: z.string().optional(),
  description: z.string().optional(),
  hashtags: z.array(z.string()).optional(),
  createdAt: z.string().datetime(),
});

// ============================================
// API Request/Response Schemas
// ============================================

export const CreateProjectSchema = z.object({
  name: z.string().min(1).max(255),
  sourcePath: z.string(),
  profileId: z.string().uuid().optional(),
});

export const IngestOptionsSchema = z.object({
  createProxy: z.boolean().default(true),
  extractAudio: z.boolean().default(true),
  audioTrack: z.number().int().nonnegative().default(0),
  normalizeAudio: z.boolean().default(true),
});

export const AnalyzeOptionsSchema = z.object({
  transcribe: z.boolean().default(true),
  whisperModel: z.enum(['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3']).default('large-v3'),
  language: z.string().length(2).optional(), // auto-detect if not specified
  detectScenes: z.boolean().default(true),
  analyzeAudio: z.boolean().default(true),
  detectFaces: z.boolean().default(true),
  scoreSegments: z.boolean().default(true),
  customDictionary: z.array(z.string()).optional(),
});

export const VariantConfigSchema = z.object({
  label: z.enum(['A', 'B', 'C']),
  captionStyle: z.string().uuid().optional(),
  layoutOverrides: LayoutConfigSchema.partial().optional(),
  useColdOpen: z.boolean().default(false),
  hookCardEnabled: z.boolean().default(true),
  hookCardText: z.string().optional(),
});

export const ExportOptionsSchema = z.object({
  segmentId: z.string().uuid(),
  variant: z.enum(['A', 'B', 'C']).default('A'),
  templateId: z.string().uuid().optional(),
  platform: z.enum(['tiktok', 'shorts', 'reels']).default('tiktok'),
  resolution: z.object({
    width: z.number().int().positive().default(1080),
    height: z.number().int().positive().default(1920),
  }).optional(),
  fps: z.number().int().min(24).max(60).default(30),
  includeCaptions: z.boolean().default(true),
  includeCover: z.boolean().default(true),
  includeMetadata: z.boolean().default(true),
  includePost: z.boolean().default(true),
  useNvenc: z.boolean().default(true),
  crf: z.number().int().min(0).max(51).default(23),
  preset: z.enum(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']).default('medium'),
});

// ============================================
// Utility Schemas
// ============================================

export const PaginationSchema = z.object({
  page: z.number().int().min(1).default(1),
  pageSize: z.number().int().min(1).max(100).default(20),
});

export const SortSchema = z.object({
  field: z.string(),
  order: z.enum(['asc', 'desc']).default('desc'),
});

export const FilterSchema = z.object({
  field: z.string(),
  operator: z.enum(['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains', 'in']),
  value: z.unknown(),
});

// Export all schemas
export const Schemas = {
  Project: ProjectSchema,
  Segment: SegmentSchema,
  Job: JobSchema,
  Template: TemplateSchema,
  Profile: ProfileSchema,
  CaptionStyle: CaptionStyleSchema,
  LayoutConfig: LayoutConfigSchema,
  TimelineData: TimelineDataSchema,
  ExportPack: ExportPackSchema,
  ViralityScore: ViralityScoreSchema,
  CreateProject: CreateProjectSchema,
  IngestOptions: IngestOptionsSchema,
  AnalyzeOptions: AnalyzeOptionsSchema,
  VariantConfig: VariantConfigSchema,
  ExportOptions: ExportOptionsSchema,
};









