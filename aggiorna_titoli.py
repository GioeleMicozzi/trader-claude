"""Scarica l'elenco di tutte le azioni di Piazza Affari (Euronext Milan, compreso lo STAR,
ed Euronext Growth Milan) dal listino A–Z di Borsa Italiana, trova il simbolo Yahoo di
ognuna dal codice ISIN e scrive titoli.json. Le azioni estere del Global Equity Market
restano fuori. Da rilanciare ogni tanto: entrano ed escono società."""
import json
import re
import ssl
import string
import urllib.parse
import urllib.request

import certifi

import config

_SSL = ssl.create_default_context(cafile=certifi.where())
MERCATI = {"MTAA": "Euronext Milan", "EXGM": "Euronext Growth Milan"}
RIGA = re.compile(r'/borsa/azioni/(?:[a-z-]+/)?scheda/([A-Z0-9]{12})-(\w+)\.html\?lang=it" '
                  r'title="Accedi alla scheda strumento&nbsp;([^"]+)"')


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=_SSL, timeout=30) as r:
        return r.read().decode("utf8", "ignore")


def listino():
    """{isin: (nome, mercato)} per tutte le lettere e le pagine del listino A–Z."""
    out = {}
    for iniziale in string.ascii_uppercase + "0":
        for pagina in range(1, 40):
            html = _get(f"https://www.borsaitaliana.it/borsa/azioni/listino-a-z.html"
                        f"?initial={iniziale}&lang=it&page={pagina}")
            nuove = 0
            for isin, mercato, nome in RIGA.findall(html):
                if mercato in MERCATI and isin not in out:
                    out[isin] = (nome.replace("&amp;", "&").strip(), MERCATI[mercato])
                    nuove += 1
            if f"page={pagina + 1}" not in html:
                break
    return out


def simbolo_yahoo(isin):
    url = ("https://query2.finance.yahoo.com/v1/finance/search?quotesCount=5&newsCount=0&q="
           + urllib.parse.quote(isin))
    for q in json.loads(_get(url)).get("quotes", []):
        if q.get("symbol", "").endswith(".MI"):
            return q["symbol"]
    return None


def main():
    societa = listino()
    print(f"{len(societa)} azioni nel listino")
    titoli, senza = {}, []
    for isin, (nome, mercato) in sorted(societa.items(), key=lambda kv: kv[1][0]):
        try:
            s = simbolo_yahoo(isin)
        except Exception:
            s = None
        if s:
            titoli[s] = {"nome": nome, "mercato": mercato, "isin": isin}
        else:
            senza.append(nome)
    config.ELENCO_TITOLI.write_text(json.dumps(titoli, indent=1, ensure_ascii=False))
    print(f"{len(titoli)} con simbolo Yahoo; senza: {len(senza)} {senza[:20]}")


if __name__ == "__main__":
    main()
