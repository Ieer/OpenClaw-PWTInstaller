/**
 * Design Systems for PPTX - Pre-defined professional design templates
 *
 * USAGE:
 *   const ds = getDesignSystem('tech-modern');
 *   const css = generateCSSVariables(ds);
 *   // Insert CSS into HTML
 */

const designSystems = {
  'business-professional': {
    colors: {
      primary: '1C2833',
      secondary: '2E4053',
      accent: '3498DB',
      success: '27AE60',
      warning: 'F39C12',
      danger: 'E74C3C',
      light: 'ECF0F1',
      dark: '2C3E50'
    },
    typography: {
      heading1: { size: 44, weight: 'bold', lineHeight: 1.2 },
      heading2: { size: 32, weight: 'bold', lineHeight: 1.3 },
      heading3: { size: 24, weight: 'semibold', lineHeight: 1.4 },
      body: { size: 18, weight: 'normal', lineHeight: 1.5 },
      small: { size: 14, weight: 'normal', lineHeight: 1.4 }
    },
    spacing: {
      xs: 8,
      sm: 12,
      md: 16,
      lg: 24,
      xl: 32,
      xxl: 48
    },
    borderRadius: 8,
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
  },

  'tech-modern': {
    colors: {
      primary: 'B165FB',
      secondary: '40695B',
      accent: 'FF6B9D',
      success: '28A745',
      warning: 'FFC107',
      danger: 'DC3545',
      light: 'F8F9FA',
      dark: '181B24'
    },
    typography: {
      heading1: { size: 48, weight: 'bold', lineHeight: 1.1 },
      heading2: { size: 36, weight: 'bold', lineHeight: 1.2 },
      heading3: { size: 28, weight: 'semibold', lineHeight: 1.3 },
      body: { size: 18, weight: 'normal', lineHeight: 1.5 },
      small: { size: 14, weight: 'normal', lineHeight: 1.4 }
    },
    spacing: {
      xs: 8,
      sm: 16,
      md: 24,
      lg: 32,
      xl: 48,
      xxl: 64
    },
    borderRadius: 12,
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)'
  },

  'clean-minimal': {
    colors: {
      primary: '34495E',
      secondary: '7F8C8D',
      accent: 'E74C3C',
      success: '27AE60',
      warning: 'F39C12',
      danger: 'C0392B',
      light: 'FFFFFF',
      dark: '2C3E50'
    },
    typography: {
      heading1: { size: 40, weight: 'light', lineHeight: 1.3 },
      heading2: { size: 30, weight: 'light', lineHeight: 1.4 },
      heading3: { size: 22, weight: 'normal', lineHeight: 1.5 },
      body: { size: 16, weight: 'normal', lineHeight: 1.6 },
      small: { size: 13, weight: 'normal', lineHeight: 1.5 }
    },
    spacing: {
      xs: 12,
      sm: 16,
      md: 24,
      lg: 36,
      xl: 48,
      xxl: 64
    },
    borderRadius: 4,
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)'
  },

  'vibrant-creative': {
    colors: {
      primary: 'FF6B9D',
      secondary: 'C5DE82',
      accent: '40695B',
      success: '28A745',
      warning: 'FFC107',
      danger: 'DC3545',
      light: 'FFF9E6',
      dark: '1A1A2E'
    },
    typography: {
      heading1: { size: 52, weight: 'bold', lineHeight: 1.1 },
      heading2: { size: 40, weight: 'bold', lineHeight: 1.2 },
      heading3: { size: 32, weight: 'semibold', lineHeight: 1.3 },
      body: { size: 18, weight: 'normal', lineHeight: 1.5 },
      small: { size: 15, weight: 'normal', lineHeight: 1.4 }
    },
    spacing: {
      xs: 10,
      sm: 16,
      md: 24,
      lg: 32,
      xl: 48,
      xxl: 64
    },
    borderRadius: 16,
    boxShadow: '0 12px 32px rgba(0, 0, 0, 0.15)'
  }
};

function getDesignSystem(name) {
  const ds = designSystems[name];
  if (!ds) {
    const available = Object.keys(designSystems).join(', ');
    throw new Error(
      `Design system not found: ${name}\nAvailable: ${available}`
    );
  }
  return ds;
}

function listDesignSystems() {
  return Object.keys(designSystems);
}

function generateCSSVariables(ds) {
  return `
/* Design System CSS Variables */
:root {
  /* Colors */
  --color-primary: #${ds.colors.primary};
  --color-secondary: #${ds.colors.secondary};
  --color-accent: #${ds.colors.accent};
  --color-success: #${ds.colors.success};
  --color-warning: #${ds.colors.warning};
  --color-danger: #${ds.colors.danger};
  --color-light: #${ds.colors.light};
  --color-dark: #${ds.colors.dark};

  /* Typography - Sizes */
  --font-h1-size: ${ds.typography.heading1.size}pt;
  --font-h2-size: ${ds.typography.heading2.size}pt;
  --font-h3-size: ${ds.typography.heading3.size}pt;
  --font-body-size: ${ds.typography.body.size}pt;
  --font-small-size: ${ds.typography.small.size}pt;

  /* Typography - Weights */
  --font-h1-weight: ${ds.typography.heading1.weight};
  --font-h2-weight: ${ds.typography.heading2.weight};
  --font-h3-weight: ${ds.typography.heading3.weight};
  --font-body-weight: ${ds.typography.body.weight};
  --font-small-weight: ${ds.typography.small.weight};

  /* Typography - Line Heights */
  --font-h1-line-height: ${ds.typography.heading1.lineHeight};
  --font-h2-line-height: ${ds.typography.heading2.lineHeight};
  --font-h3-line-height: ${ds.typography.heading3.lineHeight};
  --font-body-line-height: ${ds.typography.body.lineHeight};
  --font-small-line-height: ${ds.typography.small.lineHeight};

  /* Spacing */
  --spacing-xs: ${ds.spacing.xs}pt;
  --spacing-sm: ${ds.spacing.sm}pt;
  --spacing-md: ${ds.spacing.md}pt;
  --spacing-lg: ${ds.spacing.lg}pt;
  --spacing-xl: ${ds.spacing.xl}pt;
  --spacing-xxl: ${ds.spacing.xxl}pt;

  /* Effects */
  --border-radius: ${ds.borderRadius}px;
  --box-shadow: ${ds.boxShadow};
}
`.trim();
}

function getCSSUsageExample(name) {
  const ds = getDesignSystem(name);
  return `
/* CSS Usage Examples for ${name} Design System */

/* Header */
.header {
  background: #${ds.colors.dark};
  padding: var(--spacing-md) var(--spacing-lg);
}

/* Headings */
h1 {
  font-size: var(--font-h1-size);
  font-weight: var(--font-h1-weight);
  line-height: var(--font-h1-line-height);
  color: #${ds.colors.primary};
  margin: 0;
}

h2 {
  font-size: var(--font-h2-size);
  font-weight: var(--font-h2-weight);
  line-height: var(--font-h2-line-height);
  color: #${ds.colors.secondary};
  margin: var(--spacing-md) 0;
}

/* Body text */
p {
  font-size: var(--font-body-size);
  font-weight: var(--font-body-weight);
  line-height: var(--font-body-line-height);
  color: #${ds.colors.dark};
  margin: var(--spacing-sm) 0;
}

/* Card component */
.card {
  background: var(--color-light);
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  padding: var(--spacing-lg);
  margin: var(--spacing-md) 0;
}

/* Primary button */
.button-primary {
  background: linear-gradient(135deg, #${ds.colors.primary} 0%, #${ds.colors.secondary} 100%);
  color: var(--color-light);
  padding: var(--spacing-md) var(--spacing-xl);
  border-radius: var(--border-radius);
  font-weight: var(--font-h2-weight);
  border: none;
  cursor: pointer;
}

/* Accent highlight */
.highlight {
  color: #${ds.colors.accent};
  font-weight: var(--font-h3-weight);
}

/* Success message */
.success-message {
  background: #${ds.colors.success};
  color: white;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--border-radius);
}
`.trim();
}

module.exports = {
  designSystems,
  getDesignSystem,
  listDesignSystems,
  generateCSSVariables,
  getCSSUsageExample
};
