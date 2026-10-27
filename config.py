"""Impostazioni del trader."""
import os
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
# TRADER_STATO serve solo alle prove (prove_rompilo.py): così non toccano il conto vero.
STATO = Path(os.environ.get("TRADER_STATO") or CARTELLA / "stato")
CONTO = STATO / "conto.json"
REGISTRO = STATO / "registro.jsonl"      # una riga per ogni giro: dati, previsioni, decisione
DASHBOARD = STATO / "dashboard.html" if os.environ.get("TRADER_STATO") else CARTELLA / "dashboard.html"
# La stessa dashboard pubblicata da GitHub Pages: il link va in fondo ai messaggi Telegram.
DASHBOARD_WEB = "https://gioelemicozzi.github.io/trader-claude/?apri"  # ?apri: indirizzo nuovo, Telegram non usa la copia vecchia
STORICO = STATO / "storico"             # una copia del conto dopo ogni sveglia
IN_CORSO = STATO / "sveglia_in_corso.json"  # c'è solo mentre una sveglia lavora
LUCCHETTO = STATO / "sveglia.lock"
STRATEGIA = CARTELLA / "strategia.md"           # il «contratto» con Claude, modificabile
REGOLE_IMPARATE = STATO / "regole_imparate.md"  # le regole che Claude si dà nelle pagelle
ELENCO_TITOLI = CARTELLA / "titoli.json"        # tutte le azioni di Piazza Affari (aggiorna_titoli.py)

# Modalità: "paper" = soldi finti. Non esiste ancora un collegamento a un broker vero.
MODALITA = "paper"
CAPITALE_INIZIALE = 100_000.0

# I 40 titoli del FTSE MIB dopo la revisione del 21/09/2026 (simboli Yahoo).
# L'indice cambia ogni trimestre (marzo, giugno, settembre, dicembre): va aggiornata.
FTSE_MIB = {
    "AVIO.MI": "Avio", "BZU.MI": "Buzzi", "FCT.MI": "Fincantieri", "SPM.MI": "Saipem",
    "STMMI.MI": "STMicroelectronics", "TPRO.MI": "Technoprobe",
    "ENI.MI": "Eni", "ENEL.MI": "Enel", "ISP.MI": "Intesa Sanpaolo",
    "UCG.MI": "UniCredit", "STLAM.MI": "Stellantis", "RACE.MI": "Ferrari",
    "G.MI": "Generali", "TIT.MI": "Telecom Italia", "PST.MI": "Poste Italiane",
    "MB.MI": "Mediobanca", "BAMI.MI": "Banco BPM", "BPE.MI": "BPER Banca",
    "LDO.MI": "Leonardo", "PRY.MI": "Prysmian", "MONC.MI": "Moncler",
    "TEN.MI": "Tenaris", "SRG.MI": "Snam", "TRN.MI": "Terna",
    "A2A.MI": "A2A", "HER.MI": "Hera", "CPR.MI": "Campari",
    "AMP.MI": "Amplifon", "REC.MI": "Recordati",
    "FBK.MI": "FinecoBank", "BMED.MI": "Banca Mediolanum",
    "INW.MI": "Inwit", "NEXI.MI": "Nexi", "IVG.MI": "Iveco",
    "AZM.MI": "Azimut", "BMPS.MI": "Monte dei Paschi", "BC.MI": "Brunello Cucinelli",
    "IG.MI": "Italgas", "UNI.MI": "Unipol", "LTMC.MI": "Lottomatica",
}

# Tutte le azioni di Piazza Affari, dall'elenco scaricato da aggiorna_titoli.py.
TITOLI = dict(FTSE_MIB)
if ELENCO_TITOLI.exists():
    import json as _json
    for _s, _d in _json.loads(ELENCO_TITOLI.read_text()).items():
        TITOLI.setdefault(_s, _d["nome"])

# Costi, simili a quelli di Interactive Brokers sulla Borsa Italiana.
COMMISSIONE_PERC = 0.0005      # 0,05% dell'ordine
COMMISSIONE_MIN = 1.25
COMMISSIONE_MAX = 29.0
TOBIN_TAX = 0.001              # 0,1% sugli acquisti di azioni italiane

# Limiti che Claude non può superare: il codice li applica comunque.
MAX_PESO_TITOLO = 0.10         # nessun titolo oltre il 10% del patrimonio
MIN_LIQUIDITA = 0.10           # resta sempre almeno il 10% in contanti
MAX_ORDINI_PER_GIRO = 6
MAX_QUOTA_SCAMBI = 0.10        # un acquisto non supera il 10% degli euro scambiati in media al giorno
STOP_LOSS = 0.10               # vende da solo un titolo che perde il 10% dal prezzo medio

# Le sveglie (devono coincidere con .github/workflows/sveglia.yml). Un po' in anticipo,
# perché GitHub a volte parte in ritardo. La pagella è il venerdì.
SVEGLIE = [("piano", 8, 12), ("apertura", 9, 17), ("meta", 12, 43), ("chiusura", 17, 7)]
PAGELLA = ("pagella", 18, 3)
TENTATIVI_CLAUDE = 2           # se Claude non risponde o risponde male, si riprova una volta

# Previsione
MODELLO_TIMESTRAL = "mistralai/Timestral-209M"
GIORNI_STORICO = 730           # due anni di chiusure giornaliere
GIORNI_PREVISIONE = 5          # una settimana di borsa

# Claude (abbonamento, attraverso Claude Code: nessuna API a pagamento)
MODELLO_CLAUDE = "opus"
TIMEOUT_CLAUDE = 600
