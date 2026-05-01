/**
 * Verify PPTX file structure
 */

const fs = require('fs');
const path = require('path');

function verifyPptx(filePath) {
  console.log(`🔍 Verifying PPTX file: ${filePath}\n`);

  // Check if file exists
  if (!fs.existsSync(filePath)) {
    console.log('❌ File does not exist');
    return false;
  }

  const stats = fs.statSync(filePath);
  console.log(`📄 File size: ${(stats.size / 1024).toFixed(1)} KB`);
  console.log(`📅 Created: ${stats.mtime.toISOString()}`);

  // Check if it's a valid ZIP file (PPTX is a ZIP)
  const buffer = fs.readFileSync(filePath);

  // ZIP files start with PK (0x504B)
  if (buffer[0] === 0x50 && buffer[1] === 0x4B) {
    console.log('✅ Valid ZIP signature (PPTX format)');

    // Try to extract minimal info
    let slideCount = 0;
    let content = buffer.toString('utf8', 0, Math.min(buffer.length, 10000));

    // Count slide references
    const slideMatches = content.match(/slide\d+\.xml/g);
    if (slideMatches) {
      slideCount = new Set(slideMatches).size;
      console.log(`📊 Estimated slides: ${slideCount}`);
    }

    return true;
  } else {
    console.log('❌ Invalid PPTX file (not a ZIP)');
    return false;
  }
}

// Verify the generated file
verifyPptx('/tmp/enhanced-pptx-demo.pptx');
verifyPptx('/tmp/test-enhanced.pptx');
verifyPptx('/tmp/test-basic.pptx');
