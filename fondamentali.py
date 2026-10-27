"""Dati di bilancio e stime degli analisti da Yahoo Finance (gratis). Cambiano poco:
si scaricano una volta al giorno e si tengono in stato/fondamentali.json."""
import http.cookiejar
import json
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import certifi

import config

FILE = config.STATO / "fondamentali.json"
CAMPI = [  # (modulo Yahoo, campo, nome per Claude, moltiplicatore)
    ("summaryDetail", "trailingPE", "p/e_ultimi_12_mesi", 1),
    ("summaryDetail", "forwardPE", "p/e_atteso", 1),
    ("summaryDetail", "dividendYield", "dividendo_%", 100),
    ("defaultKeyStatistics", "priceToBook", "prezzo/valore_contabile", 1),
    ("financialData", "returnOnEquity", "roe_%", 100),
    ("financialData", "revenueGrowth", "crescita_ricavi_%", 100),
    ("financialData", "profitMargins", "margine_netto_%", 100),
    ("financialData", "debtToEquity", "debito/patrimonio_%", 1),
    ("financialData", "targetMeanPrice", "prezzo_obiettivo_medio_analisti", 1),
    ("financialData", "targetLowPrice", "prezzo_obiettivo_minimo", 1),
    ("financialData", "targetHighPrice", "prezzo_obiettivo_massimo", 1),
    ("financialData", "numberOfAnalystOpinions", "numero_analisti", 1),
]


def _sessione():
    ctx = ssl.create_default_context(cafile=certifi.where())
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                     urllib.request.HTTPSHandler(context=ctx))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    try:
        op.open("https://fc.yahoo.com", timeout=20)  # serve solo a ricevere il cookie
    except Exception:
        pass
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).read().decode()
    return op, crumb


def _scarica(op, crumb, simbolo):
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{simbolo}"
           f"?modules=summaryDetail,defaultKeyStatistics,financialData,calendarEvents,earnings&crumb={crumb}")
    d = json.load(op.open(url, timeout=20))["quoteSummary"]["result"][0]
    out = {}
    for modulo, campo, nome, molt in CAMPI:
        v = (d.get(modulo, {}).get(campo) or {}).get("raw")
        if v is not None:
            out[nome] = round(v * molt, 2)
    giudizio = d.get("financialData", {}).get("recommendationKey")
    if giudizio and giudizio != "none":
        out["giudizio_analisti"] = giudizio
    # Bilanci annuali (ricavi e utile in milioni, dal più vecchio) e data dei prossimi conti.
    anni = [a for a in d.get("earnings", {}).get("financialsChart", {}).get("yearly", [])
            if (a.get("revenue") or {}).get("raw")]
    if anni:
        periodo = f"{anni[0]['date']}-{str(anni[-1]['date'])[-2:]}: "
        out["ricavi_annui_mln"] = periodo + ">".join(f"{a['revenue']['raw'] / 1e6:.0f}" for a in anni)
        out["utile_annuo_mln"] = periodo + ">".join(f"{(a.get('earnings') or {}).get('raw', 0) / 1e6:.0f}" for a in anni)
    date_conti = d.get("calendarEvents", {}).get("earnings", {}).get("earningsDate") or []
    if date_conti:
        out["prossimi_conti"] = date_conti[0]["fmt"]
    return out


def tutti(titoli):
    oggi = date.today().isoformat()
    if FILE.exists():
        salvati = json.loads(FILE.read_text())
        if salvati.get("data") == oggi:
            return salvati["titoli"]
    op, crumb = _sessione()
    out = {}
    with ThreadPoolExecutor(8) as pool:
        for s, futuro in [(s, pool.submit(_scarica, op, crumb, s)) for s in titoli]:
            try:
                out[s] = futuro.result()
            except Exception:
                pass
    FILE.write_text(json.dumps({"data": oggi, "titoli": out}, ensure_ascii=False))
    return out
