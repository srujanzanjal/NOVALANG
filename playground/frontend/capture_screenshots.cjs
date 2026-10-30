const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function capture() {
  const outDir = path.resolve(__dirname, '../../docs/screenshots');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:5174 ...');
  await page.goto('http://localhost:5174');
  // Wait for Monaco editor to finish loading
  await page.waitForSelector('.monaco-editor', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(3500);

  // Select factorial example from dropdown if available
  try {
    const select = await page.$('select');
    if (select) {
      await select.selectOption('factorial');
      await page.waitForTimeout(1500);
    }
  } catch (e) {
    console.log('Dropdown select warning:', e.message);
  }

  // 1. Overview with Tokens
  console.log('Capturing Screenshot 1: Overview with Tokens');
  await page.screenshot({ path: path.join(outDir, 'screenshot1_tokens.png') });

  // 2. Click AST tab
  console.log('Capturing Screenshot 2: AST');
  await page.click('button:has-text("AST")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, 'screenshot2_ast.png') });

  // 3. Click TAC tab
  console.log('Capturing Screenshot 3: TAC IR');
  await page.click('button:has-text("TAC")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, 'screenshot3_tac.png') });

  // 4. Click Optimized TAC tab
  console.log('Capturing Screenshot 4: Optimized TAC');
  await page.click('button:has-text("Optimized TAC")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, 'screenshot4_optimized_tac.png') });

  // 5. Click LLVM IR tab
  console.log('Capturing Screenshot 5: LLVM IR');
  await page.click('button:has-text("LLVM IR")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, 'screenshot5_llvm_ir.png') });

  // 6. Click Output tab
  console.log('Capturing Screenshot 6: Execution Output');
  await page.click('button:has-text("Output")');
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, 'screenshot6_output.png') });

  await browser.close();
  console.log('All screenshots captured successfully in:', outDir);
}

capture().catch(err => {
  console.error('Error capturing screenshots:', err);
  process.exit(1);
});
