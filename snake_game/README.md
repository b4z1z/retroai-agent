# 🐍 Snake (x86 Assembly / DOS)

Un jeu Snake complet écrit en **assembleur x86** pour DOS, utilisant le mode texte 80×25 avec accès direct à la mémoire vidéo (`B800:0000`).

---

## 📁 Fichiers du projet

| Fichier       | Description                              |
|---------------|------------------------------------------|
| `snake.asm`   | Code source complet du jeu               |
| `README.md`   | Ce fichier — compilation et instructions   |
| `CHANGELOG.md`| Historique des fonctionnalités           |

---

## 🔧 Prérequis

- **Turbo Assembler (TASM)** ou compatible
- **Turbo Linker (TLINK)**
- Un environnement DOS réel ou émulé (DOSBox, FreeDOS, etc.)

---

## ⚙️ Compilation

Depuis le dossier `snake_game/`, lancez :

```bash
tasm snake.asm
tlink snake.obj
```

Puis exécutez :

```bash
snake.exe
```

> **Note :** Sous Linux ou macOS, utilisez [DOSBox](https://www.dosbox.com/) ou [DOSBox-X](https://dosbox-x.com/) pour assembler et lancer le jeu.

---

## 🎮 Commandes

| Touche        | Action                        |
|---------------|-------------------------------|
| `↑` (Flèche haut)    | Aller vers le haut   |
| `↓` (Flèche bas)     | Aller vers le bas    |
| `←` (Flèche gauche)  | Aller vers la gauche |
| `→` (Flèche droite)  | Aller vers la droite |
| `W`           | Aller vers le haut (AZERTY/QWERTY) |
| `S`           | Aller vers le bas                |
| `A`           | Aller vers la gauche             |
| `D`           | Aller vers la droite             |
| `ESC`         | Quitter le jeu                   |

> Le serpent ne peut pas faire un demi-tour instantané (ex: aller à droite puis immédiatement à gauche).

---

## 🎯 Objectif

Manger les pommes (`*`) pour faire grandir le serpent et augmenter votre score. Évitez de heurer les murs (`#`) ou de mordre votre propre corps — c'est **Game Over** !

---

## 🖥️ Caractéristiques techniques

- **Mode texte 80×25 couleur** via accès direct à `B800:0000`
- **Buffer circulaire** pour le serpent (taille max : 400 segments)
- **Générateur pseudo-aléatoire** basé sur le timer BIOS
- **Rendu incrémental** : seuls la tête, la queue et la pomme sont redessinés chaque frame
- **Gestion clavier BIOS** (non bloquante) avec support des touches étendues

---

## 📝 Licence

Projet éducatif libre d'utilisation et de modification.
