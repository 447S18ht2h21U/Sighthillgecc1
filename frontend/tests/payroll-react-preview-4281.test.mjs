import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = (name) =>
  fs.readFileSync(new URL(name, import.meta.url), 'utf8');

const preview = read('../src/PayrollDesignPreview4281.tsx');
const main = read('../src/main.tsx');
const model = read('./payroll-presentation-model-4280.mjs');

test('all three approved payroll views exist', () => {
  for (const view of [
    'my-compensation',
    'payroll-review',
    'company-summary',
  ]) {
    assert.equal(
      (preview.match(new RegExp('data-view="' + view + '"', 'g')) ?? []).length,
      1,
      'Expected one view: ' + view
    );
  }
});

test('draft preview is not registered in operational navigation', () => {
  assert.doesNotMatch(main, /PayrollDesignPreview4281/);
  assert.doesNotMatch(preview, /\bfetch\s*\(|XMLHttpRequest|WebSocket/);
  assert.doesNotMatch(preview, /<button\b|<form\b|<input\b/);
});

test('view labels preserve payment and reporting distinctions', () => {
  for (const phrase of [
    'FICTIONAL DATA - DESIGN REVIEW ONLY',
    'Approved - Not Yet Paid',
    'Scheduled Wednesday',
    'Actual paid date',
    'CEO and Comptroller only',
    'audit history',
  ]) {
    assert.ok(preview.includes(phrase), 'Missing ' + phrase);
  }
});

test('preview contains no actual financial account information', () => {
  assert.doesNotMatch(
    preview,
    /bank.account|routing.number|social.security|taxpayer.identification/i
  );
  assert.match(preview, /DEMO-001/);
  assert.match(preview, /Fictional Contractor/);
});

test('presentation model remains separate from privileged APIs', () => {
  assert.match(model, /NOT a permission service/);
  assert.doesNotMatch(preview, /from ['"].*api|\/api\//);
});