"""Messaggi su Telegram a ogni sveglia. Il token del bot sta in stato/telegram.json,
leggibile solo dal tuo utente; lo crea collega-telegram.command."""
import json
import ssl
import sys
import urllib.parse
import urllib.request

import certifi

import config

FILE = config.STATO / "telegram.json"
_SSL = ssl.create_default_context(cafile=certifi.where())

TITOLI_MOMENTI = {"piano": "☕ Piano del mattino", "apertura": "🔔 Apertura", "meta": "🕐 Metà seduta",
                  "chiusura": "🏁 Chiusura", "pagella": "📋 Pagella della settimana",
                  "giro": "🔄 Sveglia", "prova": "🧪 Prova", "sentinella": "👁 Sentinella",
                  "bilancio": "📒 Bilancio della giornata"}


def _chiama(token, metodo, **parametri):
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    dati = urllib.parse.urlencode(parametri).encode() if parametri else None
    with urllib.request.urlopen(url, data=dati, context=_SSL, timeout=30) as r:
        return json.load(r)


def invia(testo):
    """Manda un messaggio. Se Telegram non è collegato o non risponde, non blocca il trader."""
    if not FILE.exists():
        return
    try:
        impostazioni = json.loads(FILE.read_text())
        for i in range(0, len(testo), 4000):
            _chiama(impostazioni["token"], "sendMessage", chat_id=impostazioni["chat_id"],
                    text=testo[i:i + 4000], disable_web_page_preview="true")
    except Exception as e:
        print("Telegram non raggiungibile:", e, file=sys.stderr)


def _euro(x):
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _titolo(voce):
    return TITOLI_MOMENTI.get(voce.get("momento"), "Sveglia") + f" · {voce['quando'][11:16]}"


def partenza(voce):
    """Il primo messaggio: la sveglia è partita. Se dopo non arriva ✅ o ❌, si è fermata a metà."""
    righe = [f"▶️ {_titolo(voce)} · partita"]
    righe += ["⚠️ " + a for a in voce.get("avvisi", [])]
    return "\n".join(righe)


def resoconto(voce):
    """Il testo del messaggio di fine sveglia, dalla voce del registro."""
    coda = ["", f"Prossima sveglia: {voce.get('prossima_sveglia', '—')}", f"📊 Situazione completa: {config.DASHBOARD_WEB}",
            f"· sveglia {voce.get('id', '')}"]
    if "errore" in voce:
        return "\n".join([f"❌ {_titolo(voce)}", "La sveglia non è andata a buon fine:",
                          voce["errore"].strip().splitlines()[-1], "Il conto non è stato toccato."] + coda)
    righe = [f"✅ {_titolo(voce)}"]
    if "pagella" in voce:
        p = voce["pagella"]
        righe += [f"Voto {p['voto']}/10", p["giudizio"], "", "Errore della settimana: " + p["errore_della_settimana"]]
        if p["nuova_regola"].strip():
            righe += ["", "Nuova regola: " + p["nuova_regola"]]
        return "\n".join(righe + coda)
    if voce.get("cervello_assente"):
        righe.append("🧠 Cervello non disponibile: applico solo lo stop loss.")
    tot = voce["patrimonio"]
    rend = f"{(tot / config.CAPITALE_INIZIALE - 1) * 100:+.2f}%".replace(".", ",")
    pl = voce.get("pl_giorno", 0)
    righe.append(f"Patrimonio {_euro(tot)} ({rend} dall'inizio) · oggi {'+' if pl >= 0 else '−'}{_euro(abs(pl))}")
    if voce["eseguiti"]:
        righe.append("")
        for o in voce["eseguiti"]:
            segno = "🟢 Compra" if o["azione"] == "compra" else "🔴 Vende"
            righe.append(f"{segno} {o['quantita']} {config.TITOLI.get(o['simbolo'], o['simbolo'])} a {o['prezzo']} — {o['motivo']}")
    else:
        righe.append("Nessun ordine.")
    for o in voce.get("scartati", []):
        righe.append(f"⛔ Respinto: {o.get('azione')} {o.get('simbolo')} — {o['perche']}")
    righe += ["", voce["decisione"]["analisi"]]
    if voce.get("momento") == "piano":
        righe += ["", "Piano: " + voce["decisione"]["testimone"]]
    if voce.get("errore_previsioni"):
        righe.append("\n(Senza previsioni Timestral in questa sveglia)")
    return "\n".join(righe + coda)
