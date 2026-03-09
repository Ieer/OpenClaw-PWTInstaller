/**
 * Component Library for PPTX - Pre-rendered UI components
 *
 * USAGE:
 *   // Generate all components
 *   node scripts/component-library.js
 *
 *   // Use in HTML
 *   <img src="components/card-info.png" class="card">
 */

const sharp = require('sharp');
const path = require('path');
const fs = require('fs').promises;

// Component definitions
const components = {
  // Info cards
  'card-info': {
    type: 'card',
    background: '#E7F3FF',
    borderColor: '#B165FB',
    textColor: '#181B24',
    borderRadius: 12,
    padding: 24,
    width: 400,
    height: 150,
    icon: 'ℹ️'
  },
  'card-warning': {
    type: 'card',
    background: '#FFF3CD',
    borderColor: '#FFC107',
    textColor: '#856404',
    borderRadius: 12,
    padding: 24,
    width: 400,
    height: 150,
    icon: '⚠️'
  },
  'card-success': {
    type: 'card',
    background: '#D4EDDA',
    borderColor: '#28A745',
    textColor: '#155724',
    borderRadius: 12,
    padding: 24,
    width: 400,
    height: 150,
    icon: '✅'
  },
  'card-danger': {
    type: 'card',
    background: '#F8D7DA',
    borderColor: '#DC3545',
    textColor: '#721C24',
    borderRadius: 12,
    padding: 24,
    width: 400,
    height: 150,
    icon: '❌'
  },

  // Buttons
  'button-primary': {
    type: 'button',
    gradient: ['#B165FB', '#40695B'],
    textColor: '#FFFFFF',
    borderRadius: 8,
    width: 200,
    height: 60,
    text: 'Primary'
  },
  'button-secondary': {
    type: 'button',
    background: '#40695B',
    textColor: '#FFFFFF',
    borderRadius: 8,
    width: 200,
    height: 60,
    text: 'Secondary'
  },
  'button-accent': {
    type: 'button',
    gradient: ['#FF6B9D', '#C5DE82'],
    textColor: '#FFFFFF',
    borderRadius: 8,
    width: 200,
    height: 60,
    text: 'Accent'
  },

  // Icons/Decorations
  'circle-accent': {
    type: 'shape',
    shape: 'circle',
    color: '#B165FB',
    width: 100,
    height: 100,
    opacity: 0.3
  },
  'circle-secondary': {
    type: 'shape',
    shape: 'circle',
    color: '#40695B',
    width: 100,
    height: 100,
    opacity: 0.3
  },

  // Badges
  'badge-new': {
    type: 'badge',
    background: '#FF6B9D',
    textColor: '#FFFFFF',
    borderRadius: 16,
    padding: 8,
    text: 'NEW'
  },
  'badge-hot': {
    type: 'badge',
    background: '#FFC107',
    textColor: '#181B24',
    borderRadius: 16,
    padding: 8,
    text: 'HOT'
  },
  'badge-featured': {
    type: 'badge',
    background: '#B165FB',
    textColor: '#FFFFFF',
    borderRadius: 16,
    padding: 8,
    text: 'FEATURED'
  },

  // Dividers
  'divider-gradient': {
    type: 'divider',
    gradient: ['#B165FB', '#40695B'],
    width: 600,
    height: 4
  }
};

async function createCard(component) {
  const {
    background,
    borderColor,
    borderRadius,
    padding,
    width,
    height
  } = component;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="4" stdDeviation="8" flood-opacity="0.1"/>
        </filter>
      </defs>
      <rect
        x="0" y="0"
        width="${width}" height="${height}"
        fill="${background}"
        rx="${borderRadius}"
        filter="url(#shadow)"
      />
      <rect
        x="0" y="0"
        width="${width}" height="${height}"
        fill="none"
        stroke="${borderColor}"
        rx="${borderRadius}"
        stroke-width="2"
      />
      ${component.icon ? `
        <text x="${padding}" y="${padding + 24}" font-size="20" fill="${component.textColor}">
          ${component.icon}
        </text>
      ` : ''}
    </svg>`;

  return Buffer.from(svg);
}

async function createButton(component) {
  const {
    background,
    gradient,
    textColor,
    borderRadius,
    width,
    height,
    text
  } = component;

  const fill = gradient
    ? `<defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" style="stop-color:${gradient[0]}"/>
          <stop offset="100%" style="stop-color:${gradient[1]}"/>
        </linearGradient>
      </defs>`
    : '';

  const rectFill = gradient ? 'url(#g)' : background;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      ${fill}
      <rect
        x="0" y="0"
        width="${width}" height="${height}"
        fill="${rectFill}"
        rx="${borderRadius}"
      />
      <text
        x="${width / 2}" y="${height / 2}"
        font-family="Arial, sans-serif"
        font-size="18"
        font-weight="bold"
        fill="${textColor}"
        text-anchor="middle"
        dominant-baseline="middle"
      >${text}</text>
    </svg>`;

  return Buffer.from(svg);
}

async function createShape(component) {
  const { shape, color, width, height, opacity } = component;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      ${shape === 'circle' ? `
        <circle
          cx="${width / 2}" cy="${height / 2}"
          r="${width / 2}"
          fill="${color}"
          opacity="${opacity}"
        />
      ` : `
        <rect
          x="0" y="0"
          width="${width}" height="${height}"
          fill="${color}"
          opacity="${opacity}"
        />
      `}
    </svg>`;

  return Buffer.from(svg);
}

async function createBadge(component) {
  const { background, textColor, borderRadius, padding, text } = component;

  const fontSize = 14;
  const textWidth = text.length * fontSize * 0.6;
  const width = textWidth + padding * 2;
  const height = fontSize + padding * 2;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <rect
        x="0" y="0"
        width="${width}" height="${height}"
        fill="${background}"
        rx="${borderRadius}"
      />
      <text
        x="${width / 2}" y="${height / 2}"
        font-family="Arial, sans-serif"
        font-size="${fontSize}"
        font-weight="bold"
        fill="${textColor}"
        text-anchor="middle"
        dominant-baseline="middle"
      >${text}</text>
    </svg>`;

  return Buffer.from(svg);
}

async function createDivider(component) {
  const { gradient, width, height } = component;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" style="stop-color:${gradient[0]}"/>
          <stop offset="100%" style="stop-color:${gradient[1]}"/>
        </linearGradient>
      </defs>
      <rect
        x="0" y="0"
        width="${width}" height="${height}"
        fill="url(#g)"
        rx="${height / 2}"
      />
    </svg>`;

  return Buffer.from(svg);
}

async function generateComponentLibrary(outputDir) {
  console.log('🎨 Generating component library...');
  console.log(`Output directory: ${outputDir}\n`);

  // Create output directory
  await fs.mkdir(outputDir, { recursive: true });

  const generated = [];

  for (const [name, component] of Object.entries(components)) {
    try {
      let buffer;

      switch (component.type) {
        case 'card':
          buffer = await createCard(component);
          break;
        case 'button':
          buffer = await createButton(component);
          break;
        case 'shape':
          buffer = await createShape(component);
          break;
        case 'badge':
          buffer = await createBadge(component);
          break;
        case 'divider':
          buffer = await createDivider(component);
          break;
        default:
          console.log(`  ⚠️  Unknown component type: ${component.type}`);
          continue;
      }

      if (buffer) {
        const outputPath = path.join(outputDir, `${name}.png`);
        await sharp(buffer).png().toFile(outputPath);
        generated.push(name);
        console.log(`  ✓ ${name}.png`);
      }
    } catch (error) {
      console.error(`  ✗ ${name}: ${error.message}`);
    }
  }

  // Generate README
  const readme = `# PPTX Component Library

## Usage

Use these components in your HTML slides:

\`\`\`html
<!-- Info Card -->
<img src="components/card-info.png" class="card" alt="Info card">

<!-- Warning Card -->
<img src="components/card-warning.png" class="card" alt="Warning card">

<!-- Primary Button -->
<img src="components/button-primary.png" class="button" alt="Primary button">

<!-- Accent Circle -->
<img src="components/circle-accent.png" class="decoration" alt="Circle decoration">

<!-- New Badge -->
<img src="components/badge-new.png" class="badge" alt="New badge">
\`\`\`

## Components

### Cards
- \`card-info.png\` - Information card (blue)
- \`card-warning.png\` - Warning card (yellow)
- \`card-success.png\` - Success card (green)
- \`card-danger.png\` - Danger card (red)

### Buttons
- \`button-primary.png\` - Primary button (purple-to-green gradient)
- \`button-secondary.png\` - Secondary button (solid green)
- \`button-accent.png\` - Accent button (pink-to-lime gradient)

### Decorations
- \`circle-accent.png\` - Purple circle (30% opacity)
- \`circle-secondary.png\` - Green circle (30% opacity)

### Badges
- \`badge-new.png\` - "NEW" badge (pink)
- \`badge-hot.png\` - "HOT" badge (yellow)
- \`badge-featured.png\` - "FEATURED" badge (purple)

### Dividers
- \`divider-gradient.png\` - Gradient divider (purple-to-green)

## Regenerating

To regenerate all components, run:

\`\`\`bash
node skills/pptx/scripts/component-library.js
\`\`\`
`;

  await fs.writeFile(path.join(outputDir, 'README.md'), readme);
  console.log(`\n✓ Generated ${generated.length} component(s)`);
  console.log(`✓ README.md created\n`);
  console.log('Component library ready! 🎉\n');
}

// Run if executed directly
if (require.main === module) {
  const outputDir = process.argv[2] || path.join(__dirname, '../../components');

  generateComponentLibrary(outputDir)
    .then(() => {
      console.log('Done!');
      process.exit(0);
    })
    .catch(error => {
      console.error('Error:', error);
      process.exit(1);
    });
}

module.exports = {
  components,
  generateComponentLibrary,
  createCard,
  createButton,
  createShape,
  createBadge,
  createDivider
};
