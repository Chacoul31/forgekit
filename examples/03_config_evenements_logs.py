"""Exemple 3 : configuration, événements, logs et fichiers JSON.

Lance-le avec :  python examples/03_config_evenements_logs.py
"""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # inutile après `pip install .`

from forgekit import Config, EventBus, get_logger, read_json, write_json  # noqa: E402

# --- 1. Config : lire des réglages ---------------------------------------------
print("=== Config ===")
reglages_par_defaut = {"serveur": {"hote": "localhost", "port": 8000}, "debug": False}
cfg = Config(reglages_par_defaut)

# On simule des variables d'environnement (en vrai, elles viennent de ton ordinateur).
# MONAPP_SERVEUR__PORT=9000 veut dire : réglage "serveur.port" = 9000
faux_environnement = {"MONAPP_SERVEUR__PORT": "9000", "MONAPP_DEBUG": "true", "AUTRE": "ignoré"}
cfg = cfg.merge(Config.from_env("MONAPP", environ=faux_environnement))   # l'environnement gagne

print("hôte  :", cfg.get("serveur.hote"))                   # reste "localhost"
print("port  :", cfg.get("serveur.port", cast=int))         # devient 9000
print("debug :", cfg.get("debug"))                          # devient True
print("inconnu avec valeur par défaut :", cfg.get("clef.absente", "valeur par défaut"))

# --- 2. EventBus : prévenir sans que les parties se connaissent ----------------
print("\n=== EventBus ===")
bus = EventBus()


@bus.on("fichier.recu")                                     # "quand il y a un fichier reçu, fais ceci"
def afficher(nom):
    print("   Reçu :", nom)


@bus.on("fichier.recu")
def compter(nom):
    print("   Je note aussi :", nom.upper())


bus.on("*", lambda evenement, *args, **kw: print(f"   [journal] événement '{evenement}'"))  # "*" = tous les événements

print("On annonce un fichier :")
bus.emit("fichier.recu", "rapport.pdf")

# --- 3. Logs : des messages lisibles -------------------------------------------
print("\n=== Logs ===")
log = get_logger("exemple", "DEBUG")
log.debug("message de détail")
log.info("tout va bien")
log.warning("attention, quelque chose cloche")
log.error("là, c'est une erreur")

# --- 4. Fichiers JSON sûrs --------------------------------------------------------
print("\n=== JSON ===")
with tempfile.TemporaryDirectory() as dossier:              # un dossier temporaire, effacé à la fin
    chemin = pathlib.Path(dossier) / "etat.json"
    write_json(chemin, {"nom": "Awa", "ville": "Paris", "niveau": 2})
    print("Contenu relu :", read_json(chemin))
    print("Fichier absent avec valeur par défaut :", read_json(pathlib.Path(dossier) / "absent.json", default={}))
