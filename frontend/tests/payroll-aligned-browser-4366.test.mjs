import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createServer } from 'vite';

const dir = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(dir, '..');
const require = createRequire(resolve(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const workspaceSource = readFileSync(
  resolve(dir, 'payroll-workspace-aligned-4366.tsx'), 'utf8'
);
const browserSource = readFileSync(
  resolve(dir, 'payroll-aligned-browser-4366.tsx'), 'utf8'
);
const html = readFileSync(
  resolve(dir, 'payroll-aligned-browser-4366.html'), 'utf8'
);

let server;
let Workspace;

before(async () => {
  server = await createServer({
    root: frontend,
    configFile: false,
    logLevel: 'error',
    optimizeDeps: { noDiscovery: true, entries: [], include: [] },
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });

  Workspace = (await server.ssrLoadModule(
    '/tests/payroll-workspace-aligned-4366.tsx'
  )).PayrollWorkspaceAligned4366;
});

after(async () => {
  if (server) await server.close();
});

function render(role = 'COMPTROLLER') {
  return renderToStaticMarkup(
    React.createElement(Workspace, {
      role,
      onReturnToProjects: () => {},
    })
  );
}

test('all six approved tabs remain present', () => {
  const output = render();
  for (const tab of [
    'My Payroll', 'Weekly Payroll', 'Approvals',
    'Payment History', 'Contractor Records', 'Reports',
  ]) {
    assert.ok(output.includes(tab), tab);
  }
});

test('return control is inside the same Payroll sections nav', () => {
  const start = workspaceSource.indexOf(
    '<nav aria-label="Payroll sections"'
  );
  const end = workspaceSource.indexOf('</nav>', start);
  const nav = workspaceSource.slice(start, end);

  assert.ok(start > 0);
  assert.ok(end > start);
  assert.match(nav, /tabs\.map\(tab =>/);
  assert.match(nav, /Return to Customers &amp; Projects/);
});

test('return control is after tab buttons and aligns right', () => {
  const start = workspaceSource.indexOf(
    '<nav aria-label="Payroll sections"'
  );
  const end = workspaceSource.indexOf('</nav>', start);
  const nav = workspaceSource.slice(start, end);

  assert.ok(
    nav.indexOf('Return to Customers') >
    nav.indexOf('setRequestedTab(tab)')
  );
  assert.match(nav, /marginLeft: 'auto'/);
  assert.match(nav, /flexWrap: 'wrap'/);
});

test('return button is visibly rendered within navigation', () => {
  const output = render();
  const start = output.indexOf('aria-label="Payroll sections"');
  const end = output.indexOf('</nav>', start);

  assert.ok(start >= 0 && end > start);
  assert.match(
    output.slice(start, end),
    /Return to Customers &amp; Projects/
  );
});

test('return callback is required and is not a logout', () => {
  assert.throws(() => renderToStaticMarkup(
    React.createElement(Workspace, { role: 'COMPTROLLER' })
  ));
  assert.match(workspaceSource, /onClick=\{onReturnToProjects\}/);
  assert.match(workspaceSource, /type="button"/);
  assert.doesNotMatch(workspaceSource, /logout\(|signOut\(/);
});

test('personal roles retain their permitted tabs', () => {
  for (const role of ['SALES_ASSOCIATE', 'TECHNICIAN']) {
    const output = render(role);
    assert.match(output, /Return to Customers/);
    assert.match(output, />My Payroll</);
    assert.doesNotMatch(output, />Weekly Payroll</);
    assert.doesNotMatch(output, />Contractor Records</);
  }
});

test('browser entry uses aligned workspace and fictional return', () => {
  assert.match(browserSource, /PayrollWorkspaceAligned4366/);
  assert.match(browserSource, /onReturnToProjects/);
  assert.match(browserSource, /payroll-projects-destination-4364/);
  assert.match(html, /payroll-aligned-browser-4366\.tsx/);
});

test('all fictional payroll fixtures are still connected', () => {
  for (const prop of [
    'report={fictionalData}',
    'weeklyReport={fictionalWeekly}',
    'approvalReport={fictionalApprovals}',
    'historyReport={fictionalHistory}',
    'contractorReport={fictionalContractors}',
    'companyReport={fictionalReports}',
  ]) {
    assert.ok(browserSource.includes(prop), prop);
  }
});

test('no real payroll requests or payment actions are enabled', () => {
  assert.doesNotMatch(
    browserSource, /\bfetch\s*\(|XMLHttpRequest|axios\./
  );
  assert.doesNotMatch(
    workspaceSource, /approvePayment\(|issuePayment\(/
  );
  assert.match(html, /fictional destination/);
});

test('new preview remains outside operational registration', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'), 'utf8'
  );
  const routes = readFileSync(
    resolve(frontend, '..', 'backend', 'config', 'urls.py'), 'utf8'
  );

  assert.doesNotMatch(main, /PayrollWorkspaceAligned4366/);
  assert.doesNotMatch(routes, /PayrollWorkspaceAligned4366/);
  assert.match(main, /setPanel\('projects'\)/);
});