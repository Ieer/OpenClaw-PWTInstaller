/**
 * Simple Chart Beautification Test
 */

const pptxgen = require('pptxgenjs');
const { createBeautifiedChart } = require('/home/node/.openclaw/workspace/skills/pptx/scripts/chart_beautification');

async function main() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  const slide = pptx.addSlide();

  // Test beautified chart
  const data = [
    { name: 'Q1', labels: ['Sales', 'Profit'], values: [100, 25] },
    { name: 'Q2', labels: ['Sales', 'Profit'], values: [120, 30] },
    { name: 'Q3', labels: ['Sales', 'Profit'], values: [150, 40] },
    { name: 'Q4', labels: ['Sales', 'Profit'], values: [180, 50] }
  ];

  const chartData = createBeautifiedChart(data, 'bar', 'modern-minimal');

  console.log('Chart data:', JSON.stringify(chartData, null, 2));

  slide.addChart('bar', data, {
    x: 1, y: 1, w: 8, h: 4,
    chartColors: chartData.chartColors,
    showLegend: chartData.showLegend
  });

  await pptx.writeFile({ fileName: '/tmp/test-beautified-chart.pptx' });
  console.log('✅ Beautified chart test saved');
}

main().catch(console.error);
