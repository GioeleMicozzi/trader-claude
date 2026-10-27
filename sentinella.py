"""La sentinella: ogni mezz'ora, a borsa aperta, guarda i prezzi da Yahoo senza chiamare Claude.
Applica lo stop loss e gli ordini condizionati lasciati da Claude all'ultima sveglia
(«compra FBK se scende a 21»). Se non scatta niente non scrive niente e non manda messaggi.
Uso: python sentinella.py"""
import config
import conto as c
import dashboard
import dati
import giro
import telegram


def _valido(o):
    try:
        return (o.get("azione") in ("compra", "vendi") and o.get("se") in ("sotto", "sopra")
                and float(o["soglia"]) > 0 and int(o["quantita"]) > 0)
    except (KeyError, TypeError, ValueError):
        return False


def scattato(o, prezzo):
    return prezzo <= float(o["soglia"]) if o["se"] == "sotto" else prezzo >= float(o["soglia"])


def main():
    if (config.CARTELLA / "SUL_SERVER").exists():
        print("Il trader ora gira su GitHub: qui sul Mac non parte. Il conto aggiornato si scarica con git pull.")
        return
    ora = giro.adesso()
    if not giro.borsa_aperta(ora):
        print(f"{ora:%d/%m %H:%M} [sentinella] borsa chiusa, niente da fare")
        return
    lucchetto = giro._prendi_lucchetto()
    if lucchetto is None:
        print(f"{ora:%d/%m %H:%M} [sentinella] una sveglia sta lavorando: salto questo giro")
        return
    try:
        rosse = giro.prove_dopo_modifiche()
        if rosse:
            print("Prove Rompilo fallite, la sentinella non opera:\n" + rosse)
            return
        guarda(ora)
    finally:
        lucchetto.close()


def guarda(ora):
    conto = c.carica()
    oggi = ora.date().isoformat()
    attivi = [o for o in conto.get("condizionati", []) if o.get("data") == oggi and "esito" not in o]
    simboli = set(conto["posizioni"]) | {o.get("simbolo") for o in attivi if _valido(o)}
    if not simboli:
        print(f"{ora:%d/%m %H:%M} [sentinella] niente da sorvegliare")
        return
    prezzi, saltati = dati.tutti(sorted(simboli))
    sveglia_id = f"{ora:%Y-%m-%d-%H%M}-sentinella"

    eseguiti = c.stop_loss(conto, prezzi, sveglia_id)
    scartati = []
    for o in attivi:
        prezzo = prezzi.get(o.get("simbolo"), {}).get("ultimo")
        if not _valido(o):
            o["esito"] = "ordine condizionato non valido: scartato"
            scartati.append({**o, "perche": o["esito"]})
            continue
        if prezzo is None or not scattato(o, prezzo):
            continue
        fatti, respinti = c.esegui(conto, [o], prezzi, sveglia_id)
        o["esito"] = f"{ora:%H:%M} a {prezzo}: " + ("eseguito" if fatti else respinti[0]["perche"])
        eseguiti += fatti
        scartati += respinti

    print(f"{ora:%d/%m %H:%M} [sentinella] {len(simboli)} titoli guardati, "
          f"{len(eseguiti)} ordini eseguiti, {len(scartati)} respinti" + (f", senza prezzo: {saltati}" if saltati else ""))
    if not eseguiti and not scartati:
        return
    conto.setdefault("prezzi", {}).update({s: d["ultimo"] for s, d in prezzi.items()})
    c.salva(conto, copia=sveglia_id)
    giro.registra({"quando": ora.isoformat(timespec="minutes"), "momento": "sentinella", "id": sveglia_id,
                   "eseguiti": eseguiti, "scartati": scartati, "saltati": saltati})
    dashboard.genera(c.carica(), config.TITOLI)
    righe = [f"{telegram.TITOLI_MOMENTI['sentinella']} · {ora:%H:%M}"]
    for o in eseguiti:
        segno = "🟢 Compra" if o["azione"] == "compra" else "🔴 Vende"
        righe.append(f"{segno} {o['quantita']} {config.TITOLI.get(o['simbolo'], o['simbolo'])} a {o['prezzo']} — {o['motivo']}")
    for o in scartati:
        righe.append(f"⛔ Respinto: {o.get('azione')} {o.get('simbolo')} — {o['perche']}")
    righe.append(f"\nPatrimonio {telegram._euro(c.patrimonio(conto, prezzi))}")
    telegram.invia("\n".join(righe))


if __name__ == "__main__":
    main()
