"""Exemple 2 : réessais, cache, limiteur de débit et traitement parallèle.

Lance-le avec :  python examples/02_fiabilite_et_vitesse.py
Il prend environ 3 secondes : on simule des tâches lentes avec time.sleep.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # inutile après `pip install .`

from forgekit import RateLimiter, Timer, pmap, retry, ttl_cache  # noqa: E402

# --- 1. retry : réessayer quand ça échoue --------------------------------------
print("=== retry ===")
compteur = {"essais": 0}


@retry(attempts=5, delay=0.1, on_retry=lambda n, e: print(f"   essai {n} raté ({e}), on recommence..."))
def connexion_capricieuse():
    compteur["essais"] += 1
    if compteur["essais"] < 3:                      # échoue les 2 premières fois
        raise ConnectionError("réseau coupé")
    return "connecté !"


print("Résultat :", connexion_capricieuse(), f"(après {compteur['essais']} essais)")

# --- 2. ttl_cache : retenir un résultat ---------------------------------------
print("\n=== ttl_cache ===")


@ttl_cache(ttl=60)                                  # le résultat est gardé 60 secondes
def calcul_lent(n):
    time.sleep(0.5)                                 # on fait semblant de travailler
    return n * n


with Timer("1er appel") as t1:
    calcul_lent(12)
with Timer("2e appel ") as t2:
    calcul_lent(12)                                 # même valeur : réponse immédiate
print(t1)
print(t2)
print("Statistiques du cache :", calcul_lent.cache_info())

# --- 3. RateLimiter : ne pas aller trop vite ----------------------------------
print("\n=== RateLimiter ===")
limiteur = RateLimiter(rate=5, per=1.0)             # 5 appels par seconde au maximum
with Timer("8 appels") as t3:
    for i in range(8):
        with limiteur:                              # patiente tout seul si nécessaire
            pass
print(t3, "(sans limite, ce serait presque instantané)")

# --- 4. pmap : faire plusieurs choses en même temps ----------------------------
print("\n=== pmap ===")


def tache_lente(x):
    time.sleep(0.3)
    return x * 10


with Timer("un par un ") as t4:
    resultat_simple = [tache_lente(x) for x in range(8)]
with Timer("8 en même temps") as t5:
    resultat_parallele = pmap(tache_lente, range(8), workers=8)
print(t4)
print(t5)
print("Mêmes résultats :", resultat_simple == resultat_parallele)
