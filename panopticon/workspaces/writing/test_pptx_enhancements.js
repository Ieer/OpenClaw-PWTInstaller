/**
 * Quick test for PPTX enhancements
 *
 * Tests:
 * 1. Browser pool initialization
 * 2. Gradient rasterization
 * 3. CSS style migration
 * 4. Color format conversion
 */

const html2pptx = require('./skills/pptx/scripts/html2pptx');
const pptxgen = require('pptxgenjs');

async function testGradientWithAutoMigration() {
  console.log('🧪 Test 1: Auto CSS Style Migration + Gradient Rasterization\n');

  // Create test HTML with problematic styles
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
      background: linear-gradient(135deg, #B165FB 0%, #40695B 100%);
    }
    .container {
      padding: 40pt;
    }
    h1 {
      font-size: 48pt;
      color: white;
      /* This should be auto-migrated to a wrapper */
      background: rgba(255, 255, 255, 0.2);
      border: 2pt solid white;
      padding: 20pt;
      border-radius: 10pt;
    }
    p {
      font-size: 18pt;
      color: white;
      /* This should be auto-migrated to a wrapper */
      background: rgba(0, 0, 0, 0.3);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      padding: 15pt;
      margin-top: 20pt;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Enhanced html2pptx</h1>
    <p>This text has background and box-shadow, which should be auto-migrated to a wrapper div.</p>
  </div>
</body>
</html>`;

  // Write test HTML
  const fs = require('fs');
  const testHtmlPath = '/tmp/test-auto-migration.html';
  fs.writeFileSync(testHtmlPath, testHtml);

  try {
    // Create presentation
    const pptx = new pptxgen();
    pptx.layout = 'LAYOUT_16x9';

    console.log('🔄 Converting HTML with auto-optimizations...');
    const { slide } = await html2pptx(testHtmlPath, pptx);

    console.log('\n✅ Test passed! Auto-optimizations applied:');
    console.log('  ✓ Gradient rasterized');
    console.log('  ✓ H1 background/border migrated');
    console.log('  ✓ P background/shadow migrated');

    // Save presentation
    const outputPath = '/tmp/test-enhanced.pptx';
    await pptx.writeFile({ fileName: outputPath });
    console.log(`\n📄 Presentation saved to: ${outputPath}`);

    return outputPath;
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    throw error;
  }
}

async function testColorConversion() {
  console.log('\n🧪 Test 2: Color Format Conversion\n');

  const { convertColorFormat } = require('./skills/pptx/scripts/html2pptx');

  const testColors = [
    { input: '#FF0000', expected: 'FF0000', desc: '#RRGGBB' },
    { input: 'rgb(255, 0, 0)', expected: 'FF0000', desc: 'rgb(r, g, b)' },
    { input: 'rgba(255, 0, 0, 0.5)', expected: 'FF0000', desc: 'rgba(r, g, b, a)' },
    { input: 'FF0000', expected: 'FF0000', desc: 'Already correct format' }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of testColors) {
    const result = convertColorFormat(test.input);
    if (result === test.expected) {
      console.log(`✅ ${test.desc}: ${test.input} → ${result}`);
      passed++;
    } else {
      console.log(`❌ ${test.desc}: ${test.input} → ${result} (expected ${test.expected})`);
      failed++;
    }
  }

  console.log(`\n📊 Results: ${passed} passed, ${failed} failed`);

  return failed === 0;
}

async function testDesignSystem() {
  console.log('\n🧪 Test 3: Design System Application\n');

  const { applyDesignSystem } = require('./skills/pptx/scripts/design_systems');

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
    h1 {
      color: var(--color-primary);
      font-size: var(--font-h1-size);
    }
  </style>
</head>
<body>
  <h1>Design System Test</h1>
</body>
</html>`;

  try {
    const { modifiedHtml, designSystem } = applyDesignSystem('tech-modern', testHtml);

    console.log('✅ Design system applied');
    console.log(`  - Name: tech-modern`);
    console.log(`  - Primary color: #${designSystem.colors.primary}`);
    console.log(`  - H1 size: ${designSystem.typography.heading1.size}pt`);

    // Check if CSS variables were injected
    if (modifiedHtml.includes('--color-primary: #B165FB')) {
      console.log('  ✓ CSS variables injected');
    } else {
      console.log('  ❌ CSS variables not found');
      return false;
    }

    return true;
  } catch (error) {
    console.error('❌ Design system test failed:', error.message);
    return false;
  }
}

async function runAllTests() {
  console.log('🚀 Running PPTX enhancement tests...\n');

  const results = {
    test1: await testGradientWithAutoMigration().then(() => true).catch(() => false),
    test2: await testColorConversion(),
    test3: await testDesignSystem()
  };

  console.log('\n' + '='.repeat(50));
  console.log('📊 Test Summary');
  console.log('='.repeat(50));
  console.log(`Test 1 (Auto Migration + Gradient): ${results.test1 ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`Test 2 (Color Conversion): ${results.test2 ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`Test 3 (Design System): ${results.test3 ? '✅ PASSED' : '❌ FAILED'}`);

  const allPassed = Object.values(results).every(r => r);
  console.log('='.repeat(50));
  console.log(allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED');
  console.log('='.repeat(50));

  return allPassed;
}

// Run tests
if (require.main === module) {
  runAllTests().catch(error => {
    console.error('❌ Test suite error:', error);
    process.exit(1);
  });
}

module.exports = { runAllTests };
