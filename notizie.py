"""Titoli delle notizie di borsa da Google News (gratis, in italiano)."""
import json
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

import certifi

import config

_SSL = ssl.create_default_context(cafile=certifi.where())
FILE_CONTI = config.STATO / "conti.json"
ORE_CONTI = 4  # la ricerca sui conti di tutti i titoli si rifà al massimo ogni 4 ore
_PAROLE_CONTI = ("trimestr", "semestr", "nove mesi", "risultat", "conti", "ricavi", "fatturato", "utile",
                 "guidance", "bilancio", "margin", "dividend", "stime")
# Parole del nome troppo comuni per riconoscere la società in un titolo («Banca», «Group»...).
_GENERICHE = {"banca", "banco", "group", "gruppo", "holding", "italia", "italiana", "italy", "company",
              "industrie", "industries", "società", "international", "investimenti", "capital"}


def cerca(domanda, quante=8, giorni=2):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{domanda} when:{giorni}d")
           + "&hl=it&gl=IT&ceid=IT:it")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL, timeout=20) as r:
        voci = ET.parse(r).getroot().findall(".//item")
    out = []
    for v in voci[:quante]:
        try:
            quando = parsedate_to_datetime(v.findtext("pubDate")).strftime("%d/%m %H:%M")
        except Exception:
            quando = ""
        out.append(f"{quando} {v.findtext('title')}")
    return out


def _sui_conti(nome, titolo):
    """Tiene solo le notizie che nominano la società e parlano di conti: le altre sono omonimi o rumore."""
    t = titolo.lower()
    parole = [p for p in nome.lower().split() if len(p) >= 4 and p not in _GENERICHE] or [nome.lower().split()[0]]
    return any(p in t for p in parole) and any(p in t for p in _PAROLE_CONTI)


def conti(nomi):
    """Notizie degli ultimi 10 giorni sui conti (trimestrali, semestrali, annuali, guidance) di tutti i titoli.
    Sono quasi 400 ricerche: si tengono in stato/conti.json e si rifanno al massimo ogni ORE_CONTI ore."""
    if FILE_CONTI.exists():
        salvati = json.loads(FILE_CONTI.read_text())
        if time.time() - salvati.get("quando", 0) < ORE_CONTI * 3600:
            return salvati["conti"]
    domanda = '"{}" (trimestrale OR semestrale OR "nove mesi" OR risultati OR conti OR ricavi OR utile OR guidance)'

    def una(nome):
        try:
            return nome, [t for t in cerca(domanda.format(nome), 4, giorni=10) if _sui_conti(nome, t)][:3]
        except Exception:
            return nome, []

    with ThreadPoolExecutor(6) as pool:
        trovate = {nome: voci for nome, voci in pool.map(una, sorted(set(nomi.values()))) if voci}
    FILE_CONTI.write_text(json.dumps({"quando": time.time(), "conti": trovate}, ensure_ascii=False))
    return trovate


def raccogli(posseduti, nomi):
    """Notizie generali sulla Borsa di Milano, quelle dei titoli in portafoglio e quelle sui conti di tutti."""
    out = {}
    for chiave, domanda, n in [("mercato", "Piazza Affari", 12), ("bce_macro", "BCE tassi Borsa", 5)]:
        try:
            out[chiave] = cerca(domanda, n)
        except Exception as e:
            out[chiave] = [f"(notizie non disponibili: {e})"]
    for s in posseduti:
        nome = nomi.get(s, s)
        try:
            out[nome] = cerca(f'"{nome}" azioni', 4, giorni=3)
        except Exception:
            pass
    try:
        out["conti_ultimi_10_giorni"] = conti(nomi)
    except Exception as e:
        out["conti_ultimi_10_giorni"] = {"errore": f"(notizie sui conti non disponibili: {e})"}
    return out
