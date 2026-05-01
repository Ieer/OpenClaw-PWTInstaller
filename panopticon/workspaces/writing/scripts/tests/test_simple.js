/**
 * Simple test for PPTX enhancements
 */

async function testColorConversion() {
  console.log('🧪 Test: Color Format Conversion\n');

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
  console.log('\n🧪 Test: Design System Application\n');

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

async function main() {
  console.log('🚀 Running PPTX enhancement tests...\n');

  const results = {
    test1: await testColorConversion(),
    test2: await testDesignSystem()
  };

  console.log('\n' + '='.repeat(50));
  console.log('📊 Test Summary');
  console.log('='.repeat(50));
  console.log(`Test 1 (Color Conversion): ${results.test1 ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`Test 2 (Design System): ${results.test2 ? '✅ PASSED' : '❌ FAILED'}`);

  const allPassed = Object.values(results).every(r => r);
  console.log('='.repeat(50));
  console.log(allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED');
  console.log('='.repeat(50));

  return allPassed;
}

main().catch(error => {
  console.error('❌ Test suite error:', error);
  process.exit(1);
});
