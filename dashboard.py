"""Scrive dashboard.html: una pagina che si apre col doppio clic, senza server."""
import html
import json

import config
from telegram import TITOLI_MOMENTI


def _euro(x):
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _perc(x):
    return f"{x:+.2f}%".replace(".", ",")


def _grafico(andamento):
    punti = [a for a in andamento if a.get("patrimonio")]
    if len(punti) < 2:
        return '<p class="vuoto">Il grafico compare dal secondo giro.</p>'
    W, H, M = 800, 260, 30
    base_p = config.CAPITALE_INIZIALE
    base_i = next((a["ftsemib"] for a in punti if a.get("ftsemib")), None)
    serie_p = [(a["patrimonio"] / base_p - 1) * 100 for a in punti]
    serie_i = [(a["ftsemib"] / base_i - 1) * 100 if base_i and a.get("ftsemib") else None for a in punti]
    tutti = serie_p + [v for v in serie_i if v is not None] + [0]
    lo, hi = min(tutti), max(tutti)
    if hi - lo < 1:
        lo, hi = lo - 0.5, hi + 0.5
    x = lambda i: M + i * (W - 2 * M) / (len(punti) - 1)
    y = lambda v: H - M - (v - lo) * (H - 2 * M) / (hi - lo)
    linea = lambda s: " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(s) if v is not None)
    return f"""<svg viewBox="0 0 {W} {H}" role="img" aria-label="Andamento del patrimonio">
<line x1="{M}" x2="{W-M}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="zero"/>
<text x="{M}" y="{y(0)-4:.1f}" class="et">0%</text>
<text x="{M}" y="{M-10}" class="et">{_perc(hi)}</text><text x="{M}" y="{H-8}" class="et">{_perc(lo)}</text>
<polyline points="{linea(serie_i)}" class="indice"/>
<polyline points="{linea(serie_p)}" class="portafoglio"/>
<text x="{W-M}" y="{H-8}" class="et" text-anchor="end">{punti[0]['quando'][:10]} → {punti[-1]['quando'][:16].replace('T', ' ')}</text>
</svg>
<p class="legenda"><span class="l-p"></span>Claude <span class="l-i"></span>FTSE MIB</p>"""


def _pagelle(pagelle):
    if not pagelle:
        return ""
    voci = "".join(
        f"<p><b>{p['quando'][:10]} · voto {p['voto']}/10</b><br>{html.escape(p['giudizio'])}<br>"
        f"<span class=\"giu\">Errore:</span> {html.escape(p['errore_della_settimana'])}"
        + (f"<br><span class=\"su\">Nuova regola:</span> {html.escape(p['nuova_regola'])}" if p['nuova_regola'].strip() else "")
        + "</p>"
        for p in reversed(pagelle))
    return f'<h2>Pagelle del venerdì</h2><div class="riquadro">{voci}</div>'


def _spiegazione():
    orari = ", ".join(f"{h}:{m:02d} {TITOLI_MOMENTI[n].split(' ', 1)[1].lower()}" for n, h, m in config.SVEGLIE)
    commissione = f"{config.COMMISSIONE_PERC * 100:.2f}%".replace(".", ",")
    return f"""<details class="riquadro spiega" open><summary>Che cos'è e come funziona</summary>
<p><b>È un esperimento con soldi finti.</b> Claude, l'intelligenza artificiale di Anthropic, gestisce un conto
virtuale di {_euro(config.CAPITALE_INIZIALE)} comprando e vendendo azioni di Piazza Affari. Nessun euro vero
entra o esce: prezzi, commissioni e tasse però sono quelli reali, per capire come andrebbe davvero.</p>
<p><b>L'obiettivo</b> è fare meglio dell'indice FTSE MIB nel giro di mesi, non di giorni: compra per tenere,
non fa day trading. Nel grafico la linea arancione è il conto, quella tratteggiata l'indice.</p>
<p><b>Le sveglie.</b> Ogni giorno di borsa Claude viene svegliato più volte ({orari}; la borsa chiude
alle 17:30; il venerdì sera c'è anche la pagella della settimana). La sveglia delle 8 prepara il piano a
borsa chiusa e non fa ordini. Poi decide se comprare, vendere o aspettare, e scrive perché: sono i
ragionamenti del diario qui sotto.</p>
<p><b>Cosa guarda.</b> A ogni sveglia Claude riceve:</p>
<ul>
<li>i prezzi di tutte le azioni di Piazza Affari, da Yahoo, con circa 15 minuti di ritardo;</li>
<li>le notizie del giorno sulla borsa, sulla BCE e sui titoli che possiede;</li>
<li>le notizie degli ultimi 10 giorni sui conti di tutte le società: trimestrali, semestrali,
risultati annuali e previsioni dei manager;</li>
<li>per ogni società i numeri di bilancio: ricavi e utile degli ultimi anni, rapporto fra prezzo e utili,
dividendo, debito, e la data dei prossimi conti;</li>
<li>il prezzo obiettivo degli analisti, con quanti sono;</li>
<li>il settore di ogni società, come vanno i settori negli ultimi 5, 20 e 120 giorni e quanto pesa
ciascun settore nel suo portafoglio;</li>
<li>le previsioni statistiche di Timestral sui prossimi 5 giorni.</li>
</ul>
<p>Prima di scegliere i titoli deve dire su quali settori punta e quali evita, e perché, senza
concentrare il conto su un solo settore. Prima di comprare deve scrivere quanto pensa che valga il titolo, partendo da questi numeri, e il prezzo
a cui ammetterebbe di avere torto. Se i conti escono fra pochi giorni, ne deve tenere conto.</p>
<p><b>Il bilancio.</b> Se la sveglia di chiusura salta, si può lanciare a mano un bilancio a borsa chiusa:
Claude rilegge la giornata con i prezzi di chiusura e ripassa ogni posizione, dicendo se conferma la scelta
o cosa farebbe il giorno dopo. Non può dare ordini: è solo un parere.</p>
<p><b>Le regole</b> non le decide Claude: il programma le fa rispettare e respinge gli ordini fuori regola.
Nessun titolo oltre il 10% del conto, almeno il 10% sempre in contanti, al massimo 6 ordini per sveglia.
Se un titolo perde il {config.STOP_LOSS:.0%} dal prezzo pagato, il programma lo vende da solo (stop).
Ogni ordine paga la commissione ({commissione}, minimo {_euro(config.COMMISSIONE_MIN)})
e la Tobin tax sugli acquisti.</p>
<p><b>La sentinella.</b> Fra una sveglia e l'altra un programma semplice, senza Claude, guarda i prezzi
ogni 15 minuti. Applica gli stop e gli «ordini condizionati» che Claude ha lasciato, tipo «compra FBK se
scende a 21».</p>
<p><b>La memoria.</b> Claude non ricorda niente fra una sveglia e l'altra. Per questo alla fine di ogni
sveglia scrive un «testimone»: cosa ha fatto, cosa resta da fare, cosa controllare. La sveglia dopo
riparte da lì. Nel diario lo trovi aprendo «Appunti per la sveglia dopo».</p>
</details>"""


def _registro():
    try:
        return [json.loads(r) for r in config.REGISTRO.read_text().splitlines() if r.strip()]
    except FileNotFoundError:
        return []


def _nome(s, nomi):
    return html.escape(nomi.get(s, str(s)))


def _ordine(o, nomi):
    segno = '<span class="su">Compra</span>' if o.get("azione") == "compra" else '<span class="giu">Vende</span>'
    return (f"<li>{segno} {o.get('quantita')} {_nome(o.get('simbolo'), nomi)}"
            + (f" a {_euro(o['prezzo'])}" if "prezzo" in o else "")
            + (f" — {html.escape(o['motivo'])}" if o.get("motivo") else "") + "</li>")


def _voce_diario(v, nomi):
    parti = [f"<h3>{v['quando'][11:16]} · {TITOLI_MOMENTI.get(v.get('momento'), 'Sveglia')}</h3>"]
    d = v.get("decisione") or {}
    if v.get("errore"):
        parti.append('<p class="vuoto">Questa sveglia si è interrotta per un errore del programma: nessuna decisione.</p>')
    elif v.get("cervello_assente"):
        parti.append('<p class="vuoto">Claude non ha risposto: il programma ha applicato solo gli stop, senza ordini nuovi.</p>')
    if d.get("analisi"):
        parti.append(f"<p>{html.escape(d['analisi'])}</p>")
    if v.get("pagella"):
        p = v["pagella"]
        parti.append(f"<p><b>Voto {p.get('voto')}/10.</b> {html.escape(p.get('giudizio', ''))}</p>")
    if v.get("eseguiti"):
        parti.append('<p class="et-d">Ordini eseguiti</p><ul>' + "".join(_ordine(o, nomi) for o in v["eseguiti"]) + "</ul>")
    if v.get("scartati"):
        parti.append('<p class="et-d">Ordini respinti dal programma</p><ul>' + "".join(
            f"<li>{html.escape(str(o.get('azione')))} {_nome(o.get('simbolo'), nomi)} — {html.escape(o.get('perche', ''))}</li>"
            for o in v["scartati"]) + "</ul>")
    if d.get("ordini_condizionati"):
        parti.append('<p class="et-d">Lasciati alla sentinella</p><ul>' + "".join(
            f"<li>{'Compra' if o['azione'] == 'compra' else 'Vende'} {o['quantita']} {_nome(o['simbolo'], nomi)} "
            f"se {'scende a' if o['se'] == 'sotto' else 'sale a'} {str(o['soglia']).replace('.', ',')}"
            + (f" — {html.escape(o['motivo'])}" if o.get("motivo") else "") + "</li>"
            for o in d["ordini_condizionati"]) + "</ul>")
    elif d and not v.get("eseguiti"):
        parti.append('<p class="vuoto">Nessun ordine.</p>')
    testimone = d.get("testimone") or (v.get("pagella") or {}).get("testimone")
    if testimone:
        parti.append(f'<details><summary>Appunti per la sveglia dopo</summary><p class="testimone">{html.escape(testimone)}</p></details>')
    return '<div class="voce-d">' + "".join(parti) + "</div>"


def _diario(nomi):
    giorni = {}
    for v in _registro():
        giorni.setdefault(v["quando"][:10], []).append(v)
    if not giorni:
        return ""
    blocchi = "".join(
        f'<details class="riquadro giorno"{" open" if i == 0 else ""}><summary>{g[8:10]}/{g[5:7]}/{g[:4]} · '
        f'{len(vv)} {"voce" if len(vv) == 1 else "voci"}</summary>' + "".join(_voce_diario(v, nomi) for v in reversed(vv)) + "</details>"
        for i, (g, vv) in enumerate(sorted(giorni.items(), reverse=True)))
    return "<h2>Diario dei ragionamenti</h2>" + blocchi


def genera(conto, nomi):
    prezzi = conto.get("prezzi", {})
    pos = conto["posizioni"]
    valore_titoli = sum(p["quantita"] * prezzi.get(s, p["prezzo_medio"]) for s, p in pos.items())
    tot = conto["contanti"] + valore_titoli
    rend = (tot / config.CAPITALE_INIZIALE - 1) * 100
    vendite = [o for o in conto["ordini"] if "utile" in o]
    riuscite = sum(1 for o in vendite if o["utile"] > 0)
    costi = sum(o["costi"] for o in conto["ordini"])
    analisi = conto.get("ultima_analisi", {})

    righe_pos = "".join(
        f"<tr><td>{html.escape(nomi.get(s, s))}<small>{s}</small></td><td>{p['quantita']}</td>"
        f"<td>{_euro(p['prezzo_medio'])}</td><td>{_euro(prezzi.get(s, p['prezzo_medio']))}</td>"
        f"<td>{_euro(p['quantita'] * prezzi.get(s, p['prezzo_medio']))}</td>"
        f"<td class=\"{'su' if prezzi.get(s, 0) >= p['prezzo_medio'] else 'giu'}\">"
        f"{_perc((prezzi.get(s, p['prezzo_medio']) / p['prezzo_medio'] - 1) * 100)}</td></tr>"
        for s, p in sorted(pos.items(), key=lambda kv: -kv[1]["quantita"] * prezzi.get(kv[0], 0)))
    righe_ord = "".join(
        f"<tr><td>{o['quando'].replace('T', ' ')}</td><td class=\"{'su' if o['azione'] == 'compra' else 'giu'}\">{o['azione']}</td>"
        f"<td>{html.escape(nomi.get(o['simbolo'], o['simbolo']))}</td><td>{o['quantita']}</td><td>{_euro(o['prezzo'])}</td>"
        f"<td>{_euro(o['utile']) if 'utile' in o else ''}</td><td class=\"motivo\">{html.escape(o['motivo'])}</td></tr>"
        for o in reversed(conto["ordini"][-50:]))

    pagina = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="300">
<title>Trader Claude</title><style>
:root{{--bg:#f6f6f3;--carta:#fff;--testo:#1d1d1b;--tenue:#6b6b66;--bordo:#e3e3de;--su:#1a7f4b;--giu:#c0392b;--acc:#d97757;--ind:#8a8a84}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--carta:#1f1f1d;--testo:#ecece8;--tenue:#9a9a94;--bordo:#33332f;--su:#4cc38a;--giu:#ff6b5b;--ind:#77776f}}}}
body{{margin:0;background:var(--bg);color:var(--testo);font:15px/1.45 -apple-system,system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:15px;margin:28px 0 10px;color:var(--tenue);font-weight:600}}
.sotto{{color:var(--tenue);margin:0 0 20px}} .modo{{background:var(--acc);color:#fff;border-radius:4px;padding:1px 7px;font-size:12px;font-weight:600}}
.tessere{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}}
.tessera{{background:var(--carta);border:1px solid var(--bordo);border-radius:10px;padding:12px 14px}}
.tessera b{{display:block;font-size:22px;font-variant-numeric:tabular-nums}} .tessera span{{color:var(--tenue);font-size:13px}}
.riquadro{{background:var(--carta);border:1px solid var(--bordo);border-radius:10px;padding:14px;overflow-x:auto}}
svg{{width:100%;height:auto}} .zero{{stroke:var(--bordo)}} .et{{fill:var(--tenue);font-size:11px}}
.portafoglio{{fill:none;stroke:var(--acc);stroke-width:2.5}} .indice{{fill:none;stroke:var(--ind);stroke-width:1.5;stroke-dasharray:4 3}}
.legenda{{color:var(--tenue);font-size:13px;margin:4px 0 0}} .l-p,.l-i{{display:inline-block;width:18px;height:3px;margin:0 5px 3px 12px;background:var(--acc)}} .l-i{{background:var(--ind)}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}} th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--bordo);vertical-align:top}}
th{{color:var(--tenue);font-weight:500;font-size:13px}} td small{{display:block;color:var(--tenue);font-size:11px}}
details summary{{cursor:pointer;font-weight:600}} .spiega{{margin-bottom:20px}} .spiega p{{margin:10px 0 0}} .spiega ul{{margin:6px 0 0;padding-left:20px}}
.giorno{{margin-bottom:10px}} .voce-d{{border-top:1px solid var(--bordo);margin-top:12px;padding-top:4px}}
.voce-d h3{{font-size:15px;margin:8px 0 4px}} .voce-d p{{margin:6px 0}} .voce-d ul{{margin:4px 0 8px;padding-left:20px}}
.voce-d details{{margin:6px 0}} .voce-d summary{{font-weight:500;color:var(--tenue);font-size:14px}}
.et-d{{color:var(--tenue);font-size:13px;margin-bottom:0}} .testimone{{white-space:pre-line;color:var(--tenue)}}
.su{{color:var(--su)}} .giu{{color:var(--giu)}} .motivo{{color:var(--tenue);min-width:260px}} .vuoto{{color:var(--tenue)}}
</style></head><body><main>
<h1>Trader Claude <span class="modo">{'SOLDI FINTI' if config.MODALITA == 'paper' else 'SOLDI VERI'}</span></h1>
<p class="sotto">Azioni di Piazza Affari · decide Claude, il programma fa rispettare le regole · aggiornato {html.escape(analisi.get('quando', '—')[:16].replace('T', ' '))}</p>
{_spiegazione()}
<div class="tessere">
<div class="tessera"><span>Patrimonio</span><b>{_euro(tot)}</b></div>
<div class="tessera"><span>Dall'inizio</span><b class="{'su' if rend >= 0 else 'giu'}">{_perc(rend)}</b></div>
<div class="tessera"><span>Contanti</span><b>{_euro(conto['contanti'])}</b></div>
<div class="tessera"><span>Vendite in utile</span><b>{f'{riuscite}/{len(vendite)}' if vendite else '—'}</b></div>
<div class="tessera"><span>Costi pagati</span><b>{_euro(costi)}</b></div>
</div>
<h2>Andamento</h2><div class="riquadro">{_grafico(conto['andamento'])}</div>
<h2>Ultimo ragionamento di Claude</h2><div class="riquadro">{html.escape(analisi.get('testo', 'Nessun giro ancora.'))}
{'' if analisi.get('con_previsioni', True) else '<p class="giu">Questo giro è stato fatto senza le previsioni di Timestral.</p>'}</div>
{_pagelle(conto.get('pagelle', []))}
{_diario(nomi)}
<h2>Posizioni aperte</h2><div class="riquadro">{f'<table><tr><th>Titolo</th><th>Quantità</th><th>Prezzo medio</th><th>Prezzo</th><th>Valore</th><th>Risultato</th></tr>{righe_pos}</table>' if pos else '<p class="vuoto">Nessuna posizione.</p>'}</div>
<h2>Ordini</h2><div class="riquadro">{f'<table><tr><th>Quando</th><th></th><th>Titolo</th><th>Q.tà</th><th>Prezzo</th><th>Utile</th><th>Motivo</th></tr>{righe_ord}</table>' if conto['ordini'] else '<p class="vuoto">Nessun ordine.</p>'}</div>
</main></body></html>"""
    config.DASHBOARD.write_text(pagina)
