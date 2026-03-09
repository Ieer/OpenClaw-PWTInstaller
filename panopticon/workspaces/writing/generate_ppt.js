const pptxgen = require('pptxgenjs');
const html2pptx = require('/home/node/.openclaw/workspace/skills/pptx/scripts/html2pptx.js');
const path = require('path');

async function createPresentation() {
  console.log('开始创建 PPT...');

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'AI Assistant';
  pptx.title = 'AI Agent 发展史';

  const slidesDir = '/home/node/.openclaw/workspace/slides';
  const slideFiles = [
    'slide01.html', 'slide02.html', 'slide03.html', 'slide04.html',
    'slide05.html', 'slide06.html', 'slide07.html', 'slide08.html',
    'slide09.html', 'slide10.html', 'slide11.html', 'slide12.html',
    'slide13.html', 'slide14.html', 'slide15.html', 'slide16.html',
    'slide17.html', 'slide18.html'
  ];

  for (const slideFile of slideFiles) {
    const htmlPath = path.join(slidesDir, slideFile);
    console.log(`处理 ${slideFile}...`);

    try {
      await html2pptx(htmlPath, pptx);
      console.log(`  ✓ ${slideFile} 完成`);
    } catch (error) {
      console.error(`  ✗ ${slideFile} 失败:`, error.message);
      throw error;
    }
  }

  const outputPath = '/home/node/.openclaw/workspace/ai_agent_history.pptx';
  console.log(`保存到 ${outputPath}...`);

  await pptx.writeFile({ fileName: outputPath });
  console.log('✓ PPT 创建成功！');

  return outputPath;
}

createPresentation().catch(console.error);
