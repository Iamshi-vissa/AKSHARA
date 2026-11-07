/**
 * Phase 1 end-to-end check against the real stack (API + Postgres + Redis + Vite).
 *
 *   node e2e/phase1.e2e.mjs <samples-dir> [screenshot-dir]
 *
 * <samples-dir> must contain Research_Report.docx, Methodology_Paper.pdf,
 * Quarterly_Review.pptx and Thesis.docm (a renamed DOCX, to prove .docm is refused).
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE = process.env.AKSHARA_WEB_URL ?? 'http://localhost:5173';
const [samples, shots] = process.argv.slice(2);
if (!samples) throw new Error('usage: node e2e/phase1.e2e.mjs <samples-dir> [screenshot-dir]');

const email = `e2e-${Date.now()}@example.com`;
const password = 'Akshara-e2e-2026';
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');
const check = (cond, msg) => {
  if (!cond) throw new Error(`FAILED: ${msg}`);
  console.log(`  ✓ ${msg}`);
};
const shot = async (page, name) => shots && page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
const page = await context.newPage();
const consoleErrors = [];
// A 401 from /auth/refresh is the expected answer when a stored session hint is stale.
const expected401 = (m) => m.text().includes('401') && m.location().url.includes('/auth/refresh');
page.on('console', (m) => m.type() === 'error' && !expected401(m) && consoleErrors.push(`${m.text()} @ ${m.location().url}`));

try {
  console.log('Auth');
  await page.goto(`${BASE}/documents`);
  await page.getByRole('heading', { name: 'Welcome back' }).waitFor();
  check(page.url().endsWith('/login'), 'anonymous visitor is redirected to sign-in');
  await page.waitForTimeout(2500); // let the hero animation settle for the screenshot
  await shot(page, '01-sign-in');

  await page.getByRole('link', { name: 'Create an account' }).click();
  await page.getByLabel('Name (optional)').fill('Ada Lovelace');
  await page.getByLabel('E-mail').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /create account/i }).click();
  await page.getByText('Good to see you, Ada.', { exact: false }).first().waitFor({ timeout: 15000 });
  check(true, 'registration signs the user in and opens the dashboard');

  console.log('Upload');
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Library', exact: true }).click();
  await page.getByRole('heading', { name: 'Your documents' }).waitFor();
  const files = ['Research_Report.docx', 'Methodology_Paper.pdf', 'Quarterly_Review.pptx', 'Thesis.docm'];
  await page.getByLabel('Choose files to upload').setInputFiles(files.map((f) => path.join(samples, f)));
  await page.getByText('Macro-enabled files are not accepted.').waitFor();
  check(true, '.docm is refused before upload');
  await page.waitForFunction(() => document.querySelectorAll('a[href^="/documents/"]').length >= 6, null, { timeout: 20000 });
  const stored = await page.getByText('Stored securely as version 1').count();
  check(stored === 3, 'DOCX, PDF and PPTX uploaded and stored (3/3)');
  await page.waitForTimeout(800);
  await shot(page, '03-library');

  console.log('Document detail + download');
  await page.locator('tbody').getByText('Methodology_Paper', { exact: true }).click();
  await page.getByRole('heading', { name: 'Version history' }).waitFor();
  check((await page.getByText('Security notes').count()) === 0, 'benign LibreOffice PDF shows no false security warning');
  const shown = (await page.locator('code').first().textContent())?.trim();
  check(shown === sha(path.join(samples, 'Methodology_Paper.pdf')), 'SHA-256 shown matches the local file');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /download original/i }).click(),
  ]);
  const saved = await download.path();
  check(sha(saved) === shown, 'downloaded file is byte-identical to the upload');
  check(download.suggestedFilename() === 'Methodology_Paper.pdf', 'download keeps the original filename');
  await shot(page, '04-document');

  console.log('Dashboard');
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Dashboard', exact: true }).click();
  await page.getByRole('heading', { name: 'Recent documents' }).waitFor();
  await page.waitForTimeout(2000);
  const lockedCount = await page.locator('[aria-disabled="true"]').count();
  check(lockedCount >= 5, `unbuilt modules are shown as locked, not faked (${lockedCount} locked)`);
  await shot(page, '02-dashboard');

  console.log('Session');
  await page.reload();
  await page.getByRole('heading', { name: 'Recent documents' }).waitFor();
  check(true, 'session survives a reload via the httpOnly refresh cookie');
  const cookies = await context.cookies();
  const refresh = cookies.find((c) => c.name === 'akshara_refresh');
  check(refresh?.httpOnly === true && refresh.sameSite === 'Strict', 'refresh cookie is httpOnly + SameSite=Strict');
  check(!(await page.evaluate(() => document.cookie)).includes('akshara_refresh'), 'refresh token is invisible to JavaScript');

  await page.getByRole('complementary').getByRole('button', { name: 'Sign out' }).last().click();
  await page.getByRole('heading', { name: 'Welcome back' }).waitFor();
  await page.goto(`${BASE}/`);
  await page.getByRole('heading', { name: 'Welcome back' }).waitFor();
  check(true, 'sign-out ends the session');

  console.log('Mobile layout');
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const mp = await mobile.newPage();
  await mp.goto(`${BASE}/login`);
  await mp.getByLabel('E-mail').fill(email);
  await mp.getByLabel('Password').fill(password);
  await mp.getByRole('button', { name: /sign in/i }).click();
  await mp.getByRole('heading', { name: 'Recent documents' }).waitFor();
  const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(overflow <= 0, 'no horizontal page scroll at phone width');
  await mp.waitForTimeout(1500);
  await shot(mp, '05-mobile');
  await mobile.close();

  check(consoleErrors.length === 0, `no browser console errors${consoleErrors.length ? ': ' + consoleErrors.join(' | ') : ''}`);
  console.log('\nPhase 1 E2E: all checks passed.');
} finally {
  await browser.close();
}
