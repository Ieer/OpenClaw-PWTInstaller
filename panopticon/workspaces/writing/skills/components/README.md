# PPTX Component Library

## Usage

Use these components in your HTML slides:

```html
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
```

## Components

### Cards
- `card-info.png` - Information card (blue)
- `card-warning.png` - Warning card (yellow)
- `card-success.png` - Success card (green)
- `card-danger.png` - Danger card (red)

### Buttons
- `button-primary.png` - Primary button (purple-to-green gradient)
- `button-secondary.png` - Secondary button (solid green)
- `button-accent.png` - Accent button (pink-to-lime gradient)

### Decorations
- `circle-accent.png` - Purple circle (30% opacity)
- `circle-secondary.png` - Green circle (30% opacity)

### Badges
- `badge-new.png` - "NEW" badge (pink)
- `badge-hot.png` - "HOT" badge (yellow)
- `badge-featured.png` - "FEATURED" badge (purple)

### Dividers
- `divider-gradient.png` - Gradient divider (purple-to-green)

## Regenerating

To regenerate all components, run:

```bash
node skills/pptx/scripts/component-library.js
```
