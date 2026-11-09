import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = await build({
  entryPoints: [
    resolve('tests/payroll-contractor-boundary-4398.ts'),
    resolve('tests/payroll-contractor-records-4354.tsx'),
  ],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  packages: 'external',
  write: false,
  outdir: 'isolated-contractor-4400',
  logLevel: 'silent',
});

function load(filename) {
  const file = compiled.outputFiles.find(
    item => item.path.endsWith(filename)
  );
  assert.ok(file, 'Missing compiled component: ' + filename);

  const result = { exports: {} };
  new Function(
    'require', 'module', 'exports', file.text
  )(require, result, result.exports);

  return result.exports;
}

const boundary = load('payroll-contractor-boundary-4398.js');
const screen = load('payroll-contractor-records-4354.js');

const pythonSource = `
import json
import os
import sys

sys.path.insert(0, os.environ["VERIDIAN_BACKEND_CORE"])

from payroll_contractor_screen_4399 import (
    format_fictional_contractor_screen_4399,
)

source = {
    "view": "fictional_contractor_records_only",
    "backend_access_verified": False,
    "onboarding_authority_granted": False,
    "live_payroll_authorized": False,
    "payment_actions_authorized": False,
    "company_total": "SECRET-DO-NOT-EXPOSE",
    "rows": [
        {
            "reference": "TEST-ENG-01",
            "contractor_id": "TEST-CTR-001",
            "display_name": "Fictional Contractor Alpha",
            "return_of": None,
            "engagement_status": "ENDED",
            "start_date": "2026-01-05",
            "end_date": "2026-06-30",
            "w9": "APPROVED",
            "drivers_license": "APPROVED",
            "agreement": "APPROVED",
            "payment_eligible": False,
        },
        {
            "reference": "TEST-ENG-R01",
            "contractor_id": "TEST-CTR-001",
            "display_name": "Fictional Contractor Alpha",
            "return_of": "TEST-ENG-01",
            "engagement_status": "ACTIVE",
            "start_date": "2026-07-06",
            "end_date": None,
            "w9": "APPROVED",
            "drivers_license": "APPROVED",
            "agreement": "APPROVED",
            "payment_eligible": True,
            "tax_identifier": "SECRET-DO-NOT-EXPOSE",
            "license_image": "SECRET-DO-NOT-EXPOSE",
        },
        {
            "reference": "TEST-ENG-02",
            "contractor_id": "TEST-CTR-002",
            "display_name": "Fictional Contractor Beta",
            "return_of": None,
            "engagement_status": "PENDING",
            "start_date": "2026-10-05",
            "end_date": None,
            "w9": "APPROVED",
            "drivers_license": "PENDING",
            "agreement": "APPROVED",
            "payment_eligible": False,
        },
    ],
}

result = format_fictional_contractor_screen_4399(source)
print(json.dumps(result, separators=(",", ":")))
`;

const processResult = spawnSync(
  process.env.VERIDIAN_PYTHON,
  ['-c', pythonSource],
  {
    encoding: 'utf8',
    env: { ...process.env },
    timeout: 30000,
  }
);

assert.equal(
  processResult.status,
  0,
  'Python contractor formatter failed: ' + processResult.stderr
);

const pythonOutput = JSON.parse(processResult.stdout);
const map = boundary.mapFictionalContractors4398;

function render(data, viewer = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(screen.PayrollContractorRecords4354, {
      report: map(data),
      viewer,
    })
  );
}

test('01 actual Python records render in React', () => {
  const html = render(pythonOutput);
  assert.match(html, /Fictional Contractor Alpha/);
  assert.match(html, /Fictional Contractor Beta/);
  assert.equal(map(pythonOutput).rows.length, 3);
});

test('02 returning engagements and onboarding remain separate', () => {
  const result = map(pythonOutput);

  assert.equal(result.rows[0].engagementStatus, 'ENDED');
  assert.equal(result.rows[0].paymentEligible, false);
  assert.equal(result.rows[1].returnOf, 'TEST-ENG-01');
  assert.equal(result.rows[1].paymentEligible, true);
  assert.equal(result.rows[2].driversLicense, 'PENDING');
  assert.equal(result.rows[2].paymentEligible, false);
});

test('03 unsafe changes fail before React renders', () => {
  const clone = () => structuredClone(pythonOutput);

  const unapproved = clone();
  unapproved.rows[1].drivers_license = 'PENDING';
  assert.throws(() => render(unapproved));

  const badReturn = clone();
  badReturn.rows[1].return_of = 'TEST-ENG-02';
  assert.throws(() => render(badReturn));

  const elevated = clone();
  elevated.backend_access_verified = true;
  assert.throws(() => render(elevated));

  assert.throws(() => render(pythonOutput, 'TECHNICIAN'));
});

test('04 private data and operational capabilities stay excluded', () => {
  const report = map(pythonOutput);
  const html = render(pythonOutput);

  assert.doesNotMatch(JSON.stringify(report), /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /<button/i);
  assert.equal(report.backendAccessVerified, false);
  assert.equal(report.onboardingAuthorityGranted, false);
  assert.equal(report.livePayrollAuthorized, false);
  assert.equal(boundary.contractorBoundaryGrantsLiveAccess4398(), false);
});
