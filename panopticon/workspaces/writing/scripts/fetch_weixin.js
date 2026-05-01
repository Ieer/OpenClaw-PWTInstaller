const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true,  // 无头模式
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 }
  });

  const page = await context.newPage();

  console.log('正在访问页面...');
  await page.goto('https://mp.weixin.qq.com/s/J-E_l0fFOcWrKRRA8hR0xw', {
    waitUntil: 'networkidle',
    timeout: 30000
  });

  console.log('页面加载完成，等待手动验证（如需要）...');
  console.log('如果出现验证滑块，请在浏览器中手动完成');

  // 等待主内容出现
  await page.waitForTimeout(5000);

  // 检查是否有验证码
  const hasVerification = await page.locator('text=拖动下方滑块完成拼图').count();
  if (hasVerification > 0) {
    console.log('检测到滑块验证，请在浏览器中手动完成...');
    console.log('验证完成后按 Ctrl+C 继续或等待 60 秒自动继续');
    await page.waitForTimeout(60000);
  }

  // 尝试获取文章内容
  const title = await page.locator('meta[property="og:title"]').getAttribute('content');
  console.log('文章标题:', title);

  const content = await page.locator('#js_content').innerText().catch(() => '无法获取内容');
  console.log('\n' + '='.repeat(80));
  console.log(content);
  console.log('='.repeat(80));

  // 保存到文件
  const fs = require('fs');
  fs.writeFileSync('/home/node/.openclaw/workspace/sources/weixin_article.txt', content, 'utf8');
  console.log('\n内容已保存到 sources/weixin_article.txt');

  console.log('\n按 Ctrl+C 退出');
  await new Promise(() => {});  // 保持浏览器打开
})();
