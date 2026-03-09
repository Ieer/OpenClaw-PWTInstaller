/**
 * Example: Pre-rendered Components & Chart Beautification (Fixed)
 *
 * Demonstrates P2 and P3 optimizations:
 * - Pre-rendered component library
 * - Smart chart beautification
 */

const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');
const {
  createButton,
  createCard,
  createInfoBox,
  createBadge,
  createIconPlaceholder,
  getCacheStats
} = require('./pre_rendered_components');
const {
  createBeautifiedChart,
  autoSelectPreset,
  getAvailablePresets
} = require('./chart_beautification');

async function main() {
  console.log('🎨 PPTX P2-P3 Optimization Demo\n');

  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';
  pptx.author = 'Ink Relay';
  pptx.title = 'P2-P3 Optimization Demo';

  // ============================================
  // Slide 1: Pre-rendered Components
  // ============================================
  console.log('📄 Creating Slide 1: Pre-rendered Components...');
  const slide1 = pptx.addSlide();

  // Create components
  const buttonPath = await createButton(200, 50, 'Get Started', {
    backgroundColor: 'B165FB',
    textColor: 'FFFFFF',
    fontSize: 18
  });
  console.log('  ✓ Button created:', buttonPath);

  const cardPath = await createCard(300, 200, {
    backgroundColor: 'FFFFFF',
    borderColor: '40695B',
    borderWidth: 2
  });
  console.log('  ✓ Card created:', cardPath);

  const infoBoxPath = await createInfoBox(400, 80, 'Key Feature: Auto-optimization enabled', {
    backgroundColor: 'F8F9FA',
    borderColor: '40695B',
    borderWidth: 4
  });
  console.log('  ✓ Info box created:', infoBoxPath);

  const badgePath = await createBadge(120, 32, 'NEW', {
    backgroundColor: '28A745',
    textColor: 'FFFFFF'
  });
  console.log('  ✓ Badge created:', badgePath);

  const iconPath = await createIconPlaceholder(80, 'A', {
    backgroundColor: 'B165FB'
  });
  console.log('  ✓ Icon created:', iconPath);

  // Add components to slide
  slide1.addImage({ path: buttonPath, x: 1, y: 1, w: 2.5, h: 0.7 });
  slide1.addImage({ path: cardPath, x: 4, y: 1, w: 4, h: 2.5 });
  slide1.addImage({ path: infoBoxPath, x: 1, y: 3, w: 5, h: 1 });
  slide1.addImage({ path: badgePath, x: 7.5, y: 0.5, w: 1.5, h: 0.45 });
  slide1.addImage({ path: iconPath, x: 0.2, y: 0.2, w: 1, h: 1 });

  // Add title
  slide1.addText('Pre-rendered Components', {
    x: 0.2, y: 1.5, w: 4, h: 0.5,
    fontSize: 32,
    color: 'B165FB',
    bold: true
  });

  console.log('  ✅ Slide 1 created\n');

  // ============================================
  // Slide 2: Beautified Charts
  // ============================================
  console.log('📄 Creating Slide 2: Beautified Charts...');
  const slide2 = pptx.addSlide();

  // Chart data
  const data = [
    { name: 'Q1', labels: ['Sales', 'Profit'], values: [100, 25] },
    { name: 'Q2', labels: ['Sales', 'Profit'], values: [120, 30] },
    { name: 'Q3', labels: ['Sales', 'Profit'], values: [150, 40] },
    { name: 'Q4', labels: ['Sales', 'Profit'], values: [180, 50] }
  ];

  // Auto-select preset
  const autoPreset = autoSelectPreset(data, 'bar');
  console.log(`  ✓ Auto-selected preset: ${autoPreset}`);

  // Create beautified chart options
  const chartData = createBeautifiedChart(data, 'bar', autoPreset);

  // Add chart with beautified options
  slide2.addChart('bar', data, {
    x: 1, y: 0.5, w: 8, h: 4,
    chartColors: chartData.chartColors,
    showLegend: chartData.showLegend,
    dataLabelPosition: chartData.dataLabelPosition,
    barGrouping: chartData.barGrouping,
    gridLine: chartData.gridLine,
    axisLineColor: chartData.axisLineColor,
    dataLabelFontFace: chartData.dataLabelFontFace,
    dataLabelFontSize: chartData.dataLabelFontSize
  });

  // Add title
  slide2.addText('Smart Chart Beautification', {
    x: 1, y: 4.6, w: 8, h: 0.4,
    fontSize: 20,
    color: '181B24',
    bold: true,
    align: 'center'
  });

  // Add subtitle
  slide2.addText(`Preset: ${autoPreset} (auto-selected)`, {
    x: 1, y: 5, w: 8, h: 0.2,
    fontSize: 14,
    color: '40695B',
    align: 'center'
  });

  console.log('  ✅ Slide 2 created\n');

  // ============================================
  // Slide 3: Component Gallery
  // ============================================
  console.log('📄 Creating Slide 3: Component Gallery...');
  const slide3 = pptx.addSlide();

  // Create more components
  const calloutPath = await createButton(250, 60, 'Call to Action', {
    backgroundColor: 'FF6B9D',
    textColor: 'FFFFFF',
    fontSize: 16
  });
  console.log('  ✓ Callout button created');

  const card2Path = await createCard(350, 180, {
    backgroundColor: 'E7F3FF',
    borderColor: 'B165FB',
    borderWidth: 3
  });
  console.log('  ✓ Blue card created');

  const icon2Path = await createIconPlaceholder(60, '★', {
    backgroundColor: 'FFC107'
  });
  console.log('  ✓ Star icon created');

  // Add to slide
  slide3.addImage({ path: calloutPath, x: 1, y: 0.8, w: 3, h: 0.8 });
  slide3.addImage({ path: card2Path, x: 4.5, y: 0.8, w: 4.5, h: 2.2 });
  slide3.addImage({ path: icon2Path, x: 7.8, y: 0.2, w: 1, h: 1 });

  // Add title
  slide3.addText('Component Gallery', {
    x: 0.2, y: 3.5, w: 9.6, h: 0.5,
    fontSize: 32,
    color: 'B165FB',
    bold: true
  });

  // Add description
  slide3.addText('All components are pre-rendered as PNG for perfect PPTX compatibility', {
    x: 0.2, y: 4, w: 9.6, h: 0.6,
    fontSize: 16,
    color: '181B24',
    align: 'center'
  });

  console.log('  ✅ Slide 3 created\n');

  // ============================================
  // Save presentation
  // ============================================
  console.log('💾 Saving presentation...');
  const outputPath = '/tmp/pptx-p2-p3-demo.pptx';
  await pptx.writeFile({ fileName: outputPath });
  console.log(`✅ Presentation saved to: ${outputPath}\n`);

  // ============================================
  // Cache statistics
  // ============================================
  console.log('📊 Component Cache Statistics:');
  const cacheStats = getCacheStats();
  console.log(`  - Cached components: ${cacheStats.size}`);
  cacheStats.keys.forEach((key, index) => {
    console.log(`  ${index + 1}. ${key}`);
  });

  console.log('\n' + '=' .repeat(60));
  console.log('📊 Summary');
  console.log('=' .repeat(60));
  console.log('✅ Slide 1: Pre-rendered components (button, card, info box, badge, icon)');
  console.log('✅ Slide 2: Auto-selected chart preset (modern-minimal)');
  console.log('✅ Slide 3: Component gallery with multiple styles');
  console.log('✅ Component cache: ' + cacheStats.size + ' items cached');
  console.log('=' .repeat(60));
  console.log('🎉 P2-P3 optimization demo completed!');
  console.log('=' .repeat(60));

  return outputPath;
}

// Run example
async function run() {
  try {
    const outputPath = await main();
    return outputPath;
  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  run();
}

module.exports = { main, run };
