import { z } from 'zod';
import {
  ProjectSchema,
  SegmentSchema,
  JobSchema,
  TemplateSchema,
  ProfileSchema,
  TimelineDataSchema,
  CreateProjectSchema,
  IngestOptionsSchema,
  AnalyzeOptionsSchema,
  ExportOptionsSchema,
  VariantConfigSchema,
  PaginationSchema,
} from './index';

// ============================================
// API Response Wrappers
// ============================================

export const ApiResponseSchema = <T extends z.ZodType>(dataSchema: T) =>
  z.object({
    success: z.boolean(),
    data: dataSchema.optional(),
    error: z.string().optional(),
    message: z.string().optional(),
  });

export const PaginatedResponseSchema = <T extends z.ZodType>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    total: z.number().int().nonnegative(),
    page: z.number().int().positive(),
    pageSize: z.number().int().positive(),
    hasMore: z.boolean(),
  });

// ============================================
// Project Endpoints
// ============================================

// POST /v1/projects
export const CreateProjectRequestSchema = CreateProjectSchema;
export const CreateProjectResponseSchema = ApiResponseSchema(ProjectSchema);

// GET /v1/projects
export const ListProjectsRequestSchema = PaginationSchema.extend({
  search: z.string().optional(),
  status: z.string().optional(),
});
export const ListProjectsResponseSchema = ApiResponseSchema(PaginatedResponseSchema(ProjectSchema));

// GET /v1/projects/:id
export const GetProjectResponseSchema = ApiResponseSchema(ProjectSchema);

// POST /v1/projects/:id/ingest
export const IngestRequestSchema = IngestOptionsSchema;
export const IngestResponseSchema = ApiResponseSchema(z.object({
  jobId: z.string().uuid(),
}));

// POST /v1/projects/:id/analyze
export const AnalyzeRequestSchema = AnalyzeOptionsSchema;
export const AnalyzeResponseSchema = ApiResponseSchema(z.object({
  jobId: z.string().uuid(),
}));

// GET /v1/projects/:id/timeline
export const GetTimelineResponseSchema = ApiResponseSchema(TimelineDataSchema);

// GET /v1/projects/:id/segments
export const ListSegmentsRequestSchema = PaginationSchema.extend({
  sortBy: z.enum(['score', 'startTime', 'duration']).default('score'),
  sortOrder: z.enum(['asc', 'desc']).default('desc'),
  minScore: z.number().min(0).max(100).optional(),
});
export const ListSegmentsResponseSchema = ApiResponseSchema(PaginatedResponseSchema(SegmentSchema));

// GET /v1/projects/:id/segments/:sid
export const GetSegmentResponseSchema = ApiResponseSchema(SegmentSchema);

// POST /v1/projects/:id/segments/:sid/variants
export const GenerateVariantsRequestSchema = z.object({
  variants: z.array(VariantConfigSchema).min(1).max(3),
  renderProxy: z.boolean().default(true),
});
export const GenerateVariantsResponseSchema = ApiResponseSchema(z.object({
  jobId: z.string().uuid(),
}));

// POST /v1/projects/:id/export
export const ExportRequestSchema = ExportOptionsSchema;
export const ExportResponseSchema = ApiResponseSchema(z.object({
  jobId: z.string().uuid(),
}));

// GET /v1/projects/:id/artifacts
export const ListArtifactsResponseSchema = ApiResponseSchema(z.array(z.object({
  id: z.string().uuid(),
  segmentId: z.string().uuid(),
  variant: z.enum(['A', 'B', 'C']),
  type: z.enum(['video', 'cover', 'captions_srt', 'captions_vtt', 'captions_ass', 'metadata', 'post']),
  path: z.string(),
  size: z.number().int().nonnegative(),
  createdAt: z.string().datetime(),
})));

// ============================================
// Job Endpoints
// ============================================

// GET /v1/jobs/:id
export const GetJobResponseSchema = ApiResponseSchema(JobSchema);

// POST /v1/jobs/:id/cancel
export const CancelJobResponseSchema = ApiResponseSchema(z.object({
  cancelled: z.boolean(),
}));

// ============================================
// Template Endpoints
// ============================================

// POST /v1/templates
export const CreateTemplateRequestSchema = TemplateSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export const CreateTemplateResponseSchema = ApiResponseSchema(TemplateSchema);

// GET /v1/templates
export const ListTemplatesResponseSchema = ApiResponseSchema(z.array(TemplateSchema));

// GET /v1/templates/:id
export const GetTemplateResponseSchema = ApiResponseSchema(TemplateSchema);

// PUT /v1/templates/:id
export const UpdateTemplateRequestSchema = CreateTemplateRequestSchema.partial();
export const UpdateTemplateResponseSchema = ApiResponseSchema(TemplateSchema);

// DELETE /v1/templates/:id
export const DeleteTemplateResponseSchema = ApiResponseSchema(z.object({
  deleted: z.boolean(),
}));

// ============================================
// Profile Endpoints
// ============================================

// POST /v1/profiles
export const CreateProfileRequestSchema = ProfileSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export const CreateProfileResponseSchema = ApiResponseSchema(ProfileSchema);

// GET /v1/profiles
export const ListProfilesResponseSchema = ApiResponseSchema(z.array(ProfileSchema));

// GET /v1/profiles/:id
export const GetProfileResponseSchema = ApiResponseSchema(ProfileSchema);

// PUT /v1/profiles/:id
export const UpdateProfileRequestSchema = CreateProfileRequestSchema.partial();
export const UpdateProfileResponseSchema = ApiResponseSchema(ProfileSchema);

// DELETE /v1/profiles/:id
export const DeleteProfileResponseSchema = ApiResponseSchema(z.object({
  deleted: z.boolean(),
}));

// ============================================
// System Endpoints
// ============================================

// GET /health
export const HealthResponseSchema = z.object({
  status: z.enum(['healthy', 'degraded', 'unhealthy']),
  version: z.string(),
  uptime: z.number(),
  services: z.object({
    ffmpeg: z.boolean(),
    whisper: z.boolean(),
    nvenc: z.boolean(),
    database: z.boolean(),
  }),
});

// GET /v1/capabilities
export const CapabilitiesResponseSchema = z.object({
  ffmpeg: z.object({
    version: z.string(),
    hasNvenc: z.boolean(),
    hasLibass: z.boolean(),
    encoders: z.array(z.string()),
  }),
  whisper: z.object({
    available: z.boolean(),
    models: z.array(z.string()),
    currentModel: z.string().optional(),
  }),
  gpu: z.object({
    available: z.boolean(),
    name: z.string().optional(),
    memory: z.number().optional(),
  }),
  storage: z.object({
    libraryPath: z.string(),
    freeSpace: z.number(),
  }),
});









