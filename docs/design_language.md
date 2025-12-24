# FORGE/LAB - Design Language

## Philosophie

Inspiré de l'esthétique "Westworld Lab / The Forge" : minimaliste, précis, silencieux.

### Principes Fondamentaux

1. **Silence UX** : Pas de bruit visuel, pas d'icônes partout
2. **Précision** : Chaque élément a sa place, grille stricte
3. **Élégance** : Typographie premium, espaces généreux
4. **Clarté** : États clairs, feedback subtil

## Palette de Couleurs

### Couleurs Primaires
```css
--ivory-50: #FEFEFE;   /* Background très clair */
--ivory-100: #FAFAF8;  /* Background principal */
--ivory-200: #F5F5F0;  /* Background hover */
--forge-dark: #1A1A1A; /* Texte principal */
--forge-muted: #6B6B6B; /* Texte secondaire */
```

### Couleurs d'État
```css
--viral-high: #10B981;    /* Score élevé / Succès */
--viral-medium: #F59E0B;  /* Score moyen / Warning */
--viral-low: #6B7280;     /* Score bas / Inactif */
```

### Bordures
```css
--forge-border: #E0E0D8;  /* Bordure subtile */
--hairline: 0.5px;        /* Épaisseur minimale */
```

## Typographie

### Police
- **Principale** : Inter (weights: 300, 400, 500, 600, 700)
- **Fallback** : system-ui, sans-serif

### Échelle
```css
text-2xs: 0.625rem;  /* 10px - Labels mineurs */
text-xs: 0.75rem;    /* 12px - Métadonnées */
text-sm: 0.875rem;   /* 14px - Corps */
text-base: 1rem;     /* 16px - Standard */
text-lg: 1.125rem;   /* 18px - Titres sections */
text-xl: 1.25rem;    /* 20px - Titres pages */
text-2xl: 1.5rem;    /* 24px - Titres majeurs */
```

## Espacement

Basé sur une grille de 4px :
```css
spacing-1: 0.25rem;  /* 4px */
spacing-2: 0.5rem;   /* 8px */
spacing-3: 0.75rem;  /* 12px */
spacing-4: 1rem;     /* 16px */
spacing-6: 1.5rem;   /* 24px */
spacing-8: 2rem;     /* 32px */
```

## Composants

### Cards
```css
.card {
  background: white;
  border: 1px solid var(--forge-border);
  border-radius: 0.75rem;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
```

### Buttons
```css
.btn-primary {
  background: var(--forge-dark);
  color: white;
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
}

.btn-secondary {
  background: var(--ivory-200);
  color: var(--forge-dark);
}

.btn-ghost {
  background: transparent;
  color: var(--forge-dark);
}
```

### Inputs
```css
.input {
  background: white;
  border: 1px solid var(--forge-border);
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
}
```

## Animations

### Transitions Standard
```css
transition-all: 200ms ease-out;
```

### Door Panel (Navigation)
```css
@keyframes doorSlideIn {
  from { transform: translateX(-100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

### Fade In
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

### Timing
- Micro-interactions : 150ms
- Transitions : 200-300ms
- Animations complexes : 400-500ms

## États

### Vide
- Illustration/icône subtile
- Message clair et action suggérée
- Pas de tristesse, juste guidage

### Chargement
- Skeleton avec animation pulse
- Indicateurs discrets (points, spinners fins)
- Jamais de blocage modal si évitable

### Erreur
- Bordure ou highlight subtil
- Message concis
- Action de résolution claire

### Succès
- Confirmation brève
- Retour automatique au flux
- Pas d'interruption excessive

## Iconographie

- **Style** : Lucide Icons (outlined, 24px grid)
- **Poids** : 1.5px stroke
- **Taille par défaut** : 16px dans le texte, 24px standalone

## Responsive

L'application est fixe (desktop-only) mais s'adapte :
- **Minimum** : 1200×700px
- **Optimal** : 1400×900px
- **Sidebar** : Collapsible pour plus d'espace

## Accessibilité

- Contraste minimum : 4.5:1
- Focus visible sur tous les éléments interactifs
- Labels pour tous les inputs
- Annonces pour les changements d'état









