"""Prezzi della Borsa Italiana da Yahoo Finance (gratis, ritardo di circa 15 minuti)."""
import json
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import certifi

_SSL = ssl.create_default_context(cafile=certifi.where())


def _scarica(simbolo, intervallo, periodo):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
           f"?interval={intervallo}&range={periodo}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL, timeout=30) as r:
        return json.load(r)["chart"]["result"][0]


def storico(simbolo, intervallo="1d", periodo="2y"):
    """Ritorna (date, chiusure, volumi, ultimo_prezzo). Le chiusure mancanti restano None."""
    d = _scarica(simbolo, intervallo, periodo)
    q = d["indicators"]["quote"][0]
    date = [datetime.fromtimestamp(t, timezone.utc) for t in d.get("timestamp", [])]
    return date, q["close"], q["volume"], d["meta"].get("regularMarketPrice")


def _uno(simbolo):
    date, chiusure, volumi, ultimo = storico(simbolo)
    coppie = [(t, c, v) for t, c, v in zip(date, chiusure, volumi) if c is not None]
    if len(coppie) < 60 or not ultimo:
        raise ValueError("storico troppo corto")
    ultimi20 = coppie[-20:]
    return {
        "date": [t.date().isoformat() for t, _, _ in coppie],
        "chiusure": [round(c, 4) for _, c, _ in coppie],
        "ultimo": ultimo,
        # Euro scambiati in media al giorno nelle ultime 20 sedute: misura quanto è liquido.
        "scambi_medi": sum(c * (v or 0) for _, c, v in ultimi20) / len(ultimi20),
    }


def tutti(titoli):
    """Scarica lo storico giornaliero di ogni titolo (8 alla volta); salta quelli che non rispondono."""
    out, saltati = {}, []
    with ThreadPoolExecutor(8) as pool:
        for simbolo, futuro in [(s, pool.submit(_uno, s)) for s in titoli]:
            try:
                out[simbolo] = futuro.result()
            except Exception as e:
                saltati.append(f"{simbolo}: {e}")
    return out, saltati
