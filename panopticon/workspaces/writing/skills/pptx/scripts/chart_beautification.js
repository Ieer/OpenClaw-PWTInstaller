/**
 * Smart Chart Beautification for PPTX
 *
 * Provides pre-defined chart styling presets and auto-beautification
 */

// Chart types (use string identifiers)
const ChartType = {
  bar: 'bar',
  line: 'line',
  pie: 'pie',
  scatter: 'scatter'
};

// Color palettes for charts
const chartPalettes = {
  'modern-minimal': {
    name: 'Modern Minimal',
    description: 'Clean design with single accent color',
    colors: ['4472C4', 'ED7D31', 'A5A5A5', 'FFC000', '5B9BD5'],
    axisColor: '404040',
    gridColor: 'D9D9D9',
    fontFamily: 'Arial'
  },

  'professional': {
    name: 'Professional',
    description: 'Corporate-friendly color scheme',
    colors: ['1F4E79', 'C0504D', '9BBB59', '8064A2', '4BACC6'],
    axisColor: '404040',
    gridColor: 'E0E0E0',
    fontFamily: 'Calibri'
  },

  'vibrant': {
    name: 'Vibrant',
    description: 'Bold and colorful for engaging presentations',
    colors: ['FF6B9D', 'B165FB', '40695B', 'FFC107', '28A745'],
    axisColor: '333333',
    gridColor: 'EEEEEE',
    fontFamily: 'Arial'
  },

  'tech': {
    name: 'Tech',
    description: 'Modern tech-inspired colors',
    colors: ['00D4FF', '7C3AED', 'F472B6', '34D399', 'FBBF24'],
    axisColor: '1A1A2E',
    gridColor: '2D2D44',
    fontFamily: 'Segoe UI'
  },

  'monochrome': {
    name: 'Monochrome',
    description: 'Single color with varying intensities',
    colors: ['1C2833', '2E4053', '5D6D7E', 'AAB7B8', 'D5DBDB'],
    axisColor: '2E4053',
    gridColor: 'E0E0E0',
    fontFamily: 'Arial'
  }
};

/**
 * Apply chart beautification preset
 *
 * @param {Object} chartData - Chart data object
 * @param {Object} chart - PptxGenJS chart object (optional, not used)
 * @param {string} presetName - Name of the preset to apply
 * @returns {Object} Updated chartData object
 */
function beautifyChart(chartData, chart, presetName = 'modern-minimal') {
  const preset = chartPalettes[presetName];

  if (!preset) {
    console.warn(`Chart preset not found: ${presetName}. Using 'modern-minimal'.`);
    return beautifyChart(chartData, chart, 'modern-minimal');
  }

  console.log(`📊 Applying chart preset: ${preset.name}`);

  // Apply color scheme
  if (!chartData.chartColors && preset.colors) {
    chartData.chartColors = preset.colors;
  }

  // Apply styling based on chart type
  const chartType = chartData.type || chartData.chartType;
  switch (chartType) {
    case 'bar':
    case ChartType.bar:
      beautifyBarChart(chartData, preset);
      break;
    case 'line':
    case ChartType.line:
      beautifyLineChart(chartData, preset);
      break;
    case 'pie':
    case ChartType.pie:
      beautifyPieChart(chartData, preset);
      break;
    case 'scatter':
    case ChartType.scatter:
      beautifyScatterChart(chartData, preset);
      break;
  }

  return chartData;
}

/**
 * Beautify bar chart
 */
function beautifyBarChart(chartData, preset) {
  // Data labels
  if (chartData.showLegend === undefined) {
    chartData.showLegend = false;
  }
  if (chartData.dataLabelPosition === undefined) {
    chartData.dataLabelPosition = 'outEnd';
  }

  // Bar styling
  chartData.barGrouping = 'clustered';

  // Grid
  chartData.gridLine = {
    color: preset.gridColor,
    size: 1
  };

  // Axis
  chartData.axisLineColor = preset.axisColor;

  // Font
  chartData.dataLabelFontFace = preset.fontFamily;
  chartData.dataLabelFontSize = 11;
}

/**
 * Beautify line chart
 */
function beautifyLineChart(chartData, preset) {
  // Smooth curves
  chartData.smooth = true;

  // Line width
  if (chartData.lineSize === undefined) {
    chartData.lineSize = 3;
  }

  // Data markers
  if (chartData.lineMarker === undefined) {
    chartData.lineMarker = {
      symbol: 'circle',
      size: 6
    };
  }

  // Grid
  chartData.gridLine = {
    color: preset.gridColor,
    size: 1
  };

  // Axis
  chartData.axisLineColor = preset.axisColor;

  // Data labels
  if (chartData.showLegend === undefined) {
    chartData.showLegend = false;
  }
}

/**
 * Beautify pie chart
 */
function beautifyPieChart(chartData, preset) {
  // Data labels
  if (chartData.dataLabelPosition === undefined) {
    chartData.dataLabelPosition = 'bestFit';
  }

  // Legend
  if (chartData.showLegend === undefined) {
    chartData.showLegend = true;
    chartData.legendPos = 'r';
  }

  // No grid or axis for pie charts
  chartData.showGridLines = false;
  chartData.showAxis = false;
}

/**
 * Beautify scatter chart
 */
function beautifyScatterChart(chartData, preset) {
  // Marker size
  if (chartData.lineMarker === undefined) {
    chartData.lineMarker = {
      symbol: 'circle',
      size: 8
    };
  }

  // Grid
  chartData.gridLine = {
    color: preset.gridColor,
    size: 1
  };

  // Axis
  chartData.axisLineColor = preset.axisColor;

  // No legend by default
  if (chartData.showLegend === undefined) {
    chartData.showLegend = false;
  }
}

/**
 * Create optimized chart data with beautification
 *
 * @param {Array} data - Data array
 * @param {string} type - Chart type ('bar', 'line', 'pie', 'scatter')
 * @param {string} preset - Beautification preset
 * @returns {Object} Chart data object
 */
function createBeautifiedChart(data, type, preset = 'modern-minimal') {
  const chartData = {
    data: data,
    type: type
  };

  // Apply preset
  beautifyChart(chartData, null, preset);

  return chartData;
}

/**
 * Get list of available presets
 */
function getAvailablePresets() {
  return Object.keys(chartPalettes).map(key => ({
    name: key,
    displayName: chartPalettes[key].name,
    description: chartPalettes[key].description
  }));
}

/**
 * Get preset details
 */
function getPreset(presetName) {
  return chartPalettes[presetName] || chartPalettes['modern-minimal'];
}

/**
 * Auto-select preset based on data characteristics
 *
 * @param {Array} data - Chart data
 * @param {string} chartType - Chart type
 * @returns {string} Recommended preset
 */
function autoSelectPreset(data, chartType) {
  // Count data series
  const seriesCount = Array.isArray(data[0]) ? data.length : 1;

  // Check data range (for determining complexity)
  let hasWideRange = false;
  if (chartType === 'bar' || chartType === 'line') {
    const allValues = data.flat();
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    hasWideRange = (max / min) > 10;
  }

  // Select based on characteristics
  if (seriesCount > 3) {
    return 'vibrant';  // Many series need distinct colors
  } else if (hasWideRange) {
    return 'professional';  // Complex data needs clean design
  } else if (chartType === 'pie') {
    return 'modern-minimal';  // Pie charts work best with minimal design
  } else {
    return 'modern-minimal';  // Default
  }
}

// Export all functions
module.exports = {
  chartPalettes,
  beautifyChart,
  createBeautifiedChart,
  getAvailablePresets,
  getPreset,
  autoSelectPreset
};

/**
 * Usage example:
 *
 * const { createBeautifiedChart, autoSelectPreset } = require('./chart_beautification');
 * const pptxgen = require('pptxgenjs');
 *
 * // Create chart data
 * const data = [
 *   { name: 'Q1', labels: ['Sales', 'Profit'], values: [100, 25] },
 *   { name: 'Q2', labels: ['Sales', 'Profit'], values: [120, 30] },
 * ];
 *
 * // Auto-select preset and create chart
 * const preset = autoSelectPreset(data, 'bar');
 * const chartData = createBeautifiedChart(data, 'bar', preset);
 *
 * // Add to slide
 * slide.addChart(pptxgen.ChartType.bar, chartData, { x: 1, y: 1, w: 8, h: 4 });
 */
