import test from 'node:test';
import assert from 'node:assert/strict';
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
  outdir: 'isolated-contractor-output',
  logLevel: 'silent',
});

function load(name) {
  const file = compiled.outputFiles.find(
    item => item.path.endsWith(name)
  );
  assert.ok(file, 'Compiled entry missing: ' + name);

  const module = { exports: {} };
  new Function(
    'require', 'module', 'exports', file.text
  )(require, module, module.exports);

  return module.exports;
}

const boundary = load('payroll-contractor-boundary-4398.js');
const component = load('payroll-contractor-records-4354.js');
const map = boundary.mapFictionalContractors4398;

function engagement(overrides = {}) {
  return {
    reference: 'TEST-ENG-01',
    contractor_id: 'TEST-CTR-001',
    display_name: 'Fictional Contractor Alpha',
    return_of: null,
    engagement_status: 'PENDING',
    start_date: '2026-01-05',
    end_date: null,
    w9: 'APPROVED',
    drivers_license: 'PENDING',
    agreement: 'APPROVED',
    payment_eligible: false,
    ...overrides,
  };
}

function fixture() {
  return {
    view: 'fictional_contractor_records_only',
    backend_access_verified: false,
    onboarding_authority_granted: false,
    live_payroll_authorized: false,
    payment_actions_authorized: false,
    rows: [engagement()],
  };
}

function render(data, viewer = 'CEO') {
  return renderToStaticMarkup(
    React.createElement(component.PayrollContractorRecords4354, {
      report: map(data),
      viewer,
    })
  );
}

test('01 fictional onboarding records map and render', () => {
  const report = map(fixture());

  assert.equal(report.rows[0].w9, 'APPROVED');
  assert.equal(report.rows[0].driversLicense, 'PENDING');
  assert.equal(report.rows[0].paymentEligible, false);
  assert.match(render(fixture()), /Fictional Contractor Alpha/);
});

test('02 activation requires all three approved documents', () => {
  const data = fixture();
  data.rows[0].engagement_status = 'ACTIVE';
  data.rows[0].payment_eligible = true;

  assert.throws(() => map(data));

  data.rows[0].drivers_license = 'APPROVED';

  assert.equal(map(data).rows[0].paymentEligible, true);
  assert.match(render(data), /Fictional Contractor Alpha/);
});

test('03 return engagements preserve earlier records', () => {
  const data = fixture();

  data.rows = [
    engagement({
      engagement_status: 'ENDED',
      end_date: '2026-06-30',
      drivers_license: 'APPROVED',
    }),
    engagement({
      reference: 'TEST-ENG-R01',
      return_of: 'TEST-ENG-01',
      start_date: '2026-07-06',
      drivers_license: 'APPROVED',
      engagement_status: 'ACTIVE',
      payment_eligible: true,
    }),
  ];

  const result = map(data);

  assert.equal(result.rows.length, 2);
  assert.equal(result.rows[1].returnOf, 'TEST-ENG-01');

  data.rows[1].start_date = '2026-06-30';
  assert.throws(() => map(data));
});

test('04 invalid returns and unauthorized claims fail closed', () => {
  const data = fixture();
  data.backend_access_verified = true;
  assert.throws(() => map(data));

  const duplicate = fixture();
  duplicate.rows.push(engagement());
  assert.throws(() => map(duplicate));

  const invalid = fixture();
  invalid.rows[0].return_of = 'TEST-MISSING';
  assert.throws(() => map(invalid));

  assert.throws(() => render(fixture(), 'TECHNICIAN'));
});

test('05 private documents and live authority stay excluded', () => {
  const data = fixture();

  data.rows[0].tax_identifier = 'SECRET-DO-NOT-EXPOSE';
  data.rows[0].license_image = 'SECRET-DO-NOT-EXPOSE';
  data.rows[0].bank_account = 'SECRET-DO-NOT-EXPOSE';
  data.company_total = 'SECRET-DO-NOT-EXPOSE';

  const report = map(data);
  const html = render(data);

  assert.doesNotMatch(
    JSON.stringify(report), /SECRET-DO-NOT-EXPOSE/
  );
  assert.doesNotMatch(html, /SECRET-DO-NOT-EXPOSE/);
  assert.doesNotMatch(html, /<button/i);
  assert.equal(report.backendAccessVerified, false);
  assert.equal(report.onboardingAuthorityGranted, false);
  assert.equal(report.livePayrollAuthorized, false);
  assert.equal(
    boundary.contractorBoundaryGrantsLiveAccess4398(), false
  );
});
