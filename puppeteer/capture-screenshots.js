/**
 * Compliance Screenshot Capture Script
 * Purpose: Capture timestamped, full-page screenshots of specified pricing/legal
 * pages for audit trail purposes. Designed for scheduled (cron/CI) execution.
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Toggle this to false for local visual debugging, true for production runs
const HEADLESS_MODE = true;

// Detect if running in a container/CI environment as root — common cause of
// sandbox launch failures. Adjust this check based on your actual CI setup.
const RUNNING_AS_ROOT_CONTAINER = process.env.CI === 'true' || process.env.DOCKER_CONTAINER === 'true';

// Target pages for compliance capture. Replace with your actual audit targets.
const TARGET_PAGES = [
  { label: 'aws-pricing', url: 'https://aws.amazon.com/pricing/' },
  { label: 'azure-pricing', url: 'https://azure.microsoft.com/en-us/pricing/' },
  { label: 'gcp-pricing', url: 'https://cloud.google.com/pricing' }
];

function getTimestampFolder() {
  const now = new Date();
  return now.toISOString().split('T')[0]; // e.g. 2026-07-27
}

function getTimestampFilename(label) {
  const now = new Date();
  const time = now.toISOString().replace(/[:.]/g, '-'); // filesystem-safe
  return `${label}_${time}.png`;
}

async function captureScreenshots() {
  const outputDir = path.join(__dirname, 'screenshots', getTimestampFolder());
  fs.mkdirSync(outputDir, { recursive: true });

  const launchArgs = [];
  if (RUNNING_AS_ROOT_CONTAINER) {
    // Only added when actually needed — not a blanket default.
    launchArgs.push('--no-sandbox', '--disable-setuid-sandbox');
  }

  const browser = await puppeteer.launch({
    headless: HEADLESS_MODE,
    args: launchArgs
  });

  const results = [];

  try {
    for (const target of TARGET_PAGES) {
      const page = await browser.newPage();

      try {
        await page.setViewport({ width: 1920, height: 1080 });

        console.log(`Navigating to ${target.label}: ${target.url}`);

        const response = await page.goto(target.url, {
          waitUntil: 'networkidle2', // waits until network is mostly idle,
                                      // better for pages with async pricing widgets
          timeout: 30000
        });

        // Verify page actually loaded successfully before screenshotting
        if (!response || !response.ok()) {
          throw new Error(`Page returned status ${response ? response.status() : 'no response'}`);
        }

        const filename = getTimestampFilename(target.label);
        const filepath = path.join(outputDir, filename);

        await page.screenshot({
          path: filepath,
          fullPage: true
        });

        console.log(`Screenshot saved: ${filepath}`);
        results.push({ label: target.label, status: 'success', file: filepath });

      } catch (pageError) {
        console.error(`Failed to capture ${target.label}: ${pageError.message}`);
        results.push({ label: target.label, status: 'failed', error: pageError.message });
      } finally {
        await page.close();
      }
    }
  } finally {
    // Runs even if something above throws — prevents orphaned Chromium process
    await browser.close();
  }

  console.log('\n--- Run Summary ---');
  results.forEach(r => {
    console.log(`${r.label}: ${r.status}${r.error ? ' (' + r.error + ')' : ''}`);
  });

  return results;
}

captureScreenshots()
  .then(() => console.log('\nCompliance screenshot capture complete.'))
  .catch(err => {
    console.error('Fatal error during capture run:', err);
    process.exit(1);
  });
