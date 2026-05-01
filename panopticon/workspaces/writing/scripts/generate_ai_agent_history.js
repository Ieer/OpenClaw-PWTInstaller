/**
 * Generate AI Agent History PPT using enhanced html2pptx
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./skills/pptx/scripts/html2pptx');
const fs = require('fs');
const path = require('path');

async function generatePPT() {
  console.log('🚀 Generating AI Agent History PPT with enhanced html2pptx v2.0...\n');

  // Create presentation
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';  // 720pt × 405pt
  pptx.author = 'Ink Relay';
  pptx.title = 'AI Agent 发展史';
  pptx.subject = 'AI Agent History';

  // Get all slide HTML files
  const slidesDir = path.join(__dirname, 'slides');
  const slideFiles = fs.readdirSync(slidesDir)
    .filter(f => f.startsWith('slide') && f.endsWith('.html'))
    .sort();

  console.log(`📊 Found ${slideFiles.length} slides\n`);

  // Process each slide
  for (let i = 0; i < slideFiles.length; i++) {
    const slideFile = slideFiles[i];
    const slidePath = path.join(slidesDir, slideFile);
    const slideNum = i + 1;

    console.log(`📄 Processing Slide ${slideNum}/${slideFiles.length}: ${slideFile}...`);

    try {
      // Convert HTML to slide
      const { slide } = await html2pptx(slidePath, pptx);

      console.log(`  ✅ Slide ${slideNum} created\n`);
    } catch (error) {
      console.error(`  ❌ Slide ${slideNum} failed:`, error.message);
      console.error(`     File: ${slideFile}`);
      throw error;
    }
  }

  // Save presentation
  console.log('💾 Saving presentation...');
  const outputPath = path.join(__dirname, 'ai_agent_history_v2.pptx');
  await pptx.writeFile({ fileName: outputPath });
  console.log(`✅ Presentation saved to: ${outputPath}\n`);

  // Summary
  console.log('=' .repeat(60));
  console.log('📊 Summary');
  console.log('=' .repeat(60));
  console.log(`✅ Total slides: ${slideFiles.length}`);
  console.log(`📄 File: ${outputPath}`);
  
  // Get file stats
  const stats = fs.statSync(outputPath);
  console.log(`📏 Size: ${(stats.size / 1024).toFixed(1)} KB`);
  console.log(`🎨 Version: html2pptx v2.0 (enhanced)`);
  console.log('='.repeat(60));

  return outputPath;
}

// Run generator
async function main() {
  try {
    const outputPath = await generatePPT();
    
    console.log('\n✨ AI Agent History PPT generated successfully!\n');
    console.log('🎯 Features used (auto-enabled):');
    console.log('  ✓ Auto gradient rasterization');
    console.log('  ✓ Auto CSS style migration');
    console.log('  ✓ Auto color format conversion');
    console.log('  ✓ Browser pool (for batch performance)');
    
    return outputPath;
  } catch (error) {
    console.error('\n❌ Generation failed:', error.message);
    console.error('\nStack trace:', error.stack);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { generatePPT };
