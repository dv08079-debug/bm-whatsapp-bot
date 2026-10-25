const { chromium } = require('playwright');
(async () => {
  const dir = process.argv[2];
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1920 }, recordVideo: { dir, size: { width: 1080, height: 1920 } } });
  const p = await ctx.newPage();
  await p.goto('file://' + dir + '/index.html');
  await p.waitForTimeout(500);
  await p.evaluate(() => window.__start());
  await p.waitForFunction(() => window.__done === true, null, { timeout: 120000, polling: 200 });
  const v = p.video(); await ctx.close(); await b.close();
  console.log(await v.path());
})();
