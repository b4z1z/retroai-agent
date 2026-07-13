# 🛒 BAZIZ.IA — Plugin Marketplace

Le marché communautaire de plugins. **Une seule source de vérité** :
[`registry.json`](registry.json) — lu à la fois par le **site vitrine**
(ce dossier) et par **l'application** (menu `/plugins` → Install).

## Comment ça marche

```
registry.json  ←── lu par l'app (/plugins → Install) via raw.githubusercontent.com
     │
     └───────── lu par le site vitrine (index.html) déployé sur Vercel
plugins/*.py   ←── les fichiers téléchargés par l'app à l'installation
```

L'app **valide le contrat** de chaque plugin téléchargé avant de le garder
(un fichier invalide est supprimé immédiatement), et demande une
confirmation avant tout téléchargement de code.

## 🚀 Déployer le site sur Vercel (une fois, ~2 minutes)

1. Allez sur [vercel.com](https://vercel.com) → **Add New → Project**
2. **Import** le dépôt GitHub `b4z1z/retroai-agent`
3. Dans **Root Directory**, choisissez `marketplace`
4. Framework preset : **Other** (site statique, aucun build)
5. **Deploy** — c'est tout. Chaque `git push` redéploie automatiquement.

Ensuite, mettez l'URL obtenue (ex. `https://baziz-plugins.vercel.app`) dans
`retroai_agent/plugins.py` (`URL_SITE`) si elle diffère.

> Alternative sans Vercel : GitHub Pages (Settings → Pages → branche main,
> dossier `/marketplace`) fonctionne aussi, c'est un site 100 % statique.

## ➕ Publier un plugin dans le marché

1. Écrivez votre plugin (contrat : voir [`../plugins/README.md`](../plugins/README.md))
2. Ajoutez le fichier dans `marketplace/plugins/`
3. Ajoutez son entrée dans `registry.json` :

```json
{
  "nom": "mon_outil",
  "fichier": "mon_outil.py",
  "description": "Ce que fait l'outil",
  "auteur": "votre-pseudo",
  "url": "https://raw.githubusercontent.com/b4z1z/retroai-agent/main/marketplace/plugins/mon_outil.py",
  "dangereux": false
}
```

4. Recopiez le même contenu dans **`registry.js`** (`window.REGISTRY = …`) —
   c'est lui qui permet au site de marcher même ouvert en double-clic
   (un test pytest vérifie que les deux fichiers restent identiques).
5. Ouvrez une **pull request** — une fois fusionnée, le plugin apparaît sur
   le site ET devient installable par tous les utilisateurs via `/plugins`.
