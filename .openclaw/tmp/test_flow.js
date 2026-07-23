const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  console.log('1. Opening site...');
  await page.goto('https://youdo-photo.onrender.com', { waitUntil: 'networkidle', timeout: 60000 });
  console.log('   Title:', await page.title());
  
  // Check step 3 exists in DOM
  const step3 = await page.$('#step3');
  console.log('2. Step 3 in DOM:', step3 ? 'YES' : 'NO');
  
  // Check step 4 exists in DOM
  const step4 = await page.$('#step4');
  console.log('3. Step 4 in DOM:', step4 ? 'YES' : 'NO');
  
  // Check current active step
  const activeStep = await page.$eval('.step-panel.active', el => el.id);
  console.log('4. Active step:', activeStep);
  
  // Check the analysis flow code
  const jsCode = await page.evaluate(() => {
    return document.querySelector('script[src*="app.js"]') ? 'app.js loaded' : 'no app.js';
  });
  console.log('5. JS:', jsCode);
  
  // Check if goToStep(4) is in the page source
  const pageContent = await page.content();
  const hasGoToStep4 = pageContent.includes('goToStep(4)');
  console.log('6. goToStep(4) in page:', hasGoToStep4);
  
  // Check if "пропускаем модерацию" is in the JS
  const jsContent = await page.evaluate(async () => {
    const resp = await fetch('/js/app.js');
    return await resp.text();
  });
  const hasSkipModeration = jsContent.includes('пропускаем модерацию');
  console.log('7. "пропускаем модерацию" in JS:', hasSkipModeration);
  
  // Check if goToStep(3) is still called after analysis
  const goToStep3AfterAnalysis = jsContent.match(/setTimeout.*goToStep\(3\)/s);
  console.log('8. goToStep(3) after analysis:', goToStep3AfterAnalysis ? 'STILL EXISTS (BAD)' : 'REMOVED (GOOD)');
  
  // Check if goToStep(4) is called after analysis
  const goToStep4AfterAnalysis = jsContent.match(/setTimeout.*goToStep\(4\)/s);
  console.log('9. goToStep(4) after analysis:', goToStep4AfterAnalysis ? 'EXISTS (GOOD)' : 'MISSING (BAD)');
  
  // Take screenshot
  await page.screenshot({ path: '/home/work/.openclaw/workspace/YouDo_photo/.openclaw/tmp/test_screenshot.png', fullPage: true });
  console.log('10. Screenshot saved');
  
  await browser.close();
  console.log('\nDONE');
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
