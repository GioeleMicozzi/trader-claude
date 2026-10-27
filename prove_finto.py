"""Una sveglia con dati, notizie e cervello finti, senza rete: la usa prove_rompilo.py.
Si comanda con variabili d'ambiente:
  TRADER_STATO    cartella di prova (obbligatoria: il conto vero non si tocca)
  FINTO_ORA       l'ora della sveglia, es. 2026-10-26T09:40
  FINTO_ORA_DOPO  l'ora che il programma vede dopo la risposta di Claude (prova dell'orologio)
  FINTO_CERVELLO  file JSON con la lista delle risposte di Claude, una per chiamata;
                  una risposta "giu" fa fallire la chiamata, "troncato" dà un JSON a metà
  FINTO_LENTO     secondi che Claude impiega a rispondere
  FINTO_PREZZI    "giu" = i prezzi non arrivano
  FINTO_PAUSA     "prima_di_salvare" o "scrittura_a_meta": si ferma lì, per essere ucciso"""
import json
import os
import sys
import time
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

assert os.environ.get("TRADER_STATO"), "senza TRADER_STATO toccherei il conto vero"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402

STATO = config.STATO
STATO.mkdir(exist_ok=True)
config.TITOLI = {"ISP.MI": "Intesa Sanpaolo", "ENEL.MI": "Enel", "ENI.MI": "Eni", "SMALL.MI": "Piccola"}
PREZZI = {"ISP.MI": 5.0, "ENEL.MI": 9.0, "ENI.MI": 15.0, "SMALL.MI": 2.0}
PREZZI.update(json.loads(os.environ.get("FINTO_LISTINO", "{}")))
SCAMBI = {"SMALL.MI": 20_000}

import conto  # noqa: E402
import dashboard  # noqa: E402
import dati  # noqa: E402
import decisore  # noqa: E402
import giro  # noqa: E402
import notizie  # noqa: E402
import telegram  # noqa: E402

ROMA = ZoneInfo("Europe/Rome")
orologio = {"ora": datetime.fromisoformat(os.environ.get("FINTO_ORA", "2026-10-26T09:40")).replace(tzinfo=ROMA)}
giro.adesso = lambda: orologio["ora"]


def _tutti(titoli):
    if os.environ.get("FINTO_PREZZI") == "giu":
        return {}, list(titoli)
    return {s: {"date": [], "chiusure": [p] * 300, "ultimo": p, "scambi_medi": SCAMBI.get(s, 5_000_000)}
            for s, p in PREZZI.items()}, []


def _storico(*a):
    raise OSError("indice finto non disponibile")


dati.tutti, dati.storico = _tutti, _storico
notizie.raccogli = lambda *a: []
sys.modules["previsioni"] = types.SimpleNamespace(prevedi=lambda prezzi: None)
sys.modules["fondamentali"] = types.SimpleNamespace(tutti=lambda prezzi: {})


def _invia(testo):
    with open(STATO / "messaggi.txt", "a") as f:
        f.write(testo + "\n---\n")


telegram.invia = _invia


def _chiama_claude(sistema, prompt, schema):
    chiamate = STATO / "chiamate_claude.txt"
    n = len(chiamate.read_text().splitlines()) if chiamate.exists() else 0
    with open(chiamate, "a") as f:
        f.write("chiamata\n")
    time.sleep(float(os.environ.get("FINTO_LENTO", "0")))
    risposte = json.loads(Path(os.environ["FINTO_CERVELLO"]).read_text())
    r = risposte[min(n, len(risposte) - 1)]
    if os.environ.get("FINTO_ORA_DOPO"):
        orologio["ora"] = datetime.fromisoformat(os.environ["FINTO_ORA_DOPO"]).replace(tzinfo=ROMA)
    if r == "giu":
        raise RuntimeError("claude -p non è andato: timeout")
    if r == "troncato":
        return json.loads('{"analisi": "Il mercato oggi', strict=False)
    return r


decisore._chiama_claude = _chiama_claude

_salva = conto.salva


def _salva_con_pausa(c, copia=None):
    pausa = os.environ.get("FINTO_PAUSA")
    if pausa == "scrittura_a_meta":
        testo = json.dumps(c)
        config.CONTO.write_text(testo[:len(testo) // 2])
    if pausa:
        (STATO / "in_pausa").touch()
        time.sleep(60)
    _salva(c, copia)


conto.salva = _salva_con_pausa

if __name__ == "__main__":
    if sys.argv[1:] == ["sentinella"]:
        import sentinella
        sentinella.main()
    else:
        giro.main()
