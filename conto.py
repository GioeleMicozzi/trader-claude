"""Conto finto: contanti, posizioni, ordini. Applica costi e limiti."""
import json
from datetime import datetime

import config

COPIE_DA_TENERE = 300


def nuovo():
    return {"contanti": config.CAPITALE_INIZIALE, "posizioni": {}, "ordini": [], "andamento": []}


def carica():
    """Il conto è la verità: se il file è rovinato (sveglia morta mentre scriveva, disco pieno)
    si riparte dall'ultima copia buona in stato/storico e lo si segnala con «_recuperato_da»."""
    if not config.CONTO.exists():
        return nuovo()
    try:
        return json.loads(config.CONTO.read_text())
    except ValueError:
        pass
    for copia in sorted(config.STORICO.glob("*.json"), reverse=True) if config.STORICO.exists() else []:
        try:
            conto = json.loads(copia.read_text())
        except ValueError:
            continue
        conto["_recuperato_da"] = copia.name
        return conto
    raise RuntimeError("conto.json è rovinato e non c'è nessuna copia buona in stato/storico")


def salva(conto, copia=None):
    """Scrittura atomica: o c'è il conto nuovo o resta quello vecchio, mai uno a metà.
    Con `copia` ne tiene anche una in stato/storico (servono a carica() se il file si rovina)."""
    config.STATO.mkdir(exist_ok=True)
    testo = json.dumps(conto, indent=1, ensure_ascii=False)
    tmp = config.CONTO.with_suffix(".tmp")
    tmp.write_text(testo)
    tmp.replace(config.CONTO)
    if copia:
        config.STORICO.mkdir(exist_ok=True)
        tmp = config.STORICO / f"{copia}.tmp"
        tmp.write_text(testo)
        tmp.replace(config.STORICO / f"{copia}.json")
        for vecchia in sorted(config.STORICO.glob("*.json"))[:-COPIE_DA_TENERE]:
            vecchia.unlink()


def patrimonio(conto, prezzi):
    titoli = sum(p["quantita"] * prezzi.get(s, {}).get("ultimo", p["prezzo_medio"])
                 for s, p in conto["posizioni"].items())
    return conto["contanti"] + titoli


def _commissione(controvalore):
    return min(max(controvalore * config.COMMISSIONE_PERC, config.COMMISSIONE_MIN), config.COMMISSIONE_MAX)


def _stoppati_oggi(conto, oggi):
    return {o["simbolo"] for o in conto["ordini"]
            if o["quando"].startswith(oggi) and o.get("motivo", "").startswith("Stop automatico")}


def stop_loss(conto, prezzi, sveglia):
    """Vende i titoli scesi oltre la soglia di stop, prima ancora di chiamare Claude."""
    ordini = [{"azione": "vendi", "simbolo": s, "quantita": p["quantita"],
               "motivo": f"Stop automatico: -{config.STOP_LOSS:.0%} dal prezzo medio"}
              for s, p in conto["posizioni"].items()
              if s in prezzi and prezzi[s]["ultimo"] <= p["prezzo_medio"] * (1 - config.STOP_LOSS)]
    eseguiti = []
    for o in ordini:
        eseguiti += esegui(conto, [o], prezzi, sveglia + "-stop")[0]
    return eseguiti


def esegui(conto, ordini, prezzi, sveglia):
    """Esegue gli ordini al prezzo attuale. Riduce o scarta quelli che violano i limiti.
    Prima le vendite, così liberano contanti per gli acquisti.
    Ogni ordine ha un id fisso (sveglia + titolo + lato): se c'è già nel conto non si ripete."""
    eseguiti, scartati = [], []
    ora = datetime.now().isoformat(timespec="minutes")
    gia_fatti = {o.get("id") for o in conto["ordini"]}
    stoppati = _stoppati_oggi(conto, ora[:10])
    scartati += [{**o, "perche": f"oltre il massimo di {config.MAX_ORDINI_PER_GIRO} ordini per sveglia"}
                 for o in ordini[config.MAX_ORDINI_PER_GIRO:]]
    ordini = sorted(ordini[:config.MAX_ORDINI_PER_GIRO], key=lambda o: o.get("azione") != "vendi")
    for o in ordini:
        s, azione = o.get("simbolo"), o.get("azione")
        try:
            q = int(o.get("quantita"))
        except (TypeError, ValueError):
            q = 0
        if azione not in ("compra", "vendi"):
            scartati.append({**o, "perche": "azione non valida: solo compra o vendi"})
            continue
        if s not in prezzi or q <= 0:
            scartati.append({**o, "perche": "titolo sconosciuto o quantità non valida"})
            continue
        id_ordine = f"{sveglia}-{s}-{azione}"
        if id_ordine in gia_fatti:
            scartati.append({**o, "perche": "ordine già eseguito in questa sveglia"})
            continue
        prezzo = prezzi[s]["ultimo"]
        pos = conto["posizioni"].get(s)
        if azione == "vendi":
            if not pos:
                scartati.append({**o, "perche": "nessuna posizione da vendere"})
                continue
            q = min(q, pos["quantita"])
            lordo = q * prezzo
            costi = _commissione(lordo)
            conto["contanti"] += lordo - costi
            utile = (prezzo - pos["prezzo_medio"]) * q - costi
            pos["quantita"] -= q
            if pos["quantita"] == 0:
                del conto["posizioni"][s]
        else:
            if s in stoppati:
                scartati.append({**o, "perche": "venduto dallo stop oggi: non si ricompra il giorno stesso"})
                continue
            tot = patrimonio(conto, prezzi)
            gia = pos["quantita"] * prezzo if pos else 0
            spazio_titolo = tot * config.MAX_PESO_TITOLO - gia
            spazio_contanti = conto["contanti"] - tot * config.MIN_LIQUIDITA
            # Su un titolo poco scambiato un ordine grosso non si eseguirebbe al prezzo di listino.
            spazio_mercato = prezzi[s].get("scambi_medi", float("inf")) * config.MAX_QUOTA_SCAMBI
            q = min(q, int(min(spazio_titolo, spazio_contanti, spazio_mercato)
                           / (prezzo * (1 + config.TOBIN_TAX + config.COMMISSIONE_PERC))))
            if q <= 0:
                scartati.append({**o, "perche": "supera i limiti di peso, di contanti o di scambi del titolo"})
                continue
            lordo = q * prezzo
            costi = _commissione(lordo) + lordo * config.TOBIN_TAX
            conto["contanti"] -= lordo + costi
            if pos:
                pos["prezzo_medio"] = (pos["prezzo_medio"] * pos["quantita"] + lordo) / (pos["quantita"] + q)
                pos["quantita"] += q
            else:
                conto["posizioni"][s] = {"quantita": q, "prezzo_medio": prezzo, "dal": ora}
            utile = None
        voce = {"id": id_ordine, "quando": ora, "azione": azione, "simbolo": s, "quantita": q,
                "prezzo": prezzo, "costi": round(costi, 2), "motivo": o.get("motivo", "")}
        if utile is not None:
            voce["utile"] = round(utile, 2)
        conto["ordini"].append(voce)
        gia_fatti.add(id_ordine)
        eseguiti.append(voce)
    return eseguiti, scartati
