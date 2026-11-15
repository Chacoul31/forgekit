# forgekit

Une petite boîte à outils Python qui t'évite de réécrire les mêmes morceaux de code dans chaque projet.
**Aucune installation compliquée, aucune dépendance** : uniquement du Python.

---

## C'est quoi, concrètement ?

Quand on programme, on retombe sans cesse sur les mêmes problèmes :

- « Mon téléchargement échoue de temps en temps, comment réessayer automatiquement ? »
- « Ce calcul est lent et je le refais 100 fois, comment le retenir ? »
- « Comment traiter 200 fichiers en même temps au lieu d'un par un ? »
- « Comment vérifier que les données reçues sont correctes ? »

`forgekit` répond à ces questions avec **une ligne de code** chacune.

## Pour qui ?

Pour toute personne qui sait écrire une fonction en Python. Pas besoin d'être expert : chaque outil
est expliqué ci-dessous avec un exemple, et le dossier `examples/` contient des programmes
que tu peux lancer tout de suite.

---

## Installation

Choisis **une** des trois façons.

**1. La plus simple : copier le dossier.**
Copie le dossier `forgekit/` à côté de ton fichier Python. C'est tout, `import forgekit` fonctionne.

**2. Avec pip, depuis le dossier du projet.**
```bash
pip install .
```

**3. Une fois publiée sur internet** (voir `PUBLIER.md`) :
```bash
pip install forgekit
```

## Ton premier test (30 secondes)

Crée un fichier `test.py` à côté du dossier `forgekit/` :

```python
from forgekit import slugify, human_size, human_duration

print(slugify("Réseaux & Télécoms 2026"))   # reseaux-telecoms-2026
print(human_size(1536))                      # 1.5 Ko
print(human_duration(3723))                  # 1 h 2 min 3 s
```

Lance-le avec `python test.py`. Si tu vois les trois lignes de résultat, tout fonctionne.

---

## Les outils, un par un

> **Petit mot sur `@`** : une ligne qui commence par `@` juste au-dessus d'une fonction s'appelle
> un *décorateur*. Pense à un super-pouvoir qu'on colle sur la fonction (réessayer, retenir le
> résultat...). Tu n'as pas besoin de comprendre comment c'est fait pour t'en servir.

### 1. Réessayer automatiquement : `retry`

**Problème** : un appel réseau échoue de temps en temps, mais réussit souvent au deuxième essai.

```python
from forgekit import retry

@retry(attempts=5, delay=1)        # 5 essais maximum, attend 1 s, puis 2 s, puis 4 s...
def telecharger(url):
    ...
```

### 2. Retenir un résultat : `ttl_cache`

**Problème** : une fonction est lente et on l'appelle souvent avec les mêmes valeurs.

```python
from forgekit import ttl_cache

@ttl_cache(ttl=60)                 # garde le résultat 60 secondes
def cours_du_jour(devise):
    ...
```

Le premier appel est lent, les suivants sont instantanés. *TTL* veut dire « durée de vie » :
après 60 secondes, le résultat est oublié et recalculé.
`DiskCache` fait la même chose mais écrit dans un fichier : le résultat survit même si tu fermes le programme.

### 3. Ne pas aller trop vite : `RateLimiter`

**Problème** : un site ou une API te bloque si tu fais plus de 5 requêtes par seconde.

```python
from forgekit import RateLimiter

limiteur = RateLimiter(rate=5)     # 5 appels par seconde au maximum
for url in urls:
    with limiteur:                 # attend automatiquement si tu vas trop vite
        appeler(url)
```

### 4. Mesurer le temps : `Timer` et `timed`

```python
from forgekit import Timer

with Timer("chargement") as t:
    charger_les_donnees()
print(t)                           # chargement: 2.3 s
```

### 5. Faire plusieurs choses en même temps : `pmap`

**Problème** : tu dois traiter beaucoup d'éléments, et chacun attend (réseau, disque...).

```python
from forgekit import pmap

resultats = pmap(traiter, fichiers, workers=8)   # 8 à la fois, résultats dans le bon ordre
```

Si un élément échoue, tu choisis : `on_error="raise"` (tout s'arrête),
`"collect"` (l'erreur est rangée dans les résultats) ou `"skip"` (on l'ignore).
Pour du code `async`, utilise `async_map(fonction, elements, limit=10)`.

### 6. Vérifier des données : `Schema` et `Field`

**Problème** : des données arrivent (formulaire, fichier JSON...) et peuvent être fausses.

```python
from forgekit import Schema, Field, ValidationError

utilisateur = Schema({
    "nom": Field(str, min=2),                   # texte d'au moins 2 caractères
    "age": Field(int, min=0, coerce=True),      # entier >= 0, "21" accepté et converti
})

try:
    propre = utilisateur.validate({"nom": "Awa", "age": "21"})
except ValidationError as e:
    print(e.errors)                             # TOUTES les erreurs d'un coup
```

### 7. Lire une configuration : `Config`

**Problème** : tes réglages (port, mot de passe, adresse...) ne doivent pas être écrits en dur dans le code.

```python
from forgekit import Config

cfg = Config.from_file("config.json").merge(Config.from_env("MONAPP"))
port = cfg.get("serveur.port", 8000, cast=int)   # 8000 si le réglage n'existe pas
```

### 8. Enchaîner des étapes : `Pipeline`

```python
from forgekit import Pipeline

nettoyer = Pipeline(str.strip, str.lower)        # d'abord strip, puis lower
nettoyer("  BONJOUR ")                           # 'bonjour'
list(nettoyer.map(["A ", " B"]))                 # ['a', 'b']
```

### 9. Prévenir une partie du programme depuis une autre : `EventBus`

```python
from forgekit import EventBus

bus = EventBus()

@bus.on("fichier.recu")
def afficher(nom):
    print("Reçu :", nom)

bus.emit("fichier.recu", "rapport.pdf")          # affiche : Reçu : rapport.pdf
```

### 10. Des logs lisibles : `get_logger`

```python
from forgekit import get_logger

log = get_logger("monapp", "INFO", file="app.log")
log.info("Démarrage")                            # écran (en couleur) + fichier
```

### 11. Manipuler du texte : `slugify`, `truncate`, `human_size`...

```python
from forgekit import slugify, truncate, snake_case, human_duration

slugify("Mon Titre à moi !")                     # 'mon-titre-a-moi'
truncate("Un texte beaucoup trop long", 12)      # 'Un texte be…'
snake_case("MaVariableTest")                     # 'ma_variable_test'
human_duration(90061)                            # '1 j 1 h 1 min 1 s'
```

### 12. Petits utilitaires : `chunked`, `flatten`, `write_json`...

```python
from forgekit import chunked, flatten, write_json, read_json

list(chunked(range(5), 2))                       # [[0, 1], [2, 3], [4]]
list(flatten([1, [2, [3, 4]]]))                  # [1, 2, 3, 4]
write_json("etat.json", {"nom": "Awa"})          # écriture sûre : jamais de fichier cassé à moitié
```

---

## Exemples prêts à lancer

Dans le dossier `examples/` :

| Fichier | Ce que tu y découvres |
|---|---|
| `01_premiers_pas.py` | texte, validation, pipeline, chronomètre |
| `02_fiabilite_et_vitesse.py` | réessais, cache, limiteur de débit, traitement parallèle (avec mesure du temps gagné) |
| `03_config_evenements_logs.py` | configuration, événements, logs, fichiers JSON |

```bash
python examples/01_premiers_pas.py
```

Chaque fichier est commenté ligne par ligne. Modifie-les, casse-les, c'est le meilleur moyen d'apprendre.

---

## Petit lexique

- **Fonction** : un bloc de code auquel on donne un nom pour le réutiliser.
- **Décorateur** (`@truc`) : un ajout collé au-dessus d'une fonction pour lui donner un pouvoir.
- **`with ... :`** : « fais ceci pendant que cette chose est active » (le chronomètre tourne, le limiteur surveille...), puis nettoie tout seul à la fin.
- **Cache** : une mémoire qui retient des résultats déjà calculés pour ne pas les recalculer.
- **Thread** : une « voie » d'exécution. Plusieurs threads permettent d'attendre plusieurs choses en même temps.
- **Dépendance** : un autre programme dont le tien a besoin. `forgekit` n'en a aucune.
- **Package / bibliothèque** : du code écrit par quelqu'un d'autre, que tu importes avec `import`.

## Erreurs fréquentes

**`ModuleNotFoundError: No module named 'forgekit'`**
Python ne trouve pas le dossier. Soit tu lances ton fichier depuis le dossier qui contient `forgekit/`, soit tu fais `pip install .` une fois.

**`ValidationError`**
Ce n'est pas un bug : c'est l'outil qui t'indique que des données sont fausses. Affiche `e.errors` pour voir lesquelles.

**`pmap` avec `backend="process"` plante avec une fonction `lambda`**
Avec les processus, la fonction doit être écrite normalement avec `def` au niveau du fichier, pas en `lambda`.

## Vérifier que tout marche

```bash
python -m unittest discover -s tests -t .
```
Tu dois voir `OK` à la fin. Ces 68 tests ont été passés sur Python 3.13 ; le code vise Python 3.9+ (TOML demande 3.11+).

## Publier ta bibliothèque

Voir **`PUBLIER.md`** : un guide pas à pas pour la mettre sur GitHub, puis sur PyPI (pour que n'importe qui puisse faire `pip install`).

## Notes de sécurité

- `DiskCache` utilise `pickle` : n'ouvre jamais un fichier de cache qui vient d'une source inconnue.
- Ne mets jamais de mots de passe ou de clés dans le code : utilise `Config.from_env` ou un fichier `.env` (déjà ignoré par Git grâce au `.gitignore`).

## Licence

MIT : tu peux utiliser, modifier et partager librement. Voir le fichier `LICENSE`.
