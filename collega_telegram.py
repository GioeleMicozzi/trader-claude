"""Collega il bot Telegram: chiede il token, aspetta il tuo primo messaggio al bot,
salva token e chat in stato/telegram.json e manda un messaggio di prova."""
import getpass
import json
import os
import re
import subprocess
import time

import config
import telegram

def _dagli_appunti():
    testo = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    trovato = re.search(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b", testo)
    return trovato.group(0) if trovato else None


# Basta copiare il token (in Telegram: clic sul token): lo prendo dagli appunti appena compare.
print("Clicca sul token nella chat con BotFather: Telegram lo copia e io lo prendo da solo. Aspetto…")
token = None
for _ in range(600):
    token = _dagli_appunti()
    if token:
        break
    time.sleep(1)
if not token:
    token = getpass.getpass("Non l'ho visto negli appunti: incollalo qui e premi Invio: ").strip()
try:
    bot = telegram._chiama(token, "getMe")["result"]
except Exception:
    raise SystemExit("Token non valido: ricontrolla di averlo copiato tutto e rilancia.")

print(f"\nBot trovato: @{bot['username']}.")
os.system(f"open 'https://t.me/{bot['username']}'")
print("Ti ho aperto la chat con il bot: premi AVVIA (o scrivigli un messaggio qualsiasi). Aspetto…")

chat_id = None
for _ in range(180):
    aggiornamenti = telegram._chiama(token, "getUpdates")["result"]
    for a in aggiornamenti:
        messaggio = a.get("message") or {}
        if messaggio.get("chat", {}).get("type") == "private":
            chat_id = messaggio["chat"]["id"]
    if chat_id:
        break
    time.sleep(2)
if not chat_id:
    raise SystemExit("Non ho ricevuto il messaggio in 6 minuti: rilancia e scrivi al bot.")

config.STATO.mkdir(exist_ok=True)
telegram.FILE.write_text(json.dumps({"token": token, "chat_id": chat_id}))
os.chmod(telegram.FILE, 0o600)
telegram.invia("✅ Trader Claude collegato. Da adesso ti scrivo a ogni sveglia: "
               "8:30 piano, 9:35 apertura, 13:00 metà seduta, 17:15 chiusura, venerdì 18:00 pagella.")
print("\nFatto: ti è arrivato il messaggio di prova su Telegram.")
