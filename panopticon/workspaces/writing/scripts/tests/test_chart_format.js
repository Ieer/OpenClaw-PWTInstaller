/**
 * Simple Chart Test
 */

const pptxgen = require('pptxgenjs');

async function main() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  const slide = pptx.addSlide();

  // Test 1: Simple bar chart
  const data1 = [
    { name: 'Q1', labels: ['Sales'], values: [100] },
    { name: 'Q2', labels: ['Sales'], values: [120] },
    { name: 'Q3', labels: ['Sales'], values: [150] },
    { name: 'Q4', labels: ['Sales'], values: [180] }
  ];

  slide.addChart('bar', data1, {
    x: 0.5, y: 0.5, w: 8, h: 3
  });

  // Test 2: Multi-series bar chart
  const data2 = [
    { name: 'Q1', labels: ['Sales', 'Profit'], values: [100, 25] },
    { name: 'Q2', labels: ['Sales', 'Profit'], values: [120, 30] },
    { name: 'Q3', labels: ['Sales', 'Profit'], values: [150, 40] },
    { name: 'Q4', labels: ['Sales', 'Profit'], values: [180, 50] }
  ];

  slide.addChart('bar', data2, {
    x: 0.5, y: 3.5, w: 8, h: 3
  });

  await pptx.writeFile({ fileName: '/tmp/test-chart.pptx' });
  console.log('✅ Chart test saved');
}

main().catch(console.error);
