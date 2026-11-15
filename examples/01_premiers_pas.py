"""Exemple 1 : premiers pas avec forgekit.

Lance-le avec :  python examples/01_premiers_pas.py
"""
import pathlib
import sys

# Cette ligne permet de lancer l'exemple sans avoir fait `pip install .`.
# (Elle est inutile si tu as déjà installé forgekit.)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from forgekit import (  # noqa: E402
    Field,
    Pipeline,
    Schema,
    Timer,
    ValidationError,
    chunked,
    human_duration,
    human_size,
    slugify,
    truncate,
)

# --- 1. Le texte ---------------------------------------------------------
print("=== Texte ===")
titre = "Réseaux & Télécoms 2026"
print("slugify    :", slugify(titre))             # un nom propre pour un fichier ou une adresse web
print("human_size :", human_size(1_500_000))      # une taille lisible
print("durée      :", human_duration(3723))       # une durée lisible
print("truncate   :", truncate("Un texte beaucoup trop long pour la place", 15))

# --- 2. Un pipeline : plusieurs étapes à la suite ---------------------------
print("\n=== Pipeline ===")
nettoyer = Pipeline(str.strip, str.lower)           # d'abord strip (enlever les espaces), puis lower (minuscules)
for mot in ["  BONJOUR ", "Awa  ", " PARIS"]:
    print(repr(mot), "->", repr(nettoyer(mot)))

# --- 3. Valider des données --------------------------------------------------
print("\n=== Validation ===")
utilisateur = Schema({
    "nom": Field(str, min=2),                       # texte d'au moins 2 caractères
    "age": Field(int, min=0, max=150, coerce=True),  # entier entre 0 et 150 ("21" est converti en 21)
})

bonnes_donnees = {"nom": "Awa", "age": "21"}
print("Données correctes ->", utilisateur.validate(bonnes_donnees))

mauvaises_donnees = {"nom": "A", "age": 200}
try:
    utilisateur.validate(mauvaises_donnees)
except ValidationError as erreur:
    print("Données fausses ->")
    for champ, message in erreur.errors.items():    # toutes les erreurs sont listées d'un coup
        print(f"   {champ} : {message}")

# --- 4. Découper une liste et chronométrer -----------------------------------
print("\n=== Chronomètre et blocs ===")
with Timer("découpage") as chrono:
    blocs = list(chunked(range(10), 4))             # des paquets de 4 éléments
print("blocs :", blocs)
print(chrono)                                       # affiche le temps écoulé
