import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path =>
  readFileSync(new URL(path, import.meta.url), 'utf8');

const html = read('./payroll-workspace-review-4327.html');
const entry = read('./payroll-workspace-review-4327.tsx');
const main = read('../src/main.tsx');
const workspace = read('../src/PayrollWorkspacePreview4325.tsx');
const routes = read('../../backend/config/urls.py');

test('standalone review HTML has an isolated root', () => {
  assert.match(html, /id="payroll-review-root"/);
});

test('review HTML loads only its review entry', () => {
  assert.match(html, /payroll-workspace-review-4327\.tsx/);
  assert.doesNotMatch(html, /\/src\/main\.tsx/);
});

test('entry reuses the approved payroll component', () => {
  assert.match(entry, /PayrollWorkspacePreview4325/);
});

test('all approved payroll roles can be previewed', () => {
  for (const role of [
    'CEO', 'COMPTROLLER', 'SALES_MANAGER',
    'INSTALLATION_MANAGER', 'SALES_ASSOCIATE',
    'TECHNICIAN', 'MARKETING',
    'ACCOUNTS_PAYABLE_ASSOCIATE',
    'DATABASE_ADMINISTRATOR',
  ]) {
    assert.ok(entry.includes("'" + role + "'"), role);
  }
});

test('role selector is explicitly fictional', () => {
  assert.match(entry, /Simulate screen for position/);
  assert.match(entry, /does not sign in as another user/);
  assert.match(workspace, /data-preview-only="true"/);
});

test('review entry contains no payment endpoint or action', () => {
  assert.doesNotMatch(entry, /\bfetch\s*\(/);
  assert.doesNotMatch(entry, /\bapi\s*\(/);
  assert.doesNotMatch(entry, /type="submit"/);
});

test('review is not registered in operational navigation', () => {
  assert.doesNotMatch(main, /PayrollReview4327/);
  assert.doesNotMatch(main, /PayrollWorkspacePreview4325/);
  assert.doesNotMatch(main, /payroll-workspace-review-4327/);
  assert.doesNotMatch(routes, /payroll-workspace-review-4327/);
});

test('review page is marked nonindexable', () => {
  assert.match(html, /noindex, nofollow/);
});