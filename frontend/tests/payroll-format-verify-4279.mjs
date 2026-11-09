import fs from "node:fs";
import assert from "node:assert/strict";

const file = new URL("./payroll-format-preview-4279.html", import.meta.url);
const html = fs.readFileSync(file, "utf8");

for (const view of [
  "my-compensation",
  "payroll-review",
  "company-summary",
]) {
  assert.equal(
    (html.match(new RegExp('data-view="' + view + '"', "g")) || []).length,
    1,
    "Expected exactly one " + view + " view"
  );
}

for (const phrase of [
  "FICTIONAL DATA - DESIGN REVIEW ONLY",
  "Approved - Not Yet Paid",
  "Scheduled Wednesday",
  "Actual paid date",
  "Earned date",
  "Comptroller",
  "CEO and Comptroller only",
  "not operational totals",
  "no operational integration",
]) {
  assert.ok(html.includes(phrase), "Missing content: " + phrase);
}

assert.ok(!/<script\b/i.test(html), "Scripts must be absent");
assert.ok(!/<form\b/i.test(html), "Payment forms must be absent");
assert.ok(!/<button\b/i.test(html), "Operational controls must be absent");
assert.ok(!/\bfetch\s*\(/i.test(html), "API access must be absent");
assert.ok(!/XMLHttpRequest|WebSocket|EventSource/i.test(html),
  "Network clients must be absent");
assert.ok(!/<input\b/i.test(html), "Live input must be absent");

assert.ok(html.indexOf("Contractors<strong>$8,500.00") >= 0);
assert.ok(html.indexOf("Employees<strong>$4,000.00") >= 0);
assert.ok(html.indexOf("Combined total<strong>$12,500.00") >= 0);

console.log("PASS: All three proposed payroll views are present.");
console.log("PASS: Fictional-data labels and pay-status distinctions.");
console.log("PASS: No scripts, forms, buttons, inputs or API requests.");
console.log("PASS: Payroll summary demonstration reconciles.");
console.log("PASS: Test-only preview structure verified.");