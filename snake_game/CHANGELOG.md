# Changelog — Snake (x86 Assembly / DOS)

## v1.0.0 — Version complète initiale

### 🎮 Fonctionnalités du jeu
- **Jeu Snake classique** en mode texte 80×25 couleur
- **Déplacement fluide** du serpent avec gestion des directions
- **Interdiction du demi-tour** (impossible de faire un 180° instantané)
- **Génération aléatoire de pommes** avec vérification de position libre
- **Croissance du serpent** à chaque pomme mangée
- **Détection de collisions** : murs et corps du serpent
- **Affichage du score** en temps réel
- **Écran de Game Over** avec score final

### 🖥️ Technique & rendu
- **Accès direct mémoire vidéo** (`B800:0000`) pour un rendu rapide
- **Buffer circulaire** pour stocker les segments du serpent (capacité : 400)
- **Rendu incrémental optimisé** : seuls la tête, la queue et la pomme sont modifiées par frame
- **Générateur pseudo-aléatoire** basé sur le timer BIOS (0040:006C)
- **Synchronisation par timer BIOS** (18.2 Hz) pour une vitesse constante

### ⌨️ Contrôles
- Flèches directionnelles (`↑↓←→`)
- Touches WASD (`W` `A` `S` `D`)
- `ESC` pour quitter le jeu

### 🏗️ Architecture du code
- Structure modulaire avec procédures clairement séparées
- Constantes définies en début de fichier pour faciliter la maintenance
- Commentaires détaillés en français pour chaque procédure
- Compatible TASM / TLINK (syntaxe Intel)

---

*Projet créé pour l'apprentissage de l'assembleur x86 en mode réel DOS.*
