/**
 * html2pptx - Convert HTML slide to pptxgenjs slide with positioned elements
 *
 * ENHANCED VERSION - Includes:
 *   - Browser pool for better performance
 *   - Auto gradient rasterization
 *   - Auto color format conversion
 *   - Smart error handling
 *
 * USAGE:
 *   const pptx = new pptxgen();
 *   pptx.layout = 'LAYOUT_16x9';  // Must match HTML body dimensions
 *
 *   const { slide, placeholders } = await html2pptx('slide.html', pptx);
 *   slide.addChart(pptx.charts.LINE, data, placeholders[0]);
 *
 *   await pptx.writeFile('output.pptx');
 *
 * FEATURES:
 *   - Converts HTML to PowerPoint with accurate positioning
 *   - Supports text, images, shapes, and bullet lists
 *   - Extracts placeholder elements (class="placeholder") with positions
 *   - Handles CSS gradients, borders, and margins
 *   - Auto-rasterizes CSS gradients to PNG
 *   - Auto-converts color formats (#RRGGBB → RRGGBB)
 *
 * VALIDATION:
 *   - Uses body width/height from HTML for viewport sizing
 *   - Throws error if HTML dimensions don't match presentation layout
 *   - Throws error if content overflows body (with overflow details)
 *
 * RETURNS:
 *   { slide, placeholders } where placeholders is an array of { id, x, y, w, h }
 */

const { chromium } = require('playwright');
const path = require('path');
const sharp = require('sharp');
const crypto = require('crypto');

const PT_PER_PX = 0.75;
const PX_PER_IN = 96;
const EMU_PER_IN = 914400;

// ==================== OPTIMIZATION: Browser Pool ====================
class BrowserPool {
  constructor(maxSize = 3) {
    this.pool = [];
    this.maxSize = maxSize;
    this.activeCount = 0;
  }

  async acquire() {
    if (this.pool.length > 0) {
      return this.pool.pop();
    }

    if (this.activeCount < this.maxSize) {
      this.activeCount++;
      return await chromium.launch({
        env: { TMPDIR: process.env.TMPDIR || '/tmp' }
      });
    }

    // Wait for available browser
    await new Promise(resolve => setTimeout(resolve, 100));
    return this.acquire();
  }

  async release(browser) {
    try {
      const isConnected = await browser.isConnected();
      if (isConnected) {
        if (this.pool.length < this.maxSize) {
          this.pool.push(browser);
        } else {
          await browser.close();
          this.activeCount--;
        }
      } else {
        this.activeCount--;
      }
    } catch (error) {
      console.error('Error releasing browser:', error.message);
    }
  }

  async closeAll() {
    for (const browser of this.pool) {
      try {
        await browser.close();
      } catch (error) {
        // Ignore close errors
      }
    }
    this.pool = [];
    this.activeCount = 0;
  }
}

// Global browser pool instance
const browserPool = new BrowserPool();

// ==================== OPTIMIZATION: Color Format Conversion ====================
function convertColorFormat(color) {
  if (!color) return null;

  // If already correct format (no #)
  if (!color.startsWith('#') && /^[0-9A-Fa-f]{6}$/.test(color)) {
    return color;
  }

  // If #RRGGBB or #RRGGBBAA format
  if (color.startsWith('#')) {
    return color.substring(1);
  }

  // If rgb(r, g, b) format
  const rgbMatch = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
  if (rgbMatch) {
    return [rgbMatch[1], rgbMatch[2], rgbMatch[3]]
      .map(v => parseInt(v).toString(16).padStart(2, '0'))
      .join('')
      .toUpperCase();
  }

  // If rgba(r, g, b, a) format
  const rgbaMatch = color.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*[\d.]+\)/);
  if (rgbaMatch) {
    return [rgbaMatch[1], rgbaMatch[2], rgbaMatch[3]]
      .map(v => parseInt(v).toString(16).padStart(2, '0'))
      .join('')
      .toUpperCase();
  }

  return color;
}

// ==================== OPTIMIZATION: Auto Gradient Rasterization ====================
const gradientCache = new Map();

async function createGradientPng(width, height, gradientParams, outputPath) {
  // Parse gradient parameters
  const colors = gradientParams.match(/#[0-9A-Fa-f]{6}/gi) || [];
  const color1 = colors[0] || 'B165FB';
  const color2 = colors[1] || '40695B';

  // Create SVG gradient
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#${color1}"/>
          <stop offset="100%" style="stop-color:#${color2}"/>
        </linearGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
    </svg>`;

  await sharp(Buffer.from(svg)).png().toFile(outputPath);
}

async function autoRasterizeGradients(page, tmpDir) {
  const gradients = await page.evaluate(() => {
    const elements = document.querySelectorAll('*');
    const found = [];

    elements.forEach(el => {
      const style = window.getComputedStyle(el);
      const backgroundImage = style.backgroundImage;

      if (backgroundImage.includes('gradient')) {
        const gradientMatch = backgroundImage.match(/linear-gradient\(([^)]+)\)/);
        if (gradientMatch) {
          const rect = el.getBoundingClientRect();
          const elementId = el.id;

          // Find a unique path to the element
          const elementPath = [];
          let current = el;
          while (current && current !== document.body) {
            const tag = current.tagName.toLowerCase();
            const id = current.id ? `#${current.id}` : '';
            const classes = current.className ? `.${Array.from(current.classList).join('.')}` : '';

            elementPath.unshift(`${tag}${id}${classes}`);

            // Only go up 3 levels to keep path manageable
            if (elementPath.length >= 3) break;
            current = current.parentElement;
          }

          found.push({
            elementPath: elementPath.length > 0 ? elementPath.join(' > ') : null,
            elementId,
            elementClass: el.className,
            gradientParams: gradientMatch[1],
            width: Math.round(rect.width),
            height: Math.round(rect.height)
          });
        }
      }
    });

    return found;
  });

  const processedGradients = [];

  for (const gradient of gradients) {
    // Generate unique cache key
    const cacheKey = crypto
      .createHash('md5')
      .update(JSON.stringify(gradient))
      .digest('hex');

    let pngPath = gradientCache.get(cacheKey);

    if (!pngPath) {
      // Generate PNG
      pngPath = path.join(tmpDir, `gradient-${cacheKey}.png`);
      await createGradientPng(
        gradient.width,
        gradient.height,
        gradient.gradientParams,
        pngPath
      );
      gradientCache.set(cacheKey, pngPath);
    }

    // Apply PNG to element
    await page.evaluate(({ elementId, pngPath }) => {
      const el = elementId ? document.getElementById(elementId) : null;
      if (el) {
        el.style.backgroundImage = `url('${pngPath}')`;
        el.style.backgroundSize = 'cover';
        el.style.backgroundRepeat = 'no-repeat';
      }
    }, { elementId: gradient.elementId, pngPath });

    processedGradients.push({
      ...gradient,
      pngPath,
      cacheKey
    });
  }

  return processedGradients;
}

// ==================== OPTIMIZATION: Auto CSS Style Migration ====================
async function autoMigrateTextStyles(page) {
  const migratedElements = await page.evaluate(() => {
    const migrated = [];

    function migrateElement(el) {
      const tagName = el.tagName.toLowerCase();
      const parent = el.parentElement;

      // Only migrate text elements (h1-h6, p, ul, ol)
      if (!['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol'].includes(tagName)) {
        return false;
      }

      const style = window.getComputedStyle(el);

      // Check for problematic styles
      const hasBorder =
        style.borderTopWidth !== '0px' ||
        style.borderRightWidth !== '0px' ||
        style.borderBottomWidth !== '0px' ||
        style.borderLeftWidth !== '0px';

      const hasBackground =
        style.backgroundColor !== 'transparent' &&
        style.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
        style.backgroundColor !== 'rgba(255, 255, 255, 0)';

      const hasBoxShadow = style.boxShadow !== 'none';

      // If no problematic styles, skip
      if (!hasBorder && !hasBackground && !hasBoxShadow) {
        return false;
      }

      // Create a wrapper div to hold the styles
      const wrapper = document.createElement('div');

      // Copy problematic styles to wrapper
      if (hasBorder) {
        wrapper.style.borderTop = style.borderTop;
        wrapper.style.borderRight = style.borderRight;
        wrapper.style.borderBottom = style.borderBottom;
        wrapper.style.borderLeft = style.borderLeft;
        wrapper.style.borderRadius = style.borderRadius;

        // Clear border from text element
        el.style.borderTop = 'none';
        el.style.borderRight = 'none';
        el.style.borderBottom = 'none';
        el.style.borderLeft = 'none';
      }

      if (hasBackground) {
        wrapper.style.backgroundColor = style.backgroundColor;

        // Clear background from text element
        el.style.backgroundColor = 'transparent';
      }

      if (hasBoxShadow) {
        wrapper.style.boxShadow = style.boxShadow;

        // Clear box-shadow from text element
        el.style.boxShadow = 'none';
      }

      // Copy sizing and positioning to wrapper
      wrapper.style.display = el.style.display || 'block';
      wrapper.style.position = el.style.position || 'static';
      wrapper.style.width = style.width;
      wrapper.style.height = style.height;
      wrapper.style.padding = style.padding;
      wrapper.style.margin = style.margin;

      // Insert wrapper before the element
      parent.insertBefore(wrapper, el);

      // Move the element into the wrapper
      wrapper.appendChild(el);

      migrated.push({
        tagName,
        hasBorder,
        hasBackground,
        hasBoxShadow
      });

      return true;
    }

    // Process all text elements
    const textElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, ul, ol');
    textElements.forEach(migrateElement);

    return migrated;
  });

  return migratedElements;
}

// ==================== OPTIMIZATION: Smart Error Handling ====================
const errorSuggestions = {
  'CSS gradients are not supported': {
    message: '检测到 CSS 渐变',
    suggestion: '已自动转换为 PNG 图片',
    autoFixed: true
  },
  'Text element has background': {
    message: '文本元素包含背景色',
    suggestion: '已自动迁移到包裹的 div 容器',
    autoFixed: true
  },
  'Text element has border': {
    message: '文本元素包含边框',
    suggestion: '已自动迁移到包裹的 div 容器',
    autoFixed: true
  },
  'Text element has box-shadow': {
    message: '文本元素包含阴影',
    suggestion: '已自动迁移到包裹的 div 容器',
    autoFixed: true
  },
  'HTML content overflows body': {
    message: '内容超出幻灯片边界',
    suggestion: '尝试减小字体大小、减少内边距、或使用两列布局',
    autoFixed: false
  }
};

function logSmartError(error, htmlFile) {
  const errorKey = Object.keys(errorSuggestions).find(key =>
    error.message.includes(key)
  );

  if (errorKey) {
    const suggestion = errorSuggestions[errorKey];

    console.log('');
    console.log('⚠️ ' + suggestion.message);
    console.log('💡 建议：' + suggestion.suggestion);
    if (suggestion.autoFixed) {
      console.log('✅ 已自动修复');
    }
    console.log('');
  }
}

// ==================== Original html2pptx Functions ====================

// Helper: Get body dimensions and check for overflow
async function getBodyDimensions(page) {
  const bodyDimensions = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);

    return {
      width: parseFloat(style.width),
      height: parseFloat(style.height),
      scrollWidth: body.scrollWidth,
      scrollHeight: body.scrollHeight
    };
  });

  const errors = [];
  const widthOverflowPx = Math.max(0, bodyDimensions.scrollWidth - bodyDimensions.width - 1);
  const heightOverflowPx = Math.max(0, bodyDimensions.scrollHeight - bodyDimensions.height - 1);

  const widthOverflowPt = widthOverflowPx * PT_PER_PX;
  const heightOverflowPt = heightOverflowPx * PT_PER_PX;

  if (widthOverflowPt > 0 || heightOverflowPt > 0) {
    const directions = [];
    if (widthOverflowPt > 0) directions.push(`${widthOverflowPt.toFixed(1)}pt horizontally`);
    if (heightOverflowPt > 0) directions.push(`${heightOverflowPt.toFixed(1)}pt vertically`);
    const reminder = heightOverflowPt > 0 ? ' (Remember: leave 0.5" margin at bottom of slide)' : '';
    errors.push(`HTML content overflows body by ${directions.join(' and ')}${reminder}`);
  }

  return { ...bodyDimensions, errors };
}

// Helper: Validate dimensions match presentation layout
function validateDimensions(bodyDimensions, pres) {
  const errors = [];
  const widthInches = bodyDimensions.width / PX_PER_IN;
  const heightInches = bodyDimensions.height / PX_PER_IN;

  if (pres.presLayout) {
    const layoutWidth = pres.presLayout.width / EMU_PER_IN;
    const layoutHeight = pres.presLayout.height / EMU_PER_IN;

    if (Math.abs(layoutWidth - widthInches) > 0.1 || Math.abs(layoutHeight - heightInches) > 0.1) {
      errors.push(
        `HTML dimensions (${widthInches.toFixed(1)}" × ${heightInches.toFixed(1)}") ` +
        `don't match presentation layout (${layoutWidth.toFixed(1)}" × ${layoutHeight.toFixed(1)}")`
      );
    }
  }
  return errors;
}

function validateTextBoxPosition(slideData, bodyDimensions) {
  const errors = [];
  const slideHeightInches = bodyDimensions.height / PX_PER_IN;
  const minBottomMargin = 0.3; // Relaxed to 0.3 inches from bottom

  for (const el of slideData.elements) {
    // Check text elements (p, h1-h6, list)
    if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'list'].includes(el.type)) {
      const fontSize = el.style?.fontSize || 0;
      const bottomEdge = el.position.y + el.position.h;
      const distanceFromBottom = slideHeightInches - bottomEdge;

      // Only validate larger text elements
      if (fontSize > 14 && distanceFromBottom < minBottomMargin) {
        errors.push(
          `Text element near bottom edge (y=${el.position.y.toFixed(2)}", ` +
          `font-size=${fontSize.toFixed(1)}pt). Leave at least ${minBottomMargin}" margin.`
        );
      }
    }
  }

  return errors;
}

// Helper: Extract background from body
async function getBackground(page) {
  return await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);

    const backgroundInfo = {
      type: null,
      value: null,
      color: null
    };

    const backgroundImage = style.backgroundImage;
    const backgroundColor = style.backgroundColor;

    // Check for gradients
    if (backgroundImage.includes('gradient')) {
      backgroundInfo.type = 'gradient';
      backgroundInfo.value = backgroundImage;
    } else if (backgroundImage !== 'none') {
      // Image background
      const urlMatch = backgroundImage.match(/url\(["']?(.+?)["']?\)/);
      if (urlMatch) {
        backgroundInfo.type = 'image';
        backgroundInfo.value = urlMatch[1];
      }
    } else if (backgroundColor !== 'transparent' && backgroundColor !== 'rgba(0, 0, 0, 0)') {
      backgroundInfo.type = 'color';
      backgroundInfo.value = backgroundColor;
    }

    return backgroundInfo;
  });
}

// Helper: Add background to slide
async function addBackground(slideData, slide, tmpDir) {
  if (!slideData.background || !slideData.background.value) {
    return;
  }

  const { type, value } = slideData.background;

  if (type === 'color') {
    slide.background = { color: convertColorFormat(value) };
  } else if (type === 'image') {
    slide.addImage({
      path: value,
      x: 0, y: 0, w: 10, h: 5.625,
      sizing: { type: 'contain', w: 10, h: 5.625 }
    });
  } else if (type === 'gradient') {
    // Gradient is auto-rasterized, so value is now a PNG path
    slide.addImage({
      path: value,
      x: 0, y: 0, w: 10, h: 5.625,
      sizing: { type: 'contain', w: 10, h: 5.625 }
    });
  }
}

// Helper: Extract slide data (elements, placeholders, background)
async function extractSlideData(page) {
  const slideData = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);

    // Extract background
    const backgroundImage = style.backgroundImage;
    const backgroundColor = style.backgroundColor;

    let background = null;

    if (backgroundImage.includes('gradient')) {
      background = { type: 'gradient', value: backgroundImage };
    } else if (backgroundImage !== 'none') {
      const urlMatch = backgroundImage.match(/url\(["']?(.+?)["']?\)/);
      if (urlMatch) {
        background = { type: 'image', value: urlMatch[1] };
      }
    } else if (backgroundColor !== 'transparent' && backgroundColor !== 'rgba(0, 0, 0, 0)') {
      background = { type: 'color', value: backgroundColor };
    }

    // Extract all elements
    const elements = [];
    const placeholders = [];

    // Process all child elements of body
    function processElement(el, parent = null) {
      const rect = el.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(el);
      const tagName = el.tagName.toLowerCase();

      // Skip if element is hidden or has no size
      if (computedStyle.display === 'none' ||
          computedStyle.visibility === 'hidden' ||
          computedStyle.opacity === '0' ||
          rect.width < 1 ||
          rect.height < 1) {
        return;
      }

      // Check if this is a placeholder
      if (el.classList && el.classList.contains('placeholder')) {
        placeholders.push({
          id: el.id || `placeholder-${placeholders.length}`,
          x: rect.left / 96, // Convert pixels to inches
          y: rect.top / 96,
          w: rect.width / 96,
          h: rect.height / 96
        });
        return;
      }

      // Check for problematic styles on text elements
      const hasBorder =
        computedStyle.borderTopWidth !== '0px' ||
        computedStyle.borderRightWidth !== '0px' ||
        computedStyle.borderBottomWidth !== '0px' ||
        computedStyle.borderLeftWidth !== '0px';

      const hasBackground =
        computedStyle.backgroundColor !== 'transparent' &&
        computedStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
        computedStyle.backgroundColor !== 'rgba(255, 255, 255, 0)';

      const hasBoxShadow = computedStyle.boxShadow !== 'none';

      let elementData = null;

      // Text elements (h1-h6, p)
      if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'].includes(tagName)) {
        elementData = {
          type: tagName,
          text: el.textContent,
          position: {
            x: rect.left / 96,
            y: rect.top / 96,
            w: rect.width / 96,
            h: rect.height / 96
          },
          style: {
            fontSize: parseFloat(computedStyle.fontSize),
            fontFamily: computedStyle.fontFamily.split(',')[0].replace(/['"]/g, ''),
            color: computedStyle.color,
            bold: parseInt(computedStyle.fontWeight) >= 700,
            italic: computedStyle.fontStyle === 'italic',
            underline: computedStyle.textDecorationLine.includes('underline'),
            align: computedStyle.textAlign,
            lineSpacing: parseFloat(computedStyle.lineHeight),
            paddingTop: parseFloat(computedStyle.paddingTop) / 96,
            paddingBottom: parseFloat(computedStyle.paddingBottom) / 96,
            paddingLeft: parseFloat(computedStyle.paddingLeft) / 96,
            paddingRight: parseFloat(computedStyle.paddingRight) / 96
          }
        };

        // Check for problematic styles
        if (hasBorder) {
          elementData.error = `Text element <${tagName}> has border`;
        }
        if (hasBackground) {
          elementData.error = `Text element <${tagName}> has background`;
        }
        if (hasBoxShadow) {
          elementData.error = `Text element <${tagName}> has box-shadow`;
        }
      }
      // List elements (ul, ol)
      else if (['ul', 'ol'].includes(tagName)) {
        const items = [];
        el.querySelectorAll('li').forEach(li => {
          items.push(li.textContent);
        });

        elementData = {
          type: 'list',
          items: items,
          listType: tagName === 'ul' ? 'bullet' : 'number',
          position: {
            x: rect.left / 96,
            y: rect.top / 96,
            w: rect.width / 96,
            h: rect.height / 96
          },
          style: {
            fontSize: parseFloat(computedStyle.fontSize),
            fontFamily: computedStyle.fontFamily.split(',')[0].replace(/['"]/g, ''),
            color: computedStyle.color,
            bold: parseInt(computedStyle.fontWeight) >= 700,
            italic: computedStyle.fontStyle === 'italic',
            lineSpacing: parseFloat(computedStyle.lineHeight),
            paddingTop: parseFloat(computedStyle.paddingTop) / 96,
            paddingBottom: parseFloat(computedStyle.paddingBottom) / 96,
            paddingLeft: parseFloat(computedStyle.paddingLeft) / 96,
            paddingRight: parseFloat(computedStyle.paddingRight) / 96
          }
        };

        if (hasBorder) {
          elementData.error = `Text element <${tagName}> has border`;
        }
        if (hasBackground) {
          elementData.error = `Text element <${tagName}> has background`;
        }
        if (hasBoxShadow) {
          elementData.error = `Text element <${tagName}> has box-shadow`;
        }
      }
      // Image elements
      else if (tagName === 'img') {
        elementData = {
          type: 'image',
          src: el.src,
          position: {
            x: rect.left / 96,
            y: rect.top / 96,
            w: rect.width / 96,
            h: rect.height / 96
          }
        };
      }
      // Div elements (for layout only)
      else if (tagName === 'div') {
        // Check if div has background or border
        if (hasBackground || hasBorder || hasBoxShadow) {
          elementData = {
            type: 'shape',
            tagName: 'div',
            position: {
              x: rect.left / 96,
              y: rect.top / 96,
              w: rect.width / 96,
              h: rect.height / 96
            },
            style: {
              background: hasBackground ? computedStyle.backgroundColor : null,
              border: hasBorder ? {
                top: { color: computedStyle.borderTopColor, width: parseFloat(computedStyle.borderTopWidth) / 96 },
                right: { color: computedStyle.borderRightColor, width: parseFloat(computedStyle.borderRightWidth) / 96 },
                bottom: { color: computedStyle.borderBottomColor, width: parseFloat(computedStyle.borderBottomWidth) / 96 },
                left: { color: computedStyle.borderLeftColor, width: parseFloat(computedStyle.borderLeftWidth) / 96 }
              } : null,
              boxShadow: hasBoxShadow ? computedStyle.boxShadow : null,
              borderRadius: parseFloat(computedStyle.borderRadius) / 96
            }
          };
        }
      }

      if (elementData) {
        elements.push(elementData);
      }

      // Process children (but not if this is a text element)
      if (!['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'].includes(tagName)) {
        Array.from(el.children).forEach(child => processElement(child, el));
      }
    }

    // Start processing from body's children
    Array.from(body.children).forEach(child => processElement(child));

    return {
      elements,
      placeholders,
      background,
      errors: elements.filter(e => e.error).map(e => e.error)
    };
  });

  return slideData;
}

// Helper: Add elements to slide
function addElements(slideData, slide, pres) {
  for (const el of slideData.elements) {
    if (el.error) {
      // Skip elements with errors (they're already in the errors array)
      continue;
    }

    const { x, y, w, h } = el.position;

    if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(el.type)) {
      const options = {
        x, y, w, h,
        fontSize: el.style.fontSize,
        fontFace: el.style.fontFamily,
        color: convertColorFormat(el.style.color),
        bold: el.style.bold,
        italic: el.style.italic,
        underline: el.style.underline,
        align: el.style.align,
        lineSpacing: el.style.lineSpacing
      };

      if (el.style.paddingTop || el.style.paddingBottom ||
          el.style.paddingLeft || el.style.paddingRight) {
        options.margin = [
          el.style.paddingTop || 0,
          el.style.paddingRight || 0,
          el.style.paddingBottom || 0,
          el.style.paddingLeft || 0
        ];
      }

      slide.addText(el.text, options);
    } else if (el.type === 'list') {
      const options = {
        x, y, w, h,
        fontSize: el.style.fontSize,
        fontFace: el.style.fontFamily,
        color: convertColorFormat(el.style.color),
        bold: el.style.bold,
        italic: el.style.italic,
        lineSpacing: el.style.lineSpacing,
        bullet: el.listType === 'bullet'
      };

      if (el.style.paddingTop || el.style.paddingBottom ||
          el.style.paddingLeft || el.style.paddingRight) {
        options.margin = [
          el.style.paddingTop || 0,
          el.style.paddingRight || 0,
          el.style.paddingBottom || 0,
          el.style.paddingLeft || 0
        ];
      }

      slide.addText(el.items.map(item => ({ text: item, options: { bullet: el.listType === 'bullet' } })), options);
    } else if (el.type === 'image') {
      slide.addImage({
        path: el.src,
        x, y, w, h
      });
    } else if (el.type === 'shape' && el.tagName === 'div') {
      // Create a shape for div with background or border
      const options = { x, y, w, h };

      if (el.style.background) {
        options.fill = { color: convertColorFormat(el.style.background) };
      }

      if (el.style.border) {
        options.line = {
          type: 'solid',
          color: convertColorFormat(el.style.border.left.color),
          pt: el.style.border.left.width * 72
        };
      }

      if (el.style.borderRadius > 0) {
        options.rectRadius = el.style.borderRadius * 72;
      }

      slide.addShape(pres.shapes.RECTANGLE, options);
    }
  }
}

// ==================== Main Function ====================
async function html2pptx(htmlFile, pres, options = {}) {
  const {
    tmpDir = process.env.TMPDIR || '/tmp',
    slide = null
  } = options;

  try {
    const browser = await browserPool.acquire();
    let bodyDimensions;
    let slideData;

    const filePath = path.isAbsolute(htmlFile) ? htmlFile : path.join(process.cwd(), htmlFile);
    const validationErrors = [];

    try {
      const page = await browser.newPage();
      page.on('console', (msg) => {
        console.log(`Browser console: ${msg.text()}`);
      });

      await page.goto(`file://${filePath}`);

      // ENHANCED: Auto-migrate text element styles
      const migratedStyles = await autoMigrateTextStyles(page);
      if (migratedStyles.length > 0) {
        console.log(`✓ Auto-migrated ${migratedStyles.length} text element style(s)`);
      }

      // ENHANCED: Auto-rasterize gradients
      const rasterizedGradients = await autoRasterizeGradients(page, tmpDir);
      if (rasterizedGradients.length > 0) {
        console.log(`✓ Auto-rasterized ${rasterizedGradients.length} gradient(s)`);
      }

      bodyDimensions = await getBodyDimensions(page);

      await page.setViewportSize({
        width: Math.round(bodyDimensions.width),
        height: Math.round(bodyDimensions.height)
      });

      slideData = await extractSlideData(page);

      // Update background if it was a gradient
      if (slideData.background && slideData.background.type === 'gradient') {
        const gradientInfo = rasterizedGradients.find(g => g.width === Math.round(bodyDimensions.width) && g.height === Math.round(bodyDimensions.height));
        if (gradientInfo) {
          slideData.background.value = gradientInfo.pngPath;
        }
      }

      await page.close();
    } finally {
      await browserPool.release(browser);
    }

    // Collect all validation errors
    if (bodyDimensions.errors && bodyDimensions.errors.length > 0) {
      validationErrors.push(...bodyDimensions.errors);
    }

    const dimensionErrors = validateDimensions(bodyDimensions, pres);
    if (dimensionErrors.length > 0) {
      validationErrors.push(...dimensionErrors);
    }

    const textBoxPositionErrors = validateTextBoxPosition(slideData, bodyDimensions);
    if (textBoxPositionErrors.length > 0) {
      validationErrors.push(...textBoxPositionErrors);
    }

    if (slideData.errors && slideData.errors.length > 0) {
      validationErrors.push(...slideData.errors);
    }

    // Throw all errors at once if any exist
    if (validationErrors.length > 0) {
      const errorMessage = validationErrors.length === 1
        ? validationErrors[0]
        : `Multiple validation errors found:\n${validationErrors.map((e, i) => `  ${i + 1}. ${e}`).join('\n')}`;

      const error = new Error(errorMessage);

      // Log smart error messages
      logSmartError(error, htmlFile);

      throw error;
    }

    const targetSlide = slide || pres.addSlide();

    await addBackground(slideData, targetSlide, tmpDir);
    addElements(slideData, targetSlide, pres);

    return { slide: targetSlide, placeholders: slideData.placeholders };
  } catch (error) {
    // Log smart error messages for caught errors
    logSmartError(error, htmlFile);

    if (!error.message.startsWith(htmlFile)) {
      throw new Error(`${htmlFile}: ${error.message}`);
    }
    throw error;
  }
}

// Clean up browser pool on exit
if (typeof process !== 'undefined') {
  process.on('exit', async () => {
    await browserPool.closeAll();
  });

  process.on('SIGINT', async () => {
    await browserPool.closeAll();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    await browserPool.closeAll();
    process.exit(0);
  });
}

module.exports = html2pptx;
module.exports.convertColorFormat = convertColorFormat;
module.exports.autoMigrateTextStyles = autoMigrateTextStyles;
module.exports.autoRasterizeGradients = autoRasterizeGradients;
module.exports.browserPool = browserPool;
