import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = path => readFileSync(
  new URL(path, import.meta.url), 'utf8'
);
const component = read('../src/PayrollWorkspacePreview4325.tsx');
const main = read('../src/main.tsx');
const oldPreview = read('../src/PayrollDesignPreview4281.tsx');

test('approved dedicated payroll screen exists', () => {
  assert.match(component, /Payroll &amp; Compensation/);
  assert.match(component, /data-preview-only="true"/);
});

test('all six approved payroll tabs are represented', () => {
  for (const label of [
    'My Payroll',
    'Weekly Payroll',
    'Approvals',
    'Payment History',
    'Contractor Records',
    'Reports',
  ]) {
    assert.ok(component.includes(label), label);
  }
});

test('executive and manager roles are separated', () => {
  assert.match(component, /MANAGEMENT/);
  assert.match(component, /TEAM_MANAGERS/);
  assert.match(component, /SALES_MANAGER/);
  assert.match(component, /INSTALLATION_MANAGER/);
});

test('personal payroll remains available to other roles', () => {
  assert.match(component, /Personal payroll only/);
  assert.match(component, /return \[\s*'My Payroll'/);
});

test('contractor records restricted in preview', () => {
  assert.match(component, /tab !== 'Contractor Records'/);
  assert.match(component, /MANAGEMENT\.includes\(role\)/);
});

test('no live payroll or export action is enabled', () => {
  assert.match(component, /Exports are disabled/);
  assert.doesNotMatch(component, /\bfetch\s*\(/);
  assert.doesNotMatch(component, /\bapi\s*\(/);
  assert.doesNotMatch(component, /window\.open/);
});

test('contractor administration remains separate', () => {
  assert.match(component, /separate Contractor Compensation section/);
});

test('preview remains outside registered application', () => {
  assert.doesNotMatch(main, /PayrollWorkspacePreview4325/);
  assert.doesNotMatch(main, /PayrollDesignPreview4281/);
  assert.match(oldPreview, /FICTIONAL DATA ONLY/);
});