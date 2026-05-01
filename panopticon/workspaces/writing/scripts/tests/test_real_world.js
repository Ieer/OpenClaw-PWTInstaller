/**
 * Real-world test: Create a presentation with auto-optimizations
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./skills/pptx/scripts/html2pptx');
const fs = require('fs');
const path = require('path');

async function createPresentation() {
  console.log('🎨 Creating presentation with auto-optimizations...\n');

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Ink Relay';
  pptx.title = 'Enhanced PPTX Demo';

  // Slide 1: Auto gradient rasterization + auto CSS style migration
  console.log('📄 Creating Slide 1: Gradient + Text Styles...');
  const slide1Html = `
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
      /* This gradient will be auto-rasterized */
      background: linear-gradient(135deg, #B165FB 0%, #40695B 100%);
    }
    .container {
      padding: 50pt 60pt;
    }
    h1 {
      font-size: 52pt;
      color: white;
      font-family: Arial, sans-serif;
      /* These styles will be auto-migrated to a wrapper */
      background: rgba(255, 255, 255, 0.25);
      border: 3pt solid rgba(255, 255, 255, 0.5);
      border-radius: 16pt;
      padding: 25pt;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    p {
      font-size: 20pt;
      color: white;
      font-family: Arial, sans-serif;
      /* These styles will be auto-migrated to a wrapper */
      background: rgba(0, 0, 0, 0.25);
      padding: 20pt;
      border-radius: 12pt;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
      margin-top: 25pt;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Enhanced PPTX</h1>
    <p>Auto-optimizations: gradient rasterization + CSS style migration</p>
  </div>
</body>
</html>`;

  const slide1Path = '/tmp/slide1-test.html';
  fs.writeFileSync(slide1Path, slide1Html);

  try {
    const { slide: slide1 } = await html2pptx(slide1Path, pptx);
    console.log('  ✅ Slide 1 created\n');
  } catch (error) {
    console.error('  ❌ Slide 1 failed:', error.message);
    throw error;
  }

  // Slide 2: Using design system
  console.log('📄 Creating Slide 2: Design System...');
  const { applyDesignSystem } = require('./skills/pptx/scripts/design_systems');

  const slide2Html = `
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
      padding: 50pt 60pt;
    }
    h1 {
      color: var(--color-primary);
      font-size: var(--font-h1-size);
      font-family: Arial, sans-serif;
      margin-bottom: var(--spacing-lg);
    }
    .card {
      background: var(--color-light);
      border-radius: var(--border-radius);
      box-shadow: var(--box-shadow);
      padding: var(--spacing-lg);
      border: 2pt solid var(--color-secondary);
    }
    p {
      color: var(--color-dark);
      font-size: var(--font-body-size);
      font-family: Arial, sans-serif;
      line-height: var(--font-body-line-height);
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Design System Demo</h1>
    <div class="card">
      <p>This slide uses the tech-modern design system with CSS variables.</p>
    </div>
  </div>
</body>
</html>`;

  const { modifiedHtml } = applyDesignSystem('tech-modern', slide2Html);
  const slide2Path = '/tmp/slide2-test.html';
  fs.writeFileSync(slide2Path, modifiedHtml);

  try {
    const { slide: slide2 } = await html2pptx(slide2Path, pptx);
    console.log('  ✅ Slide 2 created\n');
  } catch (error) {
    console.error('  ❌ Slide 2 failed:', error.message);
    throw error;
  }

  // Slide 3: Multiple elements with auto-migration
  console.log('📄 Creating Slide 3: Complex Layout...');
  const slide3Html = `
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
      background: #F4F6F6;
    }
    .container {
      display: flex;
      gap: 30pt;
      padding: 50pt 60pt;
    }
    .column {
      flex: 1;
    }
    h1 {
      font-size: 36pt;
      color: #1C2833;
      font-family: Arial, sans-serif;
      /* Auto-migrate */
      background: white;
      border: 2pt solid #3498DB;
      padding: 15pt;
      border-radius: 8pt;
    }
    ul {
      font-size: 16pt;
      color: #2E4053;
      font-family: Arial, sans-serif;
      /* Auto-migrate */
      background: rgba(255, 255, 255, 0.8);
      padding: 15pt;
      border-radius: 8pt;
    }
    li {
      margin: 8pt 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="column">
      <h1>Left Column</h1>
      <ul>
        <li>Item 1 with styled list</li>
        <li>Item 2</li>
        <li>Item 3</li>
      </ul>
    </div>
    <div class="column">
      <h1>Right Column</h1>
      <p style="font-size: 16pt; color: #2E4053; background: rgba(52, 152, 219, 0.1); padding: 15pt; border-radius: 8pt;">
        This is a paragraph with background that will be auto-migrated.
      </p>
    </div>
  </div>
</body>
</html>`;

  const slide3Path = '/tmp/slide3-test.html';
  fs.writeFileSync(slide3Path, slide3Html);

  try {
    const { slide: slide3 } = await html2pptx(slide3Path, pptx);
    console.log('  ✅ Slide 3 created\n');
  } catch (error) {
    console.error('  ❌ Slide 3 failed:', error.message);
    throw error;
  }

  // Save presentation
  console.log('💾 Saving presentation...');
  const outputPath = '/tmp/enhanced-pptx-demo.pptx';
  await pptx.writeFile({ fileName: outputPath });
  console.log(`✅ Presentation saved to: ${outputPath}\n`);

  // Summary
  console.log('=' .repeat(60));
  console.log('📊 Test Summary');
  console.log('=' .repeat(60));
  console.log('✅ Slide 1: Gradient rasterization + Text style migration');
  console.log('✅ Slide 2: Design system with CSS variables');
  console.log('✅ Slide 3: Complex layout with multiple styled elements');
  console.log('=' .repeat(60));
  console.log('🎉 All tests completed successfully!');
  console.log('=' .repeat(60));

  return outputPath;
}

// Run test
async function main() {
  try {
    const outputPath = await createPresentation();

    // Also test color conversion separately
    console.log('\n🔬 Testing color conversion...');
    const { convertColorFormat } = require('./skills/pptx/scripts/html2pptx');

    const tests = [
      ['#FF0000', 'FF0000'],
      ['#40695B', '40695B'],
      ['#B165FB', 'B165FB'],
      ['rgb(255, 0, 0)', 'FF0000']
    ];

    let allPassed = true;
    for (const [input, expected] of tests) {
      const result = convertColorFormat(input);
      if (result === expected) {
        console.log(`  ✅ ${input} → ${result}`);
      } else {
        console.log(`  ❌ ${input} → ${result} (expected ${expected})`);
        allPassed = false;
      }
    }

    if (allPassed) {
      console.log('\n✅ Color conversion test passed!');
    }

    return outputPath;
  } catch (error) {
    console.error('\n❌ Test failed:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(error => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { createPresentation };
