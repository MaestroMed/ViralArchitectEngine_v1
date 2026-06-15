// Cross-language contract check (TypeScript/zod side).
//
// Validates the committed fixture (mobile-clip.sample.json, generated from the
// real Python ClipQueue.to_dict()) against the zod schemas exported by
// @forge-lab/shared. If the backend payload shape and the shared schema ever
// drift apart, this exits non-zero and fails CI.
//
// Deliberately framework-free (no vitest/jest) so it adds no dependency: it
// imports the built dist and runs plain assertions. `pnpm test` builds first.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
  ClipSchema,
  ClipMobileViewSchema,
  ClipsByDateResponseSchema,
  BatchApproveRequestSchema,
  BatchApproveResponseSchema,
  QueueSummaryResponseSchema,
  MobileHealthResponseSchema,
} from '../dist/index.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(join(here, 'mobile-clip.sample.json'), 'utf-8'),
);

let failures = 0;
const pass = (name) => console.log(`  ✓ ${name}`);
const fail = (name, err) => {
  failures += 1;
  console.error(`  ✗ ${name}`);
  if (err) console.error(String(err).split('\n').slice(0, 8).join('\n'));
};

function expectValid(name, schema, value) {
  const result = schema.safeParse(value);
  if (result.success) pass(name);
  else fail(name, JSON.stringify(result.error.issues, null, 2));
}

function expectInvalid(name, schema, value) {
  const result = schema.safeParse(value);
  if (!result.success) pass(name);
  else fail(name, 'expected validation to fail but it passed');
}

console.log('Mobile contract — fixture vs @forge-lab/shared zod schemas');

// Positive: the real backend payload must satisfy every schema.
expectValid('ClipSchema parses backend clip', ClipSchema, fixture.clip);
expectValid(
  'ClipMobileViewSchema parses backend clip',
  ClipMobileViewSchema,
  fixture.clip,
);
expectValid(
  'ClipsByDateResponseSchema',
  ClipsByDateResponseSchema,
  fixture.clipsByDateResponse,
);
expectValid(
  'BatchApproveRequestSchema',
  BatchApproveRequestSchema,
  fixture.batchApproveRequest,
);
expectValid(
  'BatchApproveResponseSchema',
  BatchApproveResponseSchema,
  fixture.batchApproveResponse,
);
expectValid(
  'QueueSummaryResponseSchema',
  QueueSummaryResponseSchema,
  fixture.queueSummaryResponse,
);
expectValid('MobileHealthResponseSchema', MobileHealthResponseSchema, fixture.health);

// The naive-ISO timestamp (no trailing Z) the backend really emits must pass.
expectValid('naive ISO createdAt accepted', ClipSchema, {
  ...fixture.clip,
  createdAt: '2026-06-14T08:30:00.123456',
});

// Negative: a renamed/removed required key must be rejected (drift guard).
const { id, ...clipWithoutId } = fixture.clip;
expectInvalid('missing required id rejected', ClipSchema, clipWithoutId);
expectInvalid('unknown status rejected', ClipSchema, {
  ...fixture.clip,
  status: 'totally_invalid',
});
expectInvalid('empty ids batch rejected', BatchApproveRequestSchema, { ids: [] });

if (failures > 0) {
  console.error(`\n${failures} contract check(s) failed.`);
  process.exit(1);
}
console.log('\nAll mobile contract checks passed.');
