"""Una sveglia del trader: prezzi → notizie → previsioni → decisione di Claude → ordini → dashboard.
Uso: python giro.py piano|apertura|meta|chiusura|pagella
     python giro.py prova     (gira comunque, anche a borsa chiusa)
     python giro.py stato     (lucchetto, ultima sveglia, testimone, prossima sveglia)"""
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config
import conto as c
import dashboard
import dati
import decisore
import notizie
import telegram

ROMA = ZoneInfo("Europe/Rome")


def _pasqua(anno):
    a, b, cc = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = cc // 4, cc % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    mese = (h + l - 7 * m + 90) // 25
    return date(anno, mese, (h + l - 7 * m + 33 * mese + 19) % 32)


def giorno_di_borsa(giorno):
    p = _pasqua(giorno.year)
    festivi = {p - timedelta(days=2), p + timedelta(days=1)} | {
        date(giorno.year, m, g) for m, g in [(1, 1), (5, 1), (8, 15), (12, 24), (12, 25), (12, 26), (12, 31)]}
    return giorno.weekday() < 5 and giorno not in festivi


def borsa_aperta(ora):
    return giorno_di_borsa(ora.date()) and (9, 0) <= (ora.hour, ora.minute) <= (17, 30)


def adesso():
    return datetime.now(ROMA)


def _orari(giorno):
    """Le sveglie di un giorno, come (momento, datetime)."""
    if not giorno_di_borsa(giorno):
        return []
    sveglie = config.SVEGLIE + ([config.PAGELLA] if giorno.weekday() == 4 else [])
    return [(m, datetime(giorno.year, giorno.month, giorno.day, h, mi, tzinfo=ROMA)) for m, h, mi in sveglie]


def prossima_sveglia(ora):
    for n in range(15):
        for m, quando in _orari(ora.date() + timedelta(days=n)):
            if quando > ora:
                return f"{quando:%d/%m %H:%M} ({m})"
    return "—"


def sveglie_perse(ultima, ora, momento):
    """Le sveglie dovute fra l'ultima fatta e adesso che non sono partite (Mac spento o addormentato).
    Non si recuperano: un ordine di ore fa non ha più senso. Si segnalano soltanto."""
    if not ultima:
        return []
    da = datetime.fromisoformat(ultima)
    perse = []
    giorno = da.date()
    while giorno <= ora.date():
        for m, quando in _orari(giorno):
            if da < quando <= ora and not (giorno == ora.date() and m == momento):
                perse.append(f"{quando:%a %d/%m %H:%M} {m}")
        giorno += timedelta(days=1)
    return perse


def _prendi_lucchetto():
    """Una sola sveglia alla volta. Il lucchetto è del sistema operativo (flock): se la sveglia
    muore, anche con kill -9, si libera da solo, e fra due sveglie partite insieme passa una sola."""
    config.STATO.mkdir(exist_ok=True)
    f = open(config.LUCCHETTO, "a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def riconcilia(interrotta, conto):
    """Una sveglia è morta a metà: il conto dice cosa è successo davvero."""
    sveglia = interrotta.get("sveglia", "?")
    if conto.get("ultima_sveglia", {}).get("id") == sveglia:
        fatti = [o for o in conto["ordini"] if o.get("id", "").startswith(sveglia + "-")]
        elenco = ", ".join(f"{o['azione']} {o['quantita']} {o['simbolo']}" for o in fatti) or "nessun ordine"
        return f"La sveglia {sveglia} si è interrotta dopo aver salvato il conto: {elenco}. Il conto è in ordine."
    return (f"La sveglia {sveglia} si è interrotta prima di salvare: nessun suo ordine è stato registrato, "
            "il conto è quello di prima.")


def prove_dopo_modifiche():
    """Se il codice è cambiato dall'ultima volta, rilancia le prove «Rompilo» prima di lavorare.
    Restituisce None se va tutto bene, altrimenti le prove fallite: la sveglia allora non opera."""
    if os.environ.get("TRADER_STATO"):  # siamo dentro una prova: niente prove nelle prove
        return None
    impronta = hashlib.sha256(b"".join(f.read_bytes() for f in sorted(config.CARTELLA.glob("*.py")))).hexdigest()
    fatte = config.STATO / "prove_ok.txt"
    if fatte.exists() and fatte.read_text() == impronta:
        return None
    r = subprocess.run([sys.executable, str(config.CARTELLA / "prove_rompilo.py")],
                       capture_output=True, text=True, timeout=300, cwd=config.CARTELLA)
    if r.returncode != 0:
        fallite = [riga for riga in r.stderr.splitlines() if riga.startswith(("FAIL:", "ERROR:"))]
        return "\n".join(fallite) or r.stderr.strip()[-500:]
    fatte.write_text(impronta)
    return None


def registra(voce):
    config.STATO.mkdir(exist_ok=True)
    with open(config.REGISTRO, "a") as f:
        f.write(json.dumps(voce, ensure_ascii=False) + "\n")


def _pl_giorno(conto, tot, ora):
    prima = [a for a in conto["andamento"] if a["quando"][:10] < ora.date().isoformat()]
    return round(tot - (prima[-1]["patrimonio"] if prima else config.CAPITALE_INIZIALE), 2)


def sveglia(momento, ora, conto, voce):
    prezzi, saltati = dati.tutti(config.TITOLI)
    voce["saltati"] = saltati
    if len(prezzi) < len(config.TITOLI) / 2:
        raise RuntimeError(f"prezzi scaricati solo per {len(prezzi)} titoli su {len(config.TITOLI)}: sveglia annullata")
    try:
        indice = dati.storico("FTSEMIB.MI", "1d", "5d")[3]
    except Exception:
        indice = None

    stop = c.stop_loss(conto, prezzi, voce["id"]) if momento != "piano" else []
    news = notizie.raccogli(conto["posizioni"], config.TITOLI)
    try:
        import previsioni
        prev = previsioni.prevedi(prezzi)
    except Exception as e:
        prev = None
        voce["errore_previsioni"] = f"{type(e).__name__}: {e}"

    try:
        import fondamentali
        fond = fondamentali.tutti(prezzi)
    except Exception as e:
        fond = None
        voce["errore_fondamentali"] = f"{type(e).__name__}: {e}"

    try:
        decisione = decisore.decidi(momento, conto, prezzi, prev, fond, news, config.TITOLI)
    except Exception as e:
        # Senza cervello niente ordini nuovi, ma lo stop qui sopra è già stato applicato.
        voce["cervello_assente"] = str(e)
        decisione = {"analisi": "Cervello non disponibile: applico solo lo stop loss.", "ordini": [],
                     "testimone": conto.get("testimone", "") + f"\n[{ora:%d/%m %H:%M}: sveglia senza Claude, nessun ordine nuovo]"}
    ordini = [] if momento == "piano" else decisione["ordini"]
    scartati = []
    # Claude può metterci minuti: la borsa si ricontrolla subito prima degli ordini.
    if ordini and momento != "prova" and not borsa_aperta(adesso()):
        scartati = [{**o, "perche": f"borsa chiusa alle {adesso():%H:%M}, quando è arrivata la decisione"} for o in ordini]
        ordini = []
    eseguiti, respinti = c.esegui(conto, ordini, prezzi, voce["id"])
    eseguiti, scartati = stop + eseguiti, scartati + respinti
    tot = c.patrimonio(conto, prezzi)
    voce["pl_giorno"] = _pl_giorno(conto, tot, ora)
    conto["andamento"].append({"quando": voce["quando"], "patrimonio": round(tot, 2), "ftsemib": indice})
    conto["ultima_analisi"] = {"quando": voce["quando"], "momento": momento, "testo": decisione["analisi"],
                               "con_previsioni": prev is not None}
    conto["testimone"] = decisione["testimone"]
    conto["ultimi_scartati"] = scartati
    conto["prezzi"] = {s: d["ultimo"] for s, d in prezzi.items()}
    conto["ultima_sveglia"] = {"id": voce["id"], "quando": voce["quando"]}
    c.salva(conto, copia=voce["id"])
    voce.update(decisione=decisione, eseguiti=eseguiti, scartati=scartati,
                patrimonio=round(tot, 2), previsioni=prev, notizie=news)
    print(f"{ora:%d/%m %H:%M} [{momento}] patrimonio {tot:,.2f} € — {len(eseguiti)} ordini eseguiti, {len(scartati)} respinti")
    print("Analisi:", decisione["analisi"])
    for o in eseguiti:
        print(f"  {o['azione']} {o['quantita']} {o['simbolo']} a {o['prezzo']} — {o['motivo']}")
    print("Testimone:", decisione["testimone"])


def fai_pagella(ora, conto, voce):
    prezzi, _ = dati.tutti(config.TITOLI)
    inizio = (ora - timedelta(days=7)).isoformat(timespec="minutes")
    punti = [a for a in conto["andamento"] if a["quando"] >= inizio and a.get("ftsemib")]
    settimana = {
        "ordini": [o for o in conto["ordini"] if o["quando"] >= inizio],
        "patrimonio_inizio_fine": [punti[0]["patrimonio"], punti[-1]["patrimonio"]] if punti else None,
        "ftsemib_inizio_fine": [punti[0]["ftsemib"], punti[-1]["ftsemib"]] if punti else None,
    }
    p = decisore.pagella(conto, prezzi, settimana)
    conto.setdefault("pagelle", []).append({"quando": voce["quando"], **{k: v for k, v in p.items() if k != "testimone"}})
    conto["testimone"] = p["testimone"]
    conto["ultima_sveglia"] = {"id": voce["id"], "quando": voce["quando"]}
    c.salva(conto, copia=voce["id"])
    if p["nuova_regola"].strip():
        with open(config.REGOLE_IMPARATE, "a") as f:
            f.write(f"- ({ora:%d/%m/%Y}) {p['nuova_regola'].strip()}\n")
    voce["pagella"] = p
    print(f"Pagella {p['voto']}/10 — {p['giudizio']}\nErrore: {p['errore_della_settimana']}\nNuova regola: {p['nuova_regola']}")


def _momento_da_orario(ora):
    """launchd lancia sempre lo stesso comando: il momento si ricava dall'ora."""
    hm = (ora.hour, ora.minute)
    if hm < (9, 0):
        return "piano"
    if hm < (12, 0):
        return "apertura"
    if hm < (15, 0):
        return "meta"
    if hm <= (17, 30):
        return "chiusura"
    return "pagella" if ora.weekday() == 4 else "giro"


def stato():
    ora = adesso()
    lucchetto = _prendi_lucchetto()
    print("Lucchetto:", "libero" if lucchetto else "preso: una sveglia sta lavorando adesso")
    if lucchetto:
        lucchetto.close()
    if config.IN_CORSO.exists() and lucchetto:
        print("Sveglia interrotta da riconciliare:", config.IN_CORSO.read_text())
    conto = c.carica()
    print("Ultima sveglia:", conto.get("ultima_sveglia", {}).get("id", "nessuna"))
    print("Prossima sveglia:", prossima_sveglia(ora))
    print("Testimone:", conto.get("testimone", "—"))


def main():
    if (config.CARTELLA / "SUL_SERVER").exists():
        print("Il trader ora gira su GitHub: qui sul Mac non parte. Il conto aggiornato si scarica con git pull.")
        return
    ora = adesso()
    momento = sys.argv[1] if len(sys.argv) > 1 else _momento_da_orario(ora)
    if momento == "stato":
        return stato()
    if momento == "piano" or momento == "pagella":
        da_fare = giorno_di_borsa(ora.date())
    elif momento == "prova":
        da_fare = True
    else:
        da_fare = borsa_aperta(ora)
    if not da_fare:
        print(f"{ora:%d/%m %H:%M} [{momento}] borsa chiusa, niente da fare")
        return
    lucchetto = _prendi_lucchetto()
    if lucchetto is None:
        print(f"{ora:%d/%m %H:%M} [{momento}] un'altra sveglia sta già lavorando: questa non parte")
        return
    try:
        rosse = prove_dopo_modifiche()
        if rosse:
            print("Prove Rompilo fallite, sveglia annullata:\n" + rosse, file=sys.stderr)
            telegram.invia(f"❌ {momento}: il codice è cambiato e le prove «Rompilo» sono rosse. "
                           f"Nessun ordine finché non si sistemano.\n{rosse}")
            return
        _sveglia_col_lucchetto(ora, momento)
    except Exception as e:
        telegram.invia(f"❌ Sveglia {momento} non partita: {type(e).__name__}: {e}")
        raise
    finally:
        lucchetto.close()


def _sveglia_col_lucchetto(ora, momento):
    sveglia_id = f"{ora:%Y-%m-%d-%H%M}-prova" if momento == "prova" else f"{ora:%Y-%m-%d}-{momento}"
    conto = c.carica()
    avvisi = []
    if "_recuperato_da" in conto:
        avvisi.append(f"conto.json era rovinato: ripreso dalla copia {conto.pop('_recuperato_da')}.")
        c.salva(conto)
    if config.IN_CORSO.exists():
        try:
            interrotta = json.loads(config.IN_CORSO.read_text())
        except ValueError:
            interrotta = {}
        avvisi.append(riconcilia(interrotta, conto))
        config.IN_CORSO.unlink()
    if conto.get("ultima_sveglia", {}).get("id") == sveglia_id:
        print(f"{ora:%d/%m %H:%M} [{momento}] sveglia {sveglia_id} già fatta: non riparte")
        if avvisi:
            telegram.invia("⚠️ " + "\n".join(avvisi))
        return
    perse = sveglie_perse(conto.get("ultima_sveglia", {}).get("quando"), ora, momento)
    if perse:
        avvisi.append("Sveglie saltate (Mac spento o addormentato), non recuperate: " + "; ".join(perse) + ".")
    voce = {"quando": ora.isoformat(timespec="minutes"), "momento": momento, "id": sveglia_id}
    if avvisi:
        voce["avvisi"] = avvisi
    config.IN_CORSO.write_text(json.dumps({"sveglia": sveglia_id, "pid": os.getpid(), "da": voce["quando"]}))
    telegram.invia(telegram.partenza(voce))
    try:
        if momento == "pagella":
            fai_pagella(ora, conto, voce)
        else:
            sveglia(momento, ora, conto, voce)
    except Exception as e:
        voce["errore"] = traceback.format_exc()
        print("Errore:", e, file=sys.stderr)
    finally:
        voce["prossima_sveglia"] = prossima_sveglia(adesso())
        registra(voce)
        dashboard.genera(c.carica(), config.TITOLI)
        telegram.invia(telegram.resoconto(voce))
        config.IN_CORSO.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
