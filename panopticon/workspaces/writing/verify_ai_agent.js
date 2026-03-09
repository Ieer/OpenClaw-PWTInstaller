const fs = require('fs');

function verifyPptx(filePath) {
  console.log(`🔍 Verifying: ${filePath}`);

  if (!fs.existsSync(filePath)) {
    console.log('❌ File does not exist\n');
    return false;
  }

  const stats = fs.statSync(filePath);
  console.log(`📄 Size: ${(stats.size / 1024).toFixed(1)} KB`);
  console.log(`📅 Created: ${stats.mtime.toISOString()}`);

  const buffer = fs.readFileSync(filePath);

  // Check ZIP signature
  if (buffer[0] === 0x50 && buffer[1] === 0x4B) {
    console.log('✅ Valid ZIP signature (PPTX format)');

    // Count slides
    let content = buffer.toString('utf8', 0, Math.min(buffer.length, 50000));
    const slideMatches = content.match(/slide\d+\.xml/g);
    if (slideMatches) {
      const slideCount = new Set(slideMatches).size;
      console.log(`📊 Slides: ${slideCount}\n`);
    }

    return true;
  } else {
    console.log('❌ Invalid PPTX file\n');
    return false;
  }
}

verifyPptx('/home/node/.openclaw/workspace/ai_agent_history_v2.pptx');
verifyPptx('/home/node/.openclaw/workspace/ai_agent_history.pptx'); // Old version
