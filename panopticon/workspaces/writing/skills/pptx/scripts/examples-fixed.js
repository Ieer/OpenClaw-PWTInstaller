/**
 * PPTX Enhanced Usage Examples - Fixed
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');
const { getDesignSystem, generateCSSVariables, listDesignSystems } = require('./design-systems');
const fs = require('fs');
const path = require('path');

// ==================== EXAMPLE 3: Pre-rendered Components (Fixed) ====================
async function example3_Components() {
  console.log('\n🧩 Example 3: Pre-rendered Components (Fixed)');

  // Generate component library
  const { generateComponentLibrary } = require('./component-library');
  const componentsDir = path.join(__dirname, '../../components');

  try {
    await generateComponentLibrary(componentsDir);
    console.log('  ✓ Component library generated');
  } catch (error) {
    console.error('  ✗ Component library failed:', error.message);
    return;
  }

  const html = `
<!DOCTYPE html>
<html>
<head>
<style>
body {
  width: 720pt; height: 405pt;
  background: #F8F9FA;
  font-family: Arial, sans-serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30pt;
}
.content {
  text-align: center;
}
h1 {
  font-size: 30pt;
  color: #181B24;
  margin: 0 0 20pt 0;
}
.cards {
  display: flex;
  gap: 15pt;
  width: 100%;
  justify-content: center;
}
.card {
  width: 180pt;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.card img {
  width: 100%;
  height: auto;
  border-radius: 6pt;
  margin-bottom: 8pt;
}
.button {
  margin-top: 15pt;
}
.button img {
  margin: 0;
}
</style>
</head>
<body>
<div class="content">
  <h1>Component Library</h1>
  <div class="cards">
    <div class="card">
      <img src="components/card-info.png" alt="Info card">
    </div>
    <div class="card">
      <img src="components/card-warning.png" alt="Warning card">
    </div>
    <div class="card">
      <img src="components/card-success.png" alt="Success card">
    </div>
  </div>
  <div class="button">
    <img src="components/button-primary.png" alt="Primary button" style="width: 150pt;">
  </div>
</div>
</body>
</html>`;

  const htmlFile = 'example3-components.html';
  fs.writeFileSync(htmlFile, html);

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  try {
    const { slide } = await html2pptx(htmlFile, pptx);
    await pptx.writeFile({ fileName: 'example3-components.pptx' });
    console.log('✓ Example 3 complete: example3-components.pptx');
  } catch (error) {
    console.error('✗ Example 3 failed:', error.message);
  }
}

// ==================== EXAMPLE 4: All Features Combined (Fixed) ====================
async function example4_AllFeatures() {
  console.log('\n🚀 Example 4: All Features Combined (Fixed)');

  const ds = getDesignSystem('business-professional');
  const css = generateCSSVariables(ds);

  const html = `
<!DOCTYPE html>
<html>
<head>
<style>
body {
  width: 720pt; height: 405pt;
  font-family: Arial, sans-serif;
  display: flex;
}
${css}
.sidebar {
  width: 180pt;
  background: linear-gradient(135deg, var(--color-dark) 0%, var(--color-secondary) 100%);
  padding: 24pt;
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: white;
}
.sidebar h2 {
  font-size: 28pt;
  margin: 0 0 12pt 0;
  color: var(--color-accent);
}
.sidebar p {
  font-size: 16pt;
  margin: 0;
  line-height: 1.4;
}
.main {
  flex: 1;
  padding: 24pt;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.card {
  background: white;
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  padding: 16pt;
  margin-bottom: 12pt;
}
.card h3 {
  font-size: 18pt;
  margin: 0 0 8pt 0;
  color: var(--color-primary);
}
.card p {
  font-size: 14pt;
  margin: 0;
  line-height: 1.4;
}
</style>
</head>
<body>
<div class="sidebar">
  <h2>Enhanced PPTX</h2>
  <p>Auto-gradients + Design System + Components</p>
</div>
<div class="main">
  <div class="card">
    <h3>✨ Auto Gradient Rasterization</h3>
    <p>CSS gradients are automatically converted to PNG images</p>
  </div>
  <div class="card">
    <h3>🎨 Design Systems</h3>
    <p>Pre-built professional color schemes and typography</p>
  </div>
  <div class="card">
    <h3>🧩 Component Library</h3>
    <p>Pre-rendered UI components ready to use</p>
  </div>
</div>
</body>
</html>`;

  const htmlFile = 'example4-all-features.html';
  fs.writeFileSync(htmlFile, html);

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  try {
    const { slide } = await html2pptx(htmlFile, pptx);
    await pptx.writeFile({ fileName: 'example4-all-features.pptx' });
    console.log('✓ Example 4 complete: example4-all-features.pptx');
  } catch (error) {
    console.error('✗ Example 4 failed:', error.message);
  }
}

// ==================== RUN FIXED EXAMPLES ====================
async function runFixedExamples() {
  console.log('========================================');
  console.log('PPTX Enhanced Examples (Fixed)');
  console.log('========================================');

  try {
    await example3_Components();
    await example4_AllFeatures();

    console.log('\n========================================');
    console.log('All examples completed! ✅');
    console.log('========================================');

    // List available design systems
    console.log('\n📋 Available Design Systems:');
    listDesignSystems().forEach((ds, i) => {
      console.log(`  ${i + 1}. ${ds}`);
    });

  } catch (error) {
    console.error('Error running examples:', error);
    process.exit(1);
  }
}

// Run examples if executed directly
if (require.main === module) {
  runFixedExamples().catch(console.error);
}

module.exports = {
  example3_Components,
  example4_AllFeatures,
  runFixedExamples
};
