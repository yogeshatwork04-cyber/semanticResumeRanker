const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOTS_DIR = path.resolve(__dirname, '..', 'docs', 'screenshots');

async function capture() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  console.log('Launching Chrome from:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1440, height: 960 },
  });

  try {
    const page = await browser.newPage();

    // 1. JD page
    console.log('1. Navigating to JD Input Screen...');
    await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 1000));
    // Click "Load Sample Senior Python JD" if available
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await page.evaluate((el) => el.innerText, btn);
      if (text.includes('Load Sample Senior Python JD')) {
        await btn.click();
        break;
      }
    }
    await new Promise((r) => setTimeout(r, 1500));
    const ss1 = path.join(SCREENSHOTS_DIR, '01_jd_page.png');
    await page.screenshot({ path: ss1 });
    console.log('[OK] Captured 01_jd_page.png');

    // 2. Upload page
    console.log('2. Navigating to Resumes Upload Screen...');
    await page.goto('http://127.0.0.1:5173/resumes?jd_id=1', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));
    const ss2 = path.join(SCREENSHOTS_DIR, '02_upload_page.png');
    await page.screenshot({ path: ss2 });
    console.log('[OK] Captured 02_upload_page.png');

    // 3. Ranking table
    console.log('3. Navigating to Results Dashboard...');
    await page.goto('http://127.0.0.1:5173/results?jd_id=1', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));
    const ss3 = path.join(SCREENSHOTS_DIR, '03_ranking_table.png');
    await page.screenshot({ path: ss3 });
    console.log('[OK] Captured 03_ranking_table.png');

    // 4. Alex Chen analysis
    console.log('4. Navigating to Alex Chen Candidate Analysis...');
    await page.goto('http://127.0.0.1:5173/candidates/1?jd_id=1', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));
    const ss4 = path.join(SCREENSHOTS_DIR, '04_alex_analysis.png');
    await page.screenshot({ path: ss4 });
    console.log('[OK] Captured 04_alex_analysis.png');

    // 5. Kevin Brooks analysis (showing listed-only badges)
    console.log('5. Navigating to Kevin Brooks Analysis (id=6)...');
    await page.goto('http://127.0.0.1:5173/candidates/6?jd_id=1', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));
    const ss5 = path.join(SCREENSHOTS_DIR, '05_kevin_analysis.png');
    await page.screenshot({ path: ss5 });
    console.log('[OK] Captured 05_kevin_analysis.png');

    // 6. Samira Khan analysis (showing experience cap note)
    console.log('6. Navigating to Samira Khan Analysis (id=9)...');
    await page.goto('http://127.0.0.1:5173/candidates/9?jd_id=1', { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));
    const ss6 = path.join(SCREENSHOTS_DIR, '06_samira_analysis.png');
    await page.screenshot({ path: ss6 });
    console.log('[OK] Captured 06_samira_analysis.png');

    console.log('All 6 screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

capture().catch((err) => {
  console.error('Screenshot capture failed:', err);
  process.exit(1);
});
