/**
 * Enhanced html2pptx Usage Example
 *
 * Demonstrates all new features:
 * - Auto gradient rasterization
 * - Auto CSS style migration
 * - Auto color format conversion
 * - Browser pool
 * - Design systems
 */

const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const html2pptx = require('./html2pptx');
const { applyDesignSystem } = require('./design_systems');

async function main() {
  console.log('🎨 Creating presentation with enhanced html2pptx...\n');

  // Create presentation
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';  // 720pt × 405pt
  pptx.author = 'Ink Relay';
  pptx.title = 'Enhanced html2pptx Demo';

  // Read HTML template
  const htmlPath = path.join(__dirname, '../../example1-gradient.html');
  let htmlContent = fs.readFileSync(htmlPath, 'utf-8');

  // OPTIONAL: Apply design system
  console.log('📋 Applying design system: tech-modern');
  const { modifiedHtml } = applyDesignSystem('tech-modern', htmlContent);

  // Write modified HTML
  const tmpHtmlPath = '/tmp/slide-enhanced.html';
  fs.writeFileSync(tmpHtmlPath, modifiedHtml);

  // Convert to PPTX (auto-optimizations are applied automatically)
  console.log('🔄 Converting HTML to PPTX...');
  const { slide } = await html2pptx(tmpHtmlPath, pptx);

  console.log('\n✨ Auto-optimizations applied:');
  console.log('  ✓ Auto gradient rasterization (CSS gradients → PNG)');
  console.log('  ✓ Auto CSS style migration (text element styles → wrapper divs)');
  console.log('  ✓ Auto color format conversion (#RRGGBB → RRGGBB)');
  console.log('  ✓ Browser pool (reused for performance)');

  // Add a second slide (demonstrates browser pool reuse)
  console.log('\n📄 Adding second slide...');
  const { slide: slide2 } = await html2pptx(
    path.join(__dirname, '../../example2-design-system.html'),
    pptx
  );

  // Save presentation
  const outputPath = '/tmp/enhanced-presentation.pptx';
  await pptx.writeFile({ fileName: outputPath });
  console.log(`\n✅ Presentation saved to: ${outputPath}`);

  // Summary
  console.log('\n📊 Summary:');
  console.log('  - Total slides: 2');
  console.log('  - Design system: tech-modern');
  console.log('  - Auto-optimizations: enabled');
  console.log('  - Browser pool: active');

  return outputPath;
}

// Run example
if (require.main === module) {
  main().catch(error => {
    console.error('❌ Error:', error);
    process.exit(1);
  });
}

module.exports = main;
