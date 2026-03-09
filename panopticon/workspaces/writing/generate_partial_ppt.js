const pptxgen = require('pptxgenjs');
const html2pptx = require('/home/node/.openclaw/workspace/skills/pptx/scripts/html2pptx.js');
const path = require('path');

async function createPartialPresentation() {
  console.log('开始创建部分 PPT（包含已验证的页面）...');

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'AI Assistant';
  pptx.title = 'AI Agent 发展史';

  // 只处理已验证的前几页
  const slideFiles = [
    'slide01.html', 'slide02.html'
  ];

  for (const slideFile of slideFiles) {
    const htmlPath = path.join('/home/node/.openclaw/workspace/slides', slideFile);
    console.log(`处理 ${slideFile}...`);

    try {
      await html2pptx(htmlPath, pptx);
      console.log(`  ✓ ${slideFile} 完成`);
    } catch (error) {
      console.error(`  ✗ ${slideFile} 失败:`, error.message);
      // 继续处理下一页
    }
  }

  const outputPath = '/home/node/.openclaw/workspace/ai_agent_history_partial.pptx';
  console.log(`保存到 ${outputPath}...`);

  await pptx.writeFile({ fileName: outputPath });
  console.log('✓ 部分 PPT 创建成功！');

  return outputPath;
}

createPartialPresentation().catch(console.error);
