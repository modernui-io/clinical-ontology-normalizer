/**
 * External-Readiness Demo Rehearsal Script
 * Visits /sales-demo, /trust, /proof and captures:
 * - Full-page screenshots
 * - Content audit (evidence markers, simulation labels, unbacked claims)
 * - Route health (HTTP status, render success)
 * - Evidence bundle summary
 */
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const BASE_URL = 'http://localhost:3000';
const EVIDENCE_DIR = join(import.meta.dirname, '..', 'docs', 'evidence', 'demo-rehearsal');
const ROUTES = ['/sales-demo', '/trust', '/proof'];

// Terms that indicate evidence-backing
const EVIDENCE_TERMS = [
  'evidence', 'artifact', 'freshness', 'verified', 'provenance',
  'drill', 'PASS', 'MTTR', 'RTO', 'signoff', 'conditional_go',
  'simulation', 'SectionEvidenceTag', 'DataSourceModeBanner'
];

// Terms that indicate potentially unbacked claims
const RISK_TERMS = [
  '100% uptime', '100% accuracy', 'guaranteed', 'zero downtime',
  'production-grade', 'enterprise-ready', 'fully compliant'
];

async function auditPage(page, route) {
  const url = `${BASE_URL}${route}`;
  const result = {
    route,
    url,
    timestamp: new Date().toISOString(),
    httpStatus: null,
    renderSuccess: false,
    screenshotPath: null,
    evidenceTermsFound: [],
    riskTermsFound: [],
    simulationLabels: [],
    headings: [],
    linkCount: 0,
    errorMessages: [],
    textLength: 0,
  };

  try {
    const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    result.httpStatus = response?.status() || null;

    // Wait for hydration
    await page.waitForTimeout(2000);

    // Take full-page screenshot
    const screenshotName = `rehearsal-${route.replace(/\//g, '-').replace(/^-/, '')}.png`;
    const screenshotPath = join(EVIDENCE_DIR, screenshotName);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    result.screenshotPath = `docs/evidence/demo-rehearsal/${screenshotName}`;

    // Get page text content
    const bodyText = await page.evaluate(() => document.body?.innerText || '');
    result.textLength = bodyText.length;
    result.renderSuccess = bodyText.length > 100;

    // Check for evidence terms
    const lowerText = bodyText.toLowerCase();
    for (const term of EVIDENCE_TERMS) {
      if (lowerText.includes(term.toLowerCase())) {
        result.evidenceTermsFound.push(term);
      }
    }

    // Check for risk terms (unbacked claims)
    for (const term of RISK_TERMS) {
      if (lowerText.includes(term.toLowerCase())) {
        result.riskTermsFound.push(term);
      }
    }

    // Find simulation/mode labels
    const simLabels = await page.evaluate(() => {
      const labels = [];
      // Look for simulation banners
      const banners = document.querySelectorAll('[class*="simulation"], [class*="banner"], [data-testid*="simulation"], [data-testid*="mode"]');
      banners.forEach(el => {
        const text = el.textContent?.trim().substring(0, 200);
        if (text) labels.push(text);
      });
      // Look for evidence tags
      const tags = document.querySelectorAll('[data-testid*="evidence"], [data-source]');
      tags.forEach(el => {
        const src = el.getAttribute('data-source') || el.getAttribute('data-testid');
        if (src) labels.push(`[tag] ${src}`);
      });
      return labels;
    });
    result.simulationLabels = simLabels;

    // Get headings
    const headings = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('h1, h2, h3')).map(h => ({
        level: h.tagName,
        text: h.textContent?.trim().substring(0, 100)
      }));
    });
    result.headings = headings;

    // Count links
    result.linkCount = await page.evaluate(() => document.querySelectorAll('a').length);

    // Check for error states
    const errors = await page.evaluate(() => {
      const errs = [];
      const errorEls = document.querySelectorAll('[class*="error"], [role="alert"]');
      errorEls.forEach(el => {
        const text = el.textContent?.trim().substring(0, 200);
        if (text) errs.push(text);
      });
      return errs;
    });
    result.errorMessages = errors;

  } catch (err) {
    result.errorMessages.push(`Navigation error: ${err.message}`);
  }

  return result;
}

async function main() {
  mkdirSync(EVIDENCE_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const results = [];
  for (const route of ROUTES) {
    console.log(`Auditing ${route}...`);
    const result = await auditPage(page, route);
    results.push(result);

    const status = result.renderSuccess ? 'PASS' : 'FAIL';
    const risks = result.riskTermsFound.length > 0 ? `RISKS: ${result.riskTermsFound.join(', ')}` : 'No unbacked claims';
    console.log(`  ${status} | HTTP ${result.httpStatus} | ${result.evidenceTermsFound.length} evidence terms | ${risks}`);
  }

  await browser.close();

  // Generate evidence bundle
  const bundle = {
    rehearsal_id: `demo-rehearsal-${new Date().toISOString().replace(/[:.]/g, '').substring(0, 15)}Z`,
    executed_at: new Date().toISOString(),
    operator: 'closure-sweep-agent',
    routes_audited: ROUTES.length,
    overall_pass: results.every(r => r.renderSuccess && r.riskTermsFound.length === 0),
    results,
    summary: {
      all_routes_render: results.every(r => r.renderSuccess),
      all_http_200: results.every(r => r.httpStatus === 200),
      total_evidence_terms: results.reduce((sum, r) => sum + r.evidenceTermsFound.length, 0),
      total_risk_terms: results.reduce((sum, r) => sum + r.riskTermsFound.length, 0),
      unbacked_claims: results.flatMap(r => r.riskTermsFound.map(t => ({ route: r.route, term: t }))),
    }
  };

  const bundlePath = join(EVIDENCE_DIR, 'demo-rehearsal-evidence.json');
  writeFileSync(bundlePath, JSON.stringify(bundle, null, 2));
  console.log(`\nEvidence bundle written to: ${bundlePath}`);

  // Print summary
  console.log('\n=== DEMO REHEARSAL SUMMARY ===');
  console.log(`Routes audited: ${ROUTES.length}`);
  console.log(`Overall: ${bundle.overall_pass ? 'PASS' : 'REVIEW NEEDED'}`);
  console.log(`All render: ${bundle.summary.all_routes_render}`);
  console.log(`All HTTP 200: ${bundle.summary.all_http_200}`);
  console.log(`Evidence terms found: ${bundle.summary.total_evidence_terms}`);
  console.log(`Unbacked claims found: ${bundle.summary.total_risk_terms}`);
  if (bundle.summary.unbacked_claims.length > 0) {
    console.log('UNBACKED CLAIMS:');
    bundle.summary.unbacked_claims.forEach(c => console.log(`  ${c.route}: "${c.term}"`));
  }

  for (const r of results) {
    console.log(`\n--- ${r.route} ---`);
    console.log(`  HTTP: ${r.httpStatus}`);
    console.log(`  Rendered: ${r.renderSuccess} (${r.textLength} chars)`);
    console.log(`  Screenshot: ${r.screenshotPath}`);
    console.log(`  Evidence terms: ${r.evidenceTermsFound.join(', ')}`);
    console.log(`  Headings: ${r.headings.map(h => `[${h.level}] ${h.text}`).join(' | ')}`);
    console.log(`  Simulation labels: ${r.simulationLabels.length > 0 ? r.simulationLabels.join('; ') : 'none found in DOM'}`);
    console.log(`  Links: ${r.linkCount}`);
    if (r.riskTermsFound.length > 0) {
      console.log(`  ⚠ RISK TERMS: ${r.riskTermsFound.join(', ')}`);
    }
    if (r.errorMessages.length > 0) {
      console.log(`  Errors: ${r.errorMessages.join('; ')}`);
    }
  }

  // Exit with code based on pass/fail
  process.exit(bundle.overall_pass ? 0 : 1);
}

main().catch(err => {
  console.error('Rehearsal failed:', err);
  process.exit(2);
});
