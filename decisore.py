"""Claude decide cosa comprare e vendere. Gira con `claude -p`, cioè con l'abbonamento:
nessuna chiave API, nessun costo a consumo."""
import json
import os
import shutil
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import config

SCHEMA_SVEGLIA = {
    "type": "object",
    "properties": {
        "analisi": {"type": "string", "description": "Lettura del mercato e delle notizie in poche frasi"},
        "ordini": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "azione": {"enum": ["compra", "vendi"]},
                    "simbolo": {"type": "string"},
                    "quantita": {"type": "integer", "minimum": 1},
                    "motivo": {"type": "string"},
                },
                "required": ["azione", "simbolo", "quantita", "motivo"],
            },
        },
        "testimone": {"type": "string",
                      "description": "Nota per te stesso alla prossima sveglia: cosa hai fatto, cosa resta, cosa controllare per primo"},
    },
    "required": ["analisi", "ordini", "testimone"],
}

SCHEMA_PAGELLA = {
    "type": "object",
    "properties": {
        "voto": {"type": "integer", "minimum": 1, "maximum": 10},
        "giudizio": {"type": "string", "description": "Com'è andata la settimana rispetto al FTSE MIB"},
        "errore_della_settimana": {"type": "string"},
        "nuova_regola": {"type": "string", "description": "Una regola da aggiungere per le prossime settimane, o stringa vuota"},
        "testimone": {"type": "string"},
    },
    "required": ["voto", "giudizio", "errore_della_settimana", "nuova_regola", "testimone"],
}

MOMENTI = {
    "piano": "Sveglia delle 8:30, borsa chiusa: i prezzi sono quelli di ieri. Prepara il piano della giornata. "
             "Gli ordini di questa sveglia NON vengono eseguiti: lascia la lista vuota e metti il piano nel testimone.",
    "apertura": "Sveglia del mattino a borsa aperta. Esegui il piano se i prezzi lo confermano.",
    "meta": "Sveglia di metà seduta. Intervieni solo se è cambiato qualcosa di importante.",
    "chiusura": "Sveglia di fine seduta (chiude alle 17:30). Ultimi aggiustamenti e bilancio della giornata.",
    "giro": "Sveglia durante la seduta.",
    "prova": "Sveglia fuori programma, lanciata a mano.",
}


def _istruzioni():
    testo = ("Sei il trader di un portafoglio di azioni italiane, conto in euro. Decidi da solo, senza chiedere conferme. "
             "Ogni acquisto paga 0,05% di commissione (minimo 1,25 €) più 0,1% di Tobin tax. "
             "Rispondi solo con il JSON richiesto.\n\n" + config.STRATEGIA.read_text())
    if config.REGOLE_IMPARATE.exists():
        testo += "\n\n## Regole che ti sei dato nelle pagelle passate\n" + config.REGOLE_IMPARATE.read_text()
    return testo


def _controlla(risposta, schema):
    """Una risposta troncata o con un campo mancante non deve arrivare al conto."""
    if not isinstance(risposta, dict):
        raise ValueError("la risposta non è un oggetto JSON")
    for campo in schema["required"]:
        if campo not in risposta:
            raise ValueError(f"manca il campo «{campo}»")
        tipo = schema["properties"][campo].get("type")
        atteso = {"string": str, "array": list, "integer": int}.get(tipo)
        if atteso and not isinstance(risposta[campo], atteso):
            raise ValueError(f"il campo «{campo}» non è del tipo giusto")
    return risposta


def _claude(sistema, prompt, schema):
    """Chiama Claude; se non risponde o risponde male riprova, poi si arrende con un errore."""
    errore = None
    for _ in range(config.TENTATIVI_CLAUDE):
        try:
            return _controlla(_chiama_claude(sistema, prompt, schema), schema)
        except Exception as e:
            errore = e
    raise RuntimeError(f"Claude non ha dato una risposta valida: {errore}")


def _chiama_claude(sistema, prompt, schema):
    # Senza ANTHROPIC_API_KEY Claude Code usa il login dell'abbonamento.
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    # Niente strumenti, plugin, MCP e istruzioni di Claude Code: solo le nostre.
    # Così una chiamata usa qualche migliaio di token invece di oltre 200.000.
    cmd = [shutil.which("claude") or os.path.expanduser("~/.local/bin/claude"),
           "-p", "--model", config.MODELLO_CLAUDE,
           "--output-format", "json", "--json-schema", json.dumps(schema),
           "--system-prompt", sistema,
           "--tools", "", "--strict-mcp-config", "--setting-sources", "",
           "--disable-slash-commands", "--no-session-persistence"]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                       timeout=config.TIMEOUT_CLAUDE, env=env, cwd=config.STATO)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p non è andato: {r.stderr.strip() or r.stdout.strip()[:500]}")
    risposta = json.loads(r.stdout)
    if risposta.get("is_error"):
        raise RuntimeError(f"claude -p ha dato errore: {risposta.get('result')}")
    return risposta.get("structured_output") or json.loads(risposta["result"])


COLONNE = ("simbolo;nome;ftsemib;prezzo;var1g%;var5g%;var20g%;var120g%;min52s;max52s;"
           "prev5g_mediana%;prev5g_basso10%;prev5g_alto90%;scambi_medi_giorno_k€;"
           "pe;pe_atteso;dividendo%;p/bv;roe%;crescita_ricavi%;margine%;debito/patrimonio%;"
           "obiettivo_analisti;obiettivo_min;obiettivo_max;n_analisti;giudizio")
_CAMPI_FOND = ["p/e_ultimi_12_mesi", "p/e_atteso", "dividendo_%", "prezzo/valore_contabile", "roe_%",
               "crescita_ricavi_%", "margine_netto_%", "debito/patrimonio_%", "prezzo_obiettivo_medio_analisti",
               "prezzo_obiettivo_minimo", "prezzo_obiettivo_massimo", "numero_analisti", "giudizio_analisti"]


def _riga_titolo(s, nome, d, prev, fond):
    """Una riga di tabella per titolo: con quasi 400 titoli un JSON per ciascuno sarebbe troppo lungo."""
    c = d["chiusure"]
    var = lambda n: round((d["ultimo"] / c[-n - 1] - 1) * 100, 1) if len(c) > n else ""
    p = (prev or {}).get(s, {})
    f = (fond or {}).get(s, {})
    valori = [s, nome, "sì" if s in config.FTSE_MIB else "", d["ultimo"], var(1), var(5), var(20), var(120),
              round(min(c[-250:]), 3), round(max(c[-250:]), 3),
              p.get("mediana_%", [""])[-1], p.get("basso10_%", [""])[-1], p.get("alto90_%", [""])[-1],
              round(d.get("scambi_medi", 0) / 1000)] + [f.get(k, "") for k in _CAMPI_FOND]
    return ";".join(str(v) for v in valori)


def _situazione(conto, prezzi):
    import conto as c
    tot = c.patrimonio(conto, prezzi)
    return {
        "patrimonio": round(tot, 2),
        "contanti": round(conto["contanti"], 2),
        "rendimento_dall_inizio_%": round((tot / config.CAPITALE_INIZIALE - 1) * 100, 2),
        "posizioni": {
            s: {**p, "prezzo_attuale": prezzi[s]["ultimo"],
                "risultato_%": round((prezzi[s]["ultimo"] / p["prezzo_medio"] - 1) * 100, 2)}
            for s, p in conto["posizioni"].items() if s in prezzi
        },
        "ultimi_ordini": conto["ordini"][-15:],
    }


def decidi(momento, conto, prezzi, prev, fond, notizie, nomi):
    dati = {
        "ora_attuale": datetime.now(ZoneInfo("Europe/Rome")).strftime("%A %d/%m/%Y %H:%M"),
        "momento": MOMENTI[momento],
        "testimone_della_sveglia_precedente": conto.get("testimone", "Prima sveglia: nessun testimone."),
        "ordini_respinti_l_ultima_volta": conto.get("ultimi_scartati", []),
        **_situazione(conto, prezzi),
        "notizie": notizie,
    }
    tabella = "\n".join([COLONNE] + [_riga_titolo(s, nomi.get(s, s), d, prev, fond) for s, d in prezzi.items()])
    prompt = ("Situazione attuale:\n" + json.dumps(dati, ensure_ascii=False)
              + f"\n\nTutte le {len(prezzi)} azioni di Piazza Affari (previsioni = a 5 giorni; campi vuoti = dato non disponibile):\n"
              + tabella)
    return _claude(_istruzioni(), prompt, SCHEMA_SVEGLIA)


def pagella(conto, prezzi, settimana):
    dati = {
        "compito": "È venerdì sera. Dai il voto alla settimana confrontandola con il FTSE MIB, "
                   "individua l'errore principale e, se serve, una regola nuova per le prossime settimane.",
        "testimone_della_sveglia_precedente": conto.get("testimone", ""),
        **_situazione(conto, prezzi),
        "settimana": settimana,
    }
    return _claude(_istruzioni(), json.dumps(dati, ensure_ascii=False), SCHEMA_PAGELLA)
