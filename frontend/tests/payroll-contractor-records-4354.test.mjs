import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(frontend, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
let vite;
let Review;

before(async () => {
  vite = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  Review = (await vite.ssrLoadModule(
    '/tests/payroll-contractor-records-4354.tsx'
  )).PayrollContractorRecords4354;
  assert.equal(typeof Review, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function fixture() {
  return {
    view: 'fictional_contractor_records_only',
    backendAccessVerified: false,
    onboardingAuthorityGranted: false,
    livePayrollAuthorized: false,
    rows: [{
      reference: 'TEST-CTR-A-01',
      contractorId: 'TEST-CTR-A',
      displayName: 'Fictional Contractor A',
      returnOf: null,
      engagementStatus: 'ENDED',
      startDate: '2026-01-05',
      endDate: '2026-06-30',
      w9: 'APPROVED',
      driversLicense: 'APPROVED',
      agreement: 'APPROVED',
      paymentEligible: false,
    }, {
      reference: 'TEST-CTR-A-R01',
      contractorId: 'TEST-CTR-A',
      displayName: 'Fictional Contractor A',
      returnOf: 'TEST-CTR-A-01',
      engagementStatus: 'ACTIVE',
      startDate: '2026-09-01',
      endDate: null,
      w9: 'APPROVED',
      driversLicense: 'APPROVED',
      agreement: 'APPROVED',
      paymentEligible: true,
    }, {
      reference: 'TEST-CTR-B-01',
      contractorId: 'TEST-CTR-B',
      displayName: 'Fictional Contractor B',
      returnOf: null,
      engagementStatus: 'PENDING',
      startDate: '2026-11-02',
      endDate: null,
      w9: 'APPROVED',
      driversLicense: 'PENDING',
      agreement: 'PENDING',
      paymentEligible: false,
    }],
  };
}

function render(data = fixture(), viewer = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Review, { report: data, viewer })
  );
}

test('contractors and distinct engagements display', () => {
  const html = render();
  assert.match(html, /Fictional Contractor A/);
  assert.match(html, /TEST-CTR-A-01/);
  assert.match(html, /TEST-CTR-A-R01/);
});

test('W-9, driver license and agreement status are separate', () => {
  const html = render();
  assert.match(html, /W-9/);
  assert.match(html, /Driver license/);
  assert.match(html, /Signed agreement/);
});

test('pending onboarding does not imply payment eligibility', () => {
  const html = render();
  assert.match(html, /Pending review/);
  assert.match(html, /Not eligible/);
});

test('approved active fictional engagement displays eligibility', () => {
  const html = render();
  assert.match(html, /Eligible in fictional record/);
});

test('return engagement preserves original historical reference', () => {
  const html = render();
  assert.match(html, /Return after TEST-CTR-A-01/);
  assert.match(html, /2026-06-30/);
});

test('missing onboarding approval rejects active eligibility', () => {
  const data = fixture();
  data.rows[1].agreement = 'PENDING';
  assert.throws(() => render(data));
});

test('ended or pending engagement cannot remain payment eligible', () => {
  const data = fixture();
  data.rows[0].paymentEligible = true;
  assert.throws(() => render(data));
});

test('invalid return linkage fails closed', () => {
  const data = fixture();
  data.rows[1].returnOf = 'TEST-CTR-B-01';
  assert.throws(() => render(data));
});

test('only executive and Comptroller fictional views are allowed', () => {
  assert.match(render(fixture(), 'CEO'), /Contractor/);
  assert.throws(() => render(fixture(), 'SALES_MANAGER'));
  assert.throws(() => render(fixture(), 'TECHNICIAN'));
});

test('claimed backend access or live authority fails closed', () => {
  const data = fixture();
  data.backendAccessVerified = true;
  assert.throws(() => render(data));
  const other = fixture();
  other.livePayrollAuthorized = true;
  assert.throws(() => render(other));
});

test('private fields and source documents do not display', () => {
  const data = fixture();
  data.rows[1].bankAccount = 'SECRET-DO-NOT-DISPLAY';
  data.rows[1].taxIdentifier = 'SECRET-DO-NOT-DISPLAY';
  assert.doesNotMatch(render(data), /SECRET-DO-NOT-DISPLAY/);
});

test('review is unregistered, read-only and separated from compensation', () => {
  const html = render();
  assert.doesNotMatch(html, /<form\b|type="submit"/);
  assert.match(html, /separate Contractor Compensation section/);
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollContractorRecords4354/);
  assert.doesNotMatch(urls, /payroll_contractor_records_4354/);
});