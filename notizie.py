"""Titoli delle notizie di borsa da Google News (gratis, in italiano)."""
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import certifi

_SSL = ssl.create_default_context(cafile=certifi.where())


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


def raccogli(posseduti, nomi):
    """Notizie generali sulla Borsa di Milano più quelle dei titoli in portafoglio."""
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
    return out
