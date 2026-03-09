/**
 * Pre-rendered Component Library for PPTX
 *
 * Provides commonly used UI components as PNG images for better compatibility
 * with PPTX validation rules.
 */

const sharp = require('sharp');
const path = require('path');
const fs = require('fs').promises;

// Component cache
const componentCache = new Map();

/**
 * Button component with gradient background
 */
async function createButton(width, height, text, options = {}) {
  const {
    backgroundColor = 'B165FB',
    textColor = 'FFFFFF',
    fontSize = 16,
    cornerRadius = 8,
    padding = 12
  } = options;

  const cacheKey = `button-${width}-${height}-${backgroundColor}-${text}-${fontSize}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="btn-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#${backgroundColor};stop-opacity:1" />
          <stop offset="100%" style="stop-color:#${backgroundColor}88;stop-opacity:1" />
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#00000033"/>
        </filter>
      </defs>
      <rect x="0" y="0" width="${width}" height="${height}"
            rx="${cornerRadius}" ry="${cornerRadius}"
            fill="url(#btn-grad)" filter="url(#shadow)"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
            fill="#${textColor}" font-size="${fontSize}" font-family="Arial, sans-serif"
            font-weight="bold">${text}</text>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Card component with border and shadow
 */
async function createCard(width, height, options = {}) {
  const {
    backgroundColor = 'FFFFFF',
    borderColor = '40695B',
    borderWidth = 2,
    cornerRadius = 8,
    shadowBlur = 8,
    shadowColor = '00000020'
  } = options;

  const cacheKey = `card-${width}-${height}-${backgroundColor}-${borderColor}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <filter id="card-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="${shadowBlur / 2}" stdDeviation="${shadowBlur / 2}"
                       flood-color="#${shadowColor}"/>
        </filter>
      </defs>
      <rect x="${borderWidth / 2}" y="${borderWidth / 2}"
            width="${width - borderWidth}" height="${height - borderWidth}"
            rx="${cornerRadius}" ry="${cornerRadius}"
            fill="#${backgroundColor}" stroke="#${borderColor}"
            stroke-width="${borderWidth}" filter="url(#card-shadow)"/>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Info box with colored left border
 */
async function createInfoBox(width, height, text, options = {}) {
  const {
    backgroundColor = 'F8F9FA',
    borderColor = '40695B',
    borderWidth = 4,
    textColor = '181B24',
    fontSize = 12,
    padding = 12
  } = options;

  const cacheKey = `infobox-${width}-${height}-${borderColor}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="${width}" height="${height}"
            fill="#${backgroundColor}" rx="4" ry="4"/>
      <rect x="0" y="0" width="${borderWidth}" height="${height}"
            fill="#${borderColor}" rx="4" ry="4"
            clip-path="inset(0 0 0 0 round 4px)"/>
      <text x="${padding + borderWidth + 10}" y="50%" dominant-baseline="middle"
            fill="#${textColor}" font-size="${fontSize}" font-family="Arial, sans-serif"
            font-weight="bold">${text}</text>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Callout/Quote box with decorative border
 */
async function createCallout(width, height, text, options = {}) {
  const {
    backgroundColor = 'FFF9E6',
    borderColor = 'F39C12',
    borderWidth = 3,
    textColor = '2C3E50',
    fontSize = 14,
    padding = 16
  } = options;

  const cacheKey = `callout-${width}-${height}-${borderColor}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="${width}" height="${height}"
            fill="#${backgroundColor}" rx="8" ry="8"/>
      <rect x="0" y="0" width="${width}" height="${height}"
            fill="none" stroke="#${borderColor}" stroke-width="${borderWidth}"
            rx="8" ry="8"/>
      <text x="${padding}" y="50%" dominant-baseline="middle"
            fill="#${textColor}" font-size="${fontSize}" font-family="Arial, sans-serif"
            font-style="italic">${text}</text>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Badge/Tag component
 */
async function createBadge(width, height, text, options = {}) {
  const {
    backgroundColor = '28A745',
    textColor = 'FFFFFF',
    fontSize = 12
  } = options;

  const cacheKey = `badge-${width}-${height}-${backgroundColor}-${text}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="${width}" height="${height}"
            rx="${height / 2}" ry="${height / 2}"
            fill="#${backgroundColor}"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
            fill="#${textColor}" font-size="${fontSize}" font-family="Arial, sans-serif"
            font-weight="bold">${text}</text>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Icon placeholder with colored circle
 */
async function createIconPlaceholder(size, iconLetter, options = {}) {
  const {
    backgroundColor = 'B165FB',
    textColor = 'FFFFFF',
    fontSize = Math.floor(size * 0.5)
  } = options;

  const cacheKey = `icon-${size}-${iconLetter}-${backgroundColor}`;

  if (componentCache.has(cacheKey)) {
    return componentCache.get(cacheKey);
  }

  const svg = `
    <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#${backgroundColor}"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
            fill="#${textColor}" font-size="${fontSize}" font-family="Arial, sans-serif"
            font-weight="bold">${iconLetter}</text>
    </svg>`;

  const outputPath = path.join(process.env.TMPDIR || '/tmp', `${cacheKey}.png`);

  await sharp(Buffer.from(svg)).png().toFile(outputPath);

  componentCache.set(cacheKey, outputPath);

  return outputPath;
}

/**
 * Clear component cache
 */
function clearCache() {
  componentCache.clear();
}

/**
 * Get cache statistics
 */
function getCacheStats() {
  return {
    size: componentCache.size,
    keys: Array.from(componentCache.keys())
  };
}

// Export all components
module.exports = {
  createButton,
  createCard,
  createInfoBox,
  createCallout,
  createBadge,
  createIconPlaceholder,
  clearCache,
  getCacheStats
};

/**
 * Usage example:
 *
 * const { createButton, createCard } = require('./pre_rendered_components');
 *
 * // Create a button
 * const buttonPath = await createButton(200, 40, 'Click Me', {
 *   backgroundColor: 'B165FB',
 *   textColor: 'FFFFFF'
 * });
 *
 * // Create a card
 * const cardPath = await createCard(300, 200, {
 *   backgroundColor: 'FFFFFF',
 *   borderColor: '40695B'
 * });
 */
