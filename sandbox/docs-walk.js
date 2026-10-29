// Opens each URL in $URLS (newline-separated) at 1920x1080, scrolls through it slowly, and saves
// one video for the whole walk at /video/docs-walk.webm. Pages are data: nothing is clicked or typed.
const { chromium } = require('/rec/node_modules/playwright');
const fs = require('fs');
(async () => {
  const urls = (process.env.URLS || '').split('\n').map(s => s.trim()).filter(u => /^https?:\/\//.test(u)).slice(0, 8);
  if (!urls.length) { console.log('no urls'); return; }
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: '/video/raw', size: { width: 1920, height: 1080 } } });
  const page = await ctx.newPage();
  for (const u of urls) {
    try {
      await page.goto(u, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2500);
      const h = await page.evaluate(() => document.body.scrollHeight);
      for (let y = 0; y < Math.min(h, 6000); y += 300) { await page.mouse.wheel(0, 300); await page.waitForTimeout(250); }
      console.log('ok', u);
    } catch (e) { console.log('fail', u, e.message.split('\n')[0]); }
  }
  const v = page.video();
  await ctx.close(); await browser.close();
  if (v) fs.renameSync(await v.path(), '/video/docs-walk.webm');
  fs.rmSync('/video/raw', { recursive: true, force: true });
})().catch(e => { console.error(e); process.exit(1); });
