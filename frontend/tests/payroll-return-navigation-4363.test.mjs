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
let ReturnComponent;

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

  const module = await server.ssrLoadModule(
    '/tests/payroll-return-navigation-4363.tsx'
  );

  ReturnComponent = module.PayrollReturnNavigation4363;
  assert.equal(typeof ReturnComponent, 'function');
});

after(async () => {
  if (server) await server.close();
});

function page(role = 'COMPTROLLER') {
  return renderToStaticMarkup(React.createElement(
    ReturnComponent,
    { role, onReturnToProjects: () => {} },
  ));
}

test('return button is displayed above payroll workspace', () => {
  const html = page();
  assert.match(html, /Return to Customers &amp; Projects/);
  assert.ok(
    html.indexOf('Return to Customers') <
    html.indexOf('Payroll &amp; Compensation')
  );
});

test('return control is not a submit or logout button', () => {
  const html = page();
  assert.match(html, /type="button"/);
  assert.doesNotMatch(html, /type="submit"/);
  assert.doesNotMatch(html, /Log out/);
});

test('button calls host navigation callback exactly once', () => {
  let calls = 0;
  const element = ReturnComponent({
    role: 'COMPTROLLER',
    onReturnToProjects: () => { calls++; },
  });

  const children = React.Children.toArray(element.props.children);
  const toolbar = children[0];
  const button = React.Children.only(toolbar.props.children);

  assert.equal(button.type, 'button');
  assert.equal(button.props.type, 'button');
  assert.equal(calls, 0);

  button.props.onClick();

  assert.equal(calls, 1);
});

test('missing navigation callback fails closed', () => {
  assert.throws(() => ReturnComponent({
    role: 'COMPTROLLER',
  }));
});

test('the approved six payroll tabs remain present', () => {
  const html = page();
  for (const tab of [
    'My Payroll',
    'Weekly Payroll',
    'Approvals',
    'Payment History',
    'Contractor Records',
    'Reports',
  ]) {
    assert.ok(html.includes(tab), tab);
  }
});

test('personal-only roles retain only permitted preview tabs', () => {
  for (const role of ['SALES_ASSOCIATE', 'TECHNICIAN']) {
    const html = page(role);
    assert.match(html, /Return to Customers/);
    assert.match(html, />My Payroll</);
    assert.match(html, />Payment History</);
    assert.match(html, />Reports</);
    assert.doesNotMatch(html, />Weekly Payroll</);
    assert.doesNotMatch(html, />Contractor Records</);
  }
});

test('return button does not expose payroll data', () => {
  const html = page();
  assert.doesNotMatch(html, /Fictional Employee A/);
  assert.doesNotMatch(html, /TEST-CTR-A-R01/);
  assert.doesNotMatch(html, /TEST-EMP-A/);
});

test('no payment or authorization actions exist in wrapper', () => {
  const source = readFileSync(
    resolve(frontend, 'tests', 'payroll-return-navigation-4363.tsx'),
    'utf8'
  );

  assert.doesNotMatch(source, /\bfetch\s*\(|XMLHttpRequest|axios\./);
  assert.doesNotMatch(source, /approvePayment|issuePayment/);
  assert.doesNotMatch(source, /window\.location|localStorage/);
});

test('existing application uses the verified project destination', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'),
    'utf8'
  );
  assert.match(main, /setPanel\('projects'\)/);
});

test('test-only wrapper remains outside operational registration', () => {
  const main = readFileSync(
    resolve(frontend, 'src', 'main.tsx'),
    'utf8'
  );
  const routes = readFileSync(
    resolve(root, 'backend', 'config', 'urls.py'),
    'utf8'
  );

  assert.doesNotMatch(main, /PayrollReturnNavigation4363/);
  assert.doesNotMatch(routes, /PayrollReturnNavigation4363/);
  assert.doesNotMatch(routes, /payroll_return_navigation_4363/);
});