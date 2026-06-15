import { z } from 'zod';

// ============================================
// Mobile (iOS) contract — the morning-workflow surface
// ============================================
//
// Source of truth for the desktop↔backend↔iOS clip contract. These mirror, on
// the TypeScript/zod side:
//   • Python  : ClipQueue.to_dict()         (apps/forge-engine/.../models/review.py)
//   • Swift   : struct Clip                 (apps/ios/ForgeLab/Models/Clip.swift)
//
// The same JSON fixture (contract/mobile-clip.sample.json) is validated against
// all three so any drift breaks a test in CI. Backend payloads are camelCase
// already, so there is zero key remapping here.

export const CLIP_STATUSES = [
  'pending_review',
  'approved',
  'rejected',
  'scheduled',
  'published',
  'failed',
] as const;

export const ClipStatusSchema = z.enum(CLIP_STATUSES);

// The engine serializes naive UTC datetimes via Python's `datetime.isoformat()`,
// e.g. "2026-06-14T08:30:00.123456" — NO trailing "Z" and no offset. zod's
// `.datetime()` rejects that by default, so we match ISO-8601 with an optional
// fractional part and optional timezone. Version-proof across zod minors.
const IsoDateTimeSchema = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/,
    'expected an ISO-8601 datetime',
  );

/** A queued clip, exactly as the engine serializes it for the mobile app. */
export const ClipSchema = z.object({
  id: z.string().min(1),
  projectId: z.string().min(1),
  segmentId: z.string().min(1),
  artifactId: z.string().nullable(),
  title: z.string().nullable(),
  description: z.string().nullable(),
  hashtags: z.array(z.string()),
  videoPath: z.string(),
  coverPath: z.string().nullable(),
  duration: z.number().nonnegative(),
  viralScore: z.number(),
  status: ClipStatusSchema,
  targetPlatform: z.string().nullable(),
  scheduledAt: IsoDateTimeSchema.nullable(),
  publishedAt: IsoDateTimeSchema.nullable(),
  publishedUrl: z.string().nullable(),
  publishError: z.string().nullable(),
  channelName: z.string().nullable(),
  reviewId: z.string().nullable(),
  createdAt: IsoDateTimeSchema,
  updatedAt: IsoDateTimeSchema,
});

/**
 * The subset the iOS `Clip` struct actually decodes. Swift ignores unknown keys
 * and treats absent keys as nil, so this is the minimum the engine must keep
 * emitting for the app to render. Kept as a derived schema so it can never drift
 * from {@link ClipSchema}.
 */
export const ClipMobileViewSchema = ClipSchema.pick({
  id: true,
  projectId: true,
  segmentId: true,
  title: true,
  description: true,
  hashtags: true,
  coverPath: true,
  duration: true,
  viralScore: true,
  status: true,
  channelName: true,
  createdAt: true,
});

// ── GET /v1/clips/by-date ─────────────────────────────────────────────────
export const ClipsByDateResponseSchema = z.object({
  date: z.string(),
  count: z.number().int().nonnegative(),
  items: z.array(ClipSchema),
});

// ── POST /v1/clips/batch-approve ──────────────────────────────────────────
export const BatchApproveRequestSchema = z.object({
  ids: z.array(z.string().min(1)).min(1).max(100),
});

export const BatchApproveResponseSchema = z.object({
  requested: z.number().int().nonnegative(),
  approved: z.number().int().nonnegative(),
  skipped: z.array(z.string()),
});

// ── GET /v1/clips/queue/summary ───────────────────────────────────────────
export const QueueSummaryResponseSchema = z.object({
  counts: z.record(z.string(), z.number().int().nonnegative()),
  total: z.number().int().nonnegative(),
});

// ── GET /health (mobile view — the app only reads status + version) ────────
export const MobileHealthResponseSchema = z.object({
  status: z.string(),
  version: z.string(),
});

/** All mobile schemas, mirroring the `Schemas` registry in ./index. */
export const MobileSchemas = {
  Clip: ClipSchema,
  ClipMobileView: ClipMobileViewSchema,
  ClipsByDateResponse: ClipsByDateResponseSchema,
  BatchApproveRequest: BatchApproveRequestSchema,
  BatchApproveResponse: BatchApproveResponseSchema,
  QueueSummaryResponse: QueueSummaryResponseSchema,
  MobileHealthResponse: MobileHealthResponseSchema,
};
