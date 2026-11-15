# Publier forgekit : le guide pas à pas

Ce guide part de zéro. Tu peux t'arrêter à n'importe quel niveau : chacun est déjà utile.

| Niveau | Résultat | Difficulté |
|---|---|---|
| **1. GitHub** | Ton code est en ligne, visible et installable avec `pip install git+https://...` | Facile |
| **2. PyPI à la main** | N'importe qui fait `pip install forgekit` | Moyen |
| **3. PyPI automatique** | Tu crées une version, tout part tout seul | Un peu plus avancé |

---

## Étape 0 : vérifier le nom (à faire avant tout)

Le nom du paquet doit être **unique sur PyPI**. Deux vérifications :

1. Ouvre `https://pypi.org/project/forgekit/` dans ton navigateur.
   - Page **« 404 Not Found »** : le nom est libre.
   - Une vraie page de projet : le nom est pris, il faut en choisir un autre.
2. Attention à la confusion : un projet différent, **`forgekit-cli`** (un outil de génération de projets lié au site forgekit.info), existe déjà sur PyPI. Même si `forgekit` seul est libre, les gens pourraient confondre les deux. **Un nom plus original est préférable**, par exemple `outilsfr`, `boite-a-outils-py`, `pyforge-utils`, etc. (évite tout nom qui te rappelle : ton nom, ton pseudo habituel, ta ville).

Les noms sur PyPI ne sont pas réservables à l'avance et ne se récupèrent pas facilement : choisis bien avant de publier.

### Comment renommer le projet

Si tu choisis un nouveau nom (exemple : `monkit`) :

1. Renomme le dossier `forgekit/` en `monkit/`.
2. Remplace le mot `forgekit` par `monkit` **dans tout le projet**.
   Dans VS Code : `Ctrl + Maj + H`, tape `forgekit` puis `monkit`, clique sur « Tout remplacer ».
   (Sur Linux ou Mac, tu peux aussi faire : `grep -rl forgekit . | xargs sed -i 's/forgekit/monkit/g'`)
3. Relance les tests : `python -m unittest discover -s tests -t .` (tu dois voir `OK`).

Un nom de paquet ne doit contenir que des lettres, chiffres, tirets ou underscores. Le nom du dossier de code (celui qu'on importe) doit rester sans tiret.

---

## Rester anonyme (à lire avant d'envoyer quoi que ce soit)

Tout ce qui est publié est public, et presque impossible à effacer ensuite. Voici les endroits où ton identité peut fuiter, et comment les fermer. Le projet lui-même a déjà été nettoyé : la licence est au nom de « forgekit contributors » et aucun nom ni ville ne figure dans les fichiers.

1. **Ton compte GitHub** : choisis un nom d'utilisateur qui n'a aucun rapport avec ton vrai nom, avec une adresse e-mail dédiée (pas ton adresse habituelle). Laisse vides le nom, la photo et le lieu du profil.
2. **L'identité dans l'historique Git** : chaque « commit » enregistre un nom et un e-mail, **visibles par tout le monde**. À régler *avant* le premier commit :
   - Sur GitHub : **Settings → Emails**, coche « Keep my email addresses private » et « Block command line pushes that expose my email ».
   - Note l'adresse « noreply » que GitHub t'affiche (de la forme `123456+pseudo@users.noreply.github.com`).
   - Dans ton terminal :
     ```bash
     git config --global user.name "ton-pseudo"
     git config --global user.email "123456+pseudo@users.noreply.github.com"
     ```
   - Vérifie ce qui sera publié, avant le `git push` : `git log --format="%an <%ae>"` ne doit montrer que ton pseudo.
3. **Le fichier `pyproject.toml`** : les champs `authors` et `maintainers` sont publiés sur PyPI. Laisse-les absents (comme maintenant) ou mets un pseudo, mais jamais ton e-mail personnel.
4. **Le contenu des fichiers** : avant d'envoyer, relis. Cherche ton nom, ta ville, ton établissement, et les chemins du type `C:\Users\TonNom\...` qu'on copie parfois dans un message d'erreur ou un commentaire.
5. **Ton compte PyPI** : prends le même pseudo et une adresse e-mail dédiée.

Honnêteté : l'anonymat n'est jamais total. GitHub et PyPI connaissent l'adresse e-mail du compte, et les habitudes d'écriture ou les horaires peuvent aussi trahir quelqu'un. Ces précautions suffisent pour ne pas apparaître sous ton vrai nom, pas pour résister à une enquête.

---

## Niveau 1 : mettre le code sur GitHub

### Option A : sans rien installer (la plus simple)

1. Crée un compte sur **github.com** (gratuit).
2. Clique sur **New repository** (bouton « + » en haut à droite).
   - Nom : `forgekit` (ou ton nouveau nom).
   - Choisis **Public**.
   - Ne coche **aucune** case « Add a README / .gitignore / license » : le projet les contient déjà.
3. Sur la page du dépôt vide, clique sur **« uploading an existing file »**.
4. Glisse-dépose **le contenu** du dossier du projet (le dossier `forgekit/`, `tests/`, `examples/`, `README.md`, `LICENSE`, `pyproject.toml`, `.gitignore`...).
   Pour le dossier caché `.github`, envoie-le aussi si ton ordinateur l'affiche ; sinon, passe à l'option B.
5. Clique sur **Commit changes**.

### Option B : avec Git (recommandée, tu en auras besoin plus tard)

1. Installe Git : **git-scm.com**.
2. Dis à Git qui tu es (une seule fois sur ton ordinateur). **Pour rester anonyme, utilise ton pseudo et l'adresse « noreply » de GitHub**, comme expliqué dans la section ci-dessus, pas ton vrai nom ni ton e-mail habituel :
   ```bash
   git config --global user.name "ton-pseudo"
   git config --global user.email "123456+pseudo@users.noreply.github.com"
   ```
3. Dans le dossier du projet :
   ```bash
   git init
   git add .
   git commit -m "Première version"
   ```
4. Crée le dépôt vide sur GitHub (étape 2 de l'option A), puis relie-le et envoie ton code :
   ```bash
   git branch -M main
   git remote add origin https://github.com/TON-PSEUDO/forgekit.git
   git push -u origin main
   ```
   Remplace `TON-PSEUDO` par ton nom d'utilisateur GitHub. Git te demandera de te connecter.
   Si ça te bloque, **GitHub Desktop** (application graphique gratuite) fait la même chose avec des boutons.

### Le résultat

Tout le monde peut maintenant installer ta bibliothèque avec :
```bash
pip install git+https://github.com/TON-PSEUDO/forgekit.git
```

**Dès que le code est sur GitHub**, les tests se lancent automatiquement (onglet **Actions**) sur Python 3.9 à 3.13. Si une version échoue, tu le verras là.

---

## Niveau 2 : publier sur PyPI à la main

PyPI est le grand magasin des bibliothèques Python : c'est lui qu'interroge `pip install`.

### 1. Crée tes comptes

- **pypi.org** : le vrai site. L'activation de la double authentification (2FA) est exigée.
- **test.pypi.org** : un site d'entraînement, **séparé** (autre compte, autres identifiants), où tu peux te tromper sans conséquence.

### 2. Prépare le fichier `pyproject.toml`

Ouvre-le et vérifie :
- `name` : ton nom de paquet (étape 0).
- `authors` : laisse ce champ absent pour rester anonyme (ou mets un pseudo). N'y mets jamais ton e-mail personnel.
- Décommente la partie `[project.urls]` et remplace `TON-PSEUDO` (après avoir créé ton dépôt GitHub).

La version se règle **à un seul endroit** : la ligne `__version__ = "1.0.0"` dans `forgekit/__init__.py`.

### 3. Crée un jeton (token)

Sur pypi.org : **Account settings → API tokens → Add API token**.
Pour le premier envoi, choisis « Entire account ». Copie le jeton (il commence par `pypi-`) et garde-le dans un endroit sûr : **il ne s'affiche qu'une fois**. Fais de même sur test.pypi.org.

**Ne mets jamais ce jeton dans ton code ni sur GitHub.** Celui qui l'a peut publier à ta place.

### 4. Construis le paquet

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Le dossier `dist/` contient maintenant deux fichiers (`.whl` et `.tar.gz`). La commande `twine check` doit afficher `PASSED`.

### 5. Entraîne-toi sur TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
```
- Nom d'utilisateur : `__token__` (tel quel, avec les deux tirets bas)
- Mot de passe : ton jeton TestPyPI

Teste l'installation dans un environnement vide :
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps forgekit
python -c "import forgekit; print(forgekit.__version__)"
```

### 6. Publie pour de vrai

```bash
python -m twine upload dist/*
```
Même principe, avec ton jeton PyPI. Après quelques instants, `pip install forgekit` fonctionne partout dans le monde.

### À savoir absolument

- **Un numéro de version ne peut être envoyé qu'une seule fois.** Même si tu supprimes la version, tu ne peux pas la renvoyer. Pour corriger quelque chose, augmente la version (`1.0.0` → `1.0.1`) puis reconstruis (vide le dossier `dist/` avant).
- Chaque publication est **publique et définitive**. Relis le `README.md` et le `LICENSE` avant.

---

## Niveau 3 : publication automatique (sans mot de passe)

Le fichier `.github/workflows/publish.yml` est déjà dans le projet. Quand tu crées une version, GitHub lance les tests, construit le paquet et l'envoie sur PyPI, **sans que tu aies de jeton à stocker** (c'est la « publication de confiance » : PyPI fait confiance à ton dépôt GitHub).

### Mise en place (une seule fois)

1. Ton code doit être sur GitHub (niveau 1).
2. Sur **pypi.org**, dans les réglages de **publication** (Publishing) de ton compte, ajoute un **« pending publisher »** avec :
   - le nom du projet (celui de ton `pyproject.toml`),
   - ton nom d'utilisateur GitHub et le nom du dépôt,
   - le nom du fichier : `publish.yml`,
   - le nom d'environnement : `pypi`.
3. Sur **GitHub**, dans ton dépôt : **Settings → Environments → New environment**, nom : `pypi`.
   Tu peux cocher « Required reviewers » pour devoir valider à la main chaque publication (conseillé).

### Publier une nouvelle version

```bash
# 1. Change __version__ dans forgekit/__init__.py (par exemple "1.0.1"), puis :
git add .
git commit -m "Version 1.0.1"
git tag v1.0.1
git push
git push --tags
```
Va voir l'onglet **Actions** sur GitHub : les tests tournent, puis le paquet part sur PyPI.

---

## Après la publication : ce qui fait qu'une bibliothèque vit

- **Le README** est ta vitrine : c'est la page qu'on lit en premier. Garde-le simple.
- **Réponds aux questions** (onglet *Issues* sur GitHub), même courtement.
- **Un numéro de version qui a du sens** : `1.0.0` → `1.0.1` pour une correction, `1.1.0` pour une nouveauté, `2.0.0` si tu casses ce qui existait.
- **Ajoute des tests** quand tu corriges un bug : c'est la meilleure garantie de ne pas le recréer.

## Pour aller plus loin

- [Guide officiel : publier avec GitHub Actions (publication de confiance)](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [Guide officiel : emballer un projet Python](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
