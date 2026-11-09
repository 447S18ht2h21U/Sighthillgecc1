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

let server;
let Workspace;
let Records;

before(async () => {
  server = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: {
      noDiscovery: true,
      entries: [],
      include: [],
    },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  Workspace = (await server.ssrLoadModule(
    '/tests/payroll-workspace-contractors-4355.tsx'
  )).PayrollWorkspaceContractors4355;

  Records = (await server.ssrLoadModule(
    '/tests/payroll-contractor-records-4354.tsx'
  )).PayrollContractorRecords4354;

  assert.equal(typeof Workspace, 'function');
  assert.equal(typeof Records, 'function');
});

after(async () => {
  if (server) await server.close();
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

function page(role = 'COMPTROLLER', contractorReport = fixture()) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role, contractorReport })
  );
}

function recordsPage(data = fixture(), viewer = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Records, { report: data, viewer })
  );
}

test('original My Payroll remains the initial tab', () => {
  assert.match(page(), /aria-label="My Payroll"/);
});

test('Comptroller retains the six approved tabs', () => {
  const html = page();
  for (const tab of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) assert.ok(html.includes(tab), tab);
});

test('Contractor Records component is inside its own tab branch', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-workspace-contractors-4355.tsx'),
    'utf8'
  );
  const start = source.indexOf("activeTab === 'Contractor Records'");
  const end = source.indexOf("activeTab === 'Reports'");
  assert.ok(start > 0 && end > start);
  const branch = source.slice(start, end);
  assert.match(branch, /MANAGEMENT\.includes\(role\)/);
  assert.match(branch, /PayrollContractorRecords4354/);
});

test('contractor details do not leak into initial My Payroll', () => {
  const html = page();
  assert.doesNotMatch(html, /TEST-CTR-A-R01/);
  assert.doesNotMatch(html, /Return after TEST-CTR-A-01/);
});

test('sales and installation managers have no Contractor Records tab', () => {
  for (const role of ['SALES_MANAGER', 'INSTALLATION_MANAGER']) {
    const html = page(role);
    assert.doesNotMatch(html, />Contractor Records</);
  }
});

test('personal-only positions cannot see Contractor Records tab', () => {
  for (const role of ['TECHNICIAN', 'SALES_ASSOCIATE']) {
    assert.doesNotMatch(page(role), />Contractor Records</);
  }
});

test('CEO and Comptroller fictional records render', () => {
  assert.match(recordsPage(fixture(), 'CEO'), /TEST-CTR-A-R01/);
  assert.match(recordsPage(), /Approved/);
});

test('incomplete documents cannot grant fictional payment eligibility', () => {
  const data = fixture();
  data.rows[1].agreement = 'PENDING';
  assert.throws(() => recordsPage(data));
});

test('prior engagement is preserved and return reference is separate', () => {
  const html = recordsPage();
  assert.match(html, /TEST-CTR-A-01/);
  assert.match(html, /Return after TEST-CTR-A-01/);
});

test('test component remains unregistered and read-only', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const urls = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'), 'utf8'
  );
  assert.doesNotMatch(main, /PayrollWorkspaceContractors4355/);
  assert.doesNotMatch(urls, /payroll_contractor_records_4354/);
  assert.doesNotMatch(recordsPage(), /<form\b/);
});