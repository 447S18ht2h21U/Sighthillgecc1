import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';
import { createServer } from 'vite';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

let vite;
let Workspace;

before(async () => {
  vite = await createServer({
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
  const imported = await vite.ssrLoadModule(
    '/src/PayrollWorkspacePreview4325.tsx'
  );
  Workspace = imported.PayrollWorkspacePreview4325;
  assert.equal(typeof Workspace, 'function');
});

after(async () => {
  if (vite) await vite.close();
});

function render(role) {
  return renderToStaticMarkup(
    React.createElement(Workspace, { role })
  );
}

function visibleTab(html, name) {
  return html.includes('>' + name + '</button>');
}

const allTabs = [
  'My Payroll',
  'Weekly Payroll',
  'Approvals',
  'Payment History',
  'Contractor Records',
  'Reports',
];

function expectTabs(role, expected) {
  const html = render(role);
  for (const tab of allTabs) {
    assert.equal(
      visibleTab(html, tab),
      expected.includes(tab),
      role + ' / ' + tab
    );
  }
}

test('CEO receives all six section buttons', () => {
  expectTabs('CEO', allTabs);
});

test('Comptroller receives all six section buttons', () => {
  expectTabs('COMPTROLLER', allTabs);
});

test('Sales Manager receives authorized management tabs only', () => {
  expectTabs('SALES_MANAGER', allTabs.filter(
    tab => tab !== 'Contractor Records'
  ));
  assert.match(render('SALES_MANAGER'), /sales-associate payroll/);
});

test('Installation Manager receives technician management tabs only', () => {
  expectTabs('INSTALLATION_MANAGER', allTabs.filter(
    tab => tab !== 'Contractor Records'
  ));
  assert.match(render('INSTALLATION_MANAGER'), /technician payroll/);
});

test('Sales Associate receives personal sections only', () => {
  expectTabs('SALES_ASSOCIATE', [
    'My Payroll', 'Payment History', 'Reports',
  ]);
});

test('Technician receives personal sections only', () => {
  expectTabs('TECHNICIAN', [
    'My Payroll', 'Payment History', 'Reports',
  ]);
});

test('Other positions do not receive management sections', () => {
  for (const role of [
    'MARKETING',
    'ACCOUNTS_PAYABLE_ASSOCIATE',
    'DATABASE_ADMINISTRATOR',
    'UNRECOGNIZED_ROLE',
  ]) {
    expectTabs(role, [
      'My Payroll', 'Payment History', 'Reports',
    ]);
  }
});

test('Every rendered screen clearly identifies fictional data', () => {
  for (const role of [
    'CEO', 'COMPTROLLER', 'SALES_MANAGER',
    'INSTALLATION_MANAGER', 'SALES_ASSOCIATE',
    'TECHNICIAN', 'MARKETING',
  ]) {
    const html = render(role);
    assert.match(html, /data-preview-only="true"/);
    assert.match(html, /Development preview only/);
    assert.match(html, /No live payroll/);
    assert.match(html, /Exports are disabled|report export is enabled/);
  }
});

test('Initial view contains no peer payment amounts', () => {
  for (const role of [
    'SALES_ASSOCIATE', 'TECHNICIAN', 'MARKETING',
  ]) {
    const html = render(role);
    assert.doesNotMatch(html, /Fictional Contractor A/);
    assert.doesNotMatch(html, /Fictional Contractor B/);
    assert.doesNotMatch(html, /\$1,250\.00/);
    assert.doesNotMatch(html, /\$875\.00/);
  }
});

test('Role selection does not introduce executable payment actions', () => {
  for (const role of ['CEO', 'COMPTROLLER', 'TECHNICIAN']) {
    const html = render(role);
    assert.doesNotMatch(html, /<form\b/);
    assert.doesNotMatch(html, /type="submit"/);
    assert.doesNotMatch(html, /href="\/api\//);
    assert.match(html, /Backend authorization is required/);
  }
});