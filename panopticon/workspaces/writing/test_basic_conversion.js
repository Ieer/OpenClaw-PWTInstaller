/**
 * Basic HTML to PPTX conversion test
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./skills/pptx/scripts/html2pptx');
const fs = require('fs');

async function main() {
  console.log('🚀 Testing basic HTML to PPTX conversion...\n');

  // Create simple HTML
  const testHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 720pt;
      height: 405pt;
      margin: 0;
      padding: 0;
      background: white;
    }
    .container {
      padding: 40pt;
    }
    h1 {
      font-size: 48pt;
      color: #B165FB;
    }
    p {
      font-size: 18pt;
      color: #181B24;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Basic Test</h1>
    <p>This is a simple test of HTML to PPTX conversion.</p>
  </div>
</body>
</html>`;

  // Write HTML
  const testHtmlPath = '/tmp/test-basic.html';
  fs.writeFileSync(testHtmlPath, testHtml);
  console.log(`✅ HTML written to ${testHtmlPath}`);

  // Create presentation
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  console.log('🔄 Converting HTML to PPTX...');

  try {
    const { slide } = await html2pptx(testHtmlPath, pptx);
    console.log('✅ Conversion successful');

    // Save presentation
    const outputPath = '/tmp/test-basic.pptx';
    await pptx.writeFile({ fileName: outputPath });
    console.log(`📄 Presentation saved to: ${outputPath}`);

    console.log('\n✅ All tests passed!');
    return outputPath;
  } catch (error) {
    console.error('❌ Conversion failed:', error.message);
    throw error;
  }
}

main().catch(error => {
  console.error('❌ Test failed:', error);
  process.exit(1);
});
