const fs = require('fs');

const filePath = '/tmp/pptx-p2-p3-demo.pptx';

if (fs.existsSync(filePath)) {
  const stats = fs.statSync(filePath);
  const buffer = fs.readFileSync(filePath);

  console.log('📄 File:', filePath);
  console.log('📏 Size:', (stats.size / 1024).toFixed(1), 'KB');
  console.log('📅 Created:', stats.mtime.toISOString());

  if (buffer[0] === 0x50 && buffer[1] === 0x4B) {
    console.log('✅ Valid PPTX file (ZIP)');
  } else {
    console.log('❌ Invalid PPTX file');
  }
} else {
  console.log('❌ File not found');
}
