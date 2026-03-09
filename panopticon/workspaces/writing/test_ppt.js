const pptxgen = require('pptxgenjs');
const html2pptx = require('/home/node/.openclaw/workspace/skills/pptx/scripts/html2pptx.js');
const path = require('path');

async function createTestPresentation() {
  console.log('开始创建测试 PPT...');

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'AI Assistant';
  pptx.title = 'AI Agent 发展史';

  // 只处理第一页
  const htmlPath = '/home/node/.openclaw/workspace/slides/slide01.html';
  console.log(`处理 slide01.html...`);

  try {
    await html2pptx(htmlPath, pptx);
    console.log('✓ slide01.html 完成');
  } catch (error) {
    console.error('✗ slide01.html 失败:', error.message);
    console.error(error.stack);
    throw error;
  }

  const outputPath = '/home/node/.openclaw/workspace/test_output.pptx';
  console.log(`保存到 ${outputPath}...`);

  await pptx.writeFile({ fileName: outputPath });
  console.log('✓ 测试 PPT 创建成功！');

  return outputPath;
}

createTestPresentation().catch(console.error);
