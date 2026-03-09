/**
 * PPTX Enhanced Usage Examples
 * Demonstrating new features: auto-gradients, design systems, components
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');
const { getDesignSystem, generateCSSVariables, listDesignSystems } = require('./design-systems');
const fs = require('fs');
const path = require('path');

// ==================== EXAMPLE 1: Auto Gradient Rasterization ====================
async function example1_AutoGradient() {
  console.log('\n📊 Example 1: Auto Gradient Rasterization');

  const html = `
<!DOCTYPE html>
<html>
<head>
<style>
body {
  width: 720pt; height: 405pt;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Arial, sans-serif;
}
.content {
  text-align: center;
  color: white;
}
h1 {
  font-size: 48pt;
  margin: 0 0 20pt 0;
  color: white;
}
p {
  font-size: 18pt;
  color: white;
  margin: 0;
}
.card {
  width: 400pt;
  height: 200pt;
  background: linear-gradient(135deg, #B165FB 0%, #40695B 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12pt;
  padding: 40pt;
}
</style>
</head>
<body>
<div class="card">
  <div class="content">
    <h1>Auto Gradient</h1>
    <p>CSS gradients are automatically rasterized to PNG!</p>
  </div>
</div>
</body>
</html>`;

  const htmlFile = 'example1-gradient.html';
  fs.writeFileSync(htmlFile, html);

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  try {
    const { slide } = await html2pptx(htmlFile, pptx);
    await pptx.writeFile({ fileName: 'example1-gradient.pptx' });
    console.log('✓ Example 1 complete: example1-gradient.pptx');
  } catch (error) {
    console.error('✗ Example 1 failed:', error.message);
  }
}

// ==================== EXAMPLE 2: Design System ====================
async function example2_DesignSystem() {
  console.log('\n🎨 Example 2: Design System');

  // Get design system
  const ds = getDesignSystem('tech-modern');
  const css = generateCSSVariables(ds);

  // Create HTML with design system
  const html = `
<!DOCTYPE html>
<html>
<head>
<style>
body {
  width: 720pt; height: 405pt;
  background: #${ds.colors.light};
  font-family: Arial, sans-serif;
  display: flex;
  flex-direction: column;
}
${css}
.header {
  background: var(--color-dark);
  padding: var(--spacing-md) var(--spacing-lg);
}
.header h1 {
  font-size: var(--font-h1-size);
  font-weight: var(--font-h1-weight);
  line-height: var(--font-h1-line-height);
  color: var(--color-primary);
  margin: 0;
}
.content {
  padding: var(--spacing-lg);
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card {
  background: white;
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  padding: var(--spacing-xl);
  width: 500pt;
}
.card h2 {
  font-size: var(--font-h2-size);
  font-weight: var(--font-h2-weight);
  color: var(--color-secondary);
  margin: 0 0 var(--spacing-md) 0;
}
.card p {
  font-size: var(--font-body-size);
  font-weight: var(--font-body-weight);
  line-height: var(--font-body-line-height);
  color: var(--color-dark);
  margin: 0;
}
</style>
</head>
<body>
<div class="header">
  <h1>Design System</h1>
</div>
<div class="content">
  <div class="card">
    <h2>Tech Modern Theme</h2>
    <p>Using CSS variables for consistent styling across all slides.</p>
  </div>
</div>
</body>
</html>`;

  const htmlFile = 'example2-design-system.html';
  fs.writeFileSync(htmlFile, html);

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  try {
    const { slide } = await html2pptx(htmlFile, pptx);
    await pptx.writeFile({ fileName: 'example2-design-system.pptx' });
    console.log('✓ Example 2 complete: example2-design-system.pptx');
  } catch (error) {
    console.error('✗ Example 2 failed:', error.message);
  }
}

// ==================== EXAMPLE 3: Pre-rendered Components ====================
async function example3_Components() {
  console.log('\n🧩 Example 3: Pre-rendered Components');

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
  padding: 40pt;
}
.content {
  text-align: center;
}
h1 {
  font-size: 36pt;
  color: #181B24;
  margin: 0 0 30pt 0;
}
.cards {
  display: flex;
  gap: 20pt;
}
.card {
  width: 200pt;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.card img {
  width: 100%;
  height: auto;
  border-radius: 8pt;
  margin-bottom: 10pt;
}
.button {
  margin-top: 20pt;
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
    <img src="components/button-primary.png" alt="Primary button">
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

// ==================== EXAMPLE 4: All Features Combined ====================
async function example4_AllFeatures() {
  console.log('\n🚀 Example 4: All Features Combined');

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
  width: 200pt;
  background: linear-gradient(135deg, var(--color-dark) 0%, var(--color-secondary) 100%);
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: white;
}
.sidebar h2 {
  font-size: var(--font-h2-size);
  margin: 0 0 var(--spacing-md) 0;
  color: var(--color-accent);
}
.sidebar p {
  font-size: var(--font-body-size);
  margin: 0;
}
.main {
  flex: 1;
  padding: var(--spacing-xl);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.card {
  background: white;
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
}
.card h3 {
  font-size: var(--font-h3-size);
  margin: 0 0 var(--spacing-sm) 0;
  color: var(--color-primary);
}
.card p {
  font-size: var(--font-body-size);
  margin: 0;
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

// ==================== RUN ALL EXAMPLES ====================
async function runAllExamples() {
  console.log('========================================');
  console.log('PPTX Enhanced Examples');
  console.log('========================================');

  try {
    await example1_AutoGradient();
    await example2_DesignSystem();
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
  runAllExamples().catch(console.error);
}

module.exports = {
  example1_AutoGradient,
  example2_DesignSystem,
  example3_Components,
  example4_AllFeatures,
  runAllExamples
};
