"""Le prove «Rompilo»: i guasti che contano, provati davvero con dati e cervello finti.
Uso: python3 prove_rompilo.py      (non usa la rete e non tocca il conto vero)"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
FINTO = CARTELLA / "prove_finto.py"

COMPRA_ISP = {"analisi": "Prova.", "testimone": "Comprato ISP.", "ordini_condizionati": [],
              "ordini": [{"azione": "compra", "simbolo": "ISP.MI", "quantita": 100, "motivo": "prova"}]}


class Rompilo(unittest.TestCase):
    def setUp(self):
        self.cartella = Path(tempfile.mkdtemp(prefix="rompilo-"))
        self.stato = self.cartella / "stato"
        self.cervello(COMPRA_ISP)

    def cervello(self, *risposte):
        f = self.cartella / "cervello.json"
        f.write_text(json.dumps(list(risposte)))
        (self.stato / "chiamate_claude.txt").unlink(missing_ok=True)

    def env(self, **extra):
        return {**os.environ, "TRADER_STATO": str(self.stato),
                "FINTO_CERVELLO": str(self.cartella / "cervello.json"),
                "FINTO_ORA": "2026-10-26T09:40", **extra}

    def lancia(self, momento="apertura", **extra):
        return subprocess.run([sys.executable, str(FINTO), momento], env=self.env(**extra),
                              capture_output=True, text=True, timeout=60)

    def avvia(self, momento="apertura", **extra):
        return subprocess.Popen([sys.executable, str(FINTO), momento], env=self.env(**extra),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def aspetta(self, nome, secondi=20):
        fine = time.time() + secondi
        while not (self.stato / nome).exists():
            self.assertLess(time.time(), fine, f"{nome} non è mai comparso")
            time.sleep(0.05)

    def conto(self):
        return json.loads((self.stato / "conto.json").read_text())

    def messaggi(self):
        f = self.stato / "messaggi.txt"
        return f.read_text() if f.exists() else ""

    def chiamate(self):
        f = self.stato / "chiamate_claude.txt"
        return len(f.read_text().splitlines()) if f.exists() else 0

    # 1. Morte a metà: kill -9 dopo il primo ordine, prima che il conto sia salvato.
    def test_morte_a_meta(self):
        p = self.avvia(FINTO_PAUSA="prima_di_salvare")
        self.aspetta("in_pausa")
        os.kill(p.pid, signal.SIGKILL)
        p.communicate()
        self.assertFalse((self.stato / "conto.json").exists(), "il conto non doveva essere stato scritto")
        r = self.lancia()
        self.assertIn("interrotta prima di salvare", self.messaggi())
        ordini = [o for o in self.conto()["ordini"] if o["simbolo"] == "ISP.MI"]
        self.assertEqual(len(ordini), 1, r.stdout + r.stderr)
        self.assertFalse((self.stato / "sveglia_in_corso.json").exists())
        # rilancio della stessa sveglia: non riparte, niente doppioni
        r = self.lancia()
        self.assertIn("già fatta", r.stdout)
        self.assertEqual(len(self.conto()["ordini"]), 1)

    # 2. Doppio lancio: due sveglie della stessa ora a mezzo secondo di distanza.
    def test_doppio_lancio(self):
        a = self.avvia(FINTO_LENTO="2")
        time.sleep(0.5)
        b = self.avvia(FINTO_LENTO="2")
        uscite = [p.communicate()[0] for p in (a, b)]
        self.assertEqual(sum("un'altra sveglia sta già lavorando" in u for u in uscite), 1, uscite)
        self.assertEqual(self.chiamate(), 1, "Claude è stato chiamato da tutte e due le sveglie")
        self.assertEqual(len(self.conto()["ordini"]), 1)

    # 2b. Doppio lancio dopo una sveglia morta: tutte e due vedono la sveglia morta, passa una sola.
    def test_doppio_lancio_dopo_sveglia_morta(self):
        self.stato.mkdir(parents=True)
        (self.stato / "sveglia_in_corso.json").write_text(
            json.dumps({"sveglia": "2026-10-26-piano", "pid": 999999, "da": "2026-10-26T08:30"}))
        a = self.avvia(FINTO_LENTO="2")
        time.sleep(0.5)
        b = self.avvia(FINTO_LENTO="2")
        for p in (a, b):
            p.communicate()
        self.assertEqual(self.chiamate(), 1, "Claude è stato chiamato da tutte e due le sveglie")
        self.assertEqual(len(self.conto()["ordini"]), 1)
        self.assertEqual(self.messaggi().count("interrotta"), 1)

    # 3. La fonte dei prezzi non risponde (da noi il «broker» è il conto, i dati arrivano da Yahoo).
    def test_prezzi_non_arrivano(self):
        r = self.lancia(FINTO_PREZZI="giu")
        self.assertIn("❌", self.messaggi())
        self.assertFalse((self.stato / "conto.json").exists())
        self.assertFalse((self.stato / "sveglia_in_corso.json").exists())
        r = self.lancia()  # il lucchetto è stato rilasciato: la sveglia dopo lavora
        self.assertEqual(len(self.conto()["ordini"]), 1, r.stdout + r.stderr)

    # 4. Il modello risponde male: JSON troncato, campo mancante, quantità negativa, azione inventata.
    def test_json_troncato_poi_giusto(self):
        self.cervello("troncato", COMPRA_ISP)
        self.lancia()
        self.assertEqual(self.chiamate(), 2)
        self.assertEqual(len(self.conto()["ordini"]), 1)

    def test_campo_mancante_sempre(self):
        self.cervello({"analisi": "senza ordini né testimone"})
        self.lancia()
        self.assertEqual(self.chiamate(), 2)
        self.assertEqual(self.conto()["ordini"], [])
        self.assertIn("Cervello non disponibile", self.messaggi())

    def test_quantita_negativa_e_azione_inventata(self):
        self.cervello({"analisi": "x", "testimone": "y", "ordini_condizionati": [], "ordini": [
            {"azione": "compra", "simbolo": "ISP.MI", "quantita": -50, "motivo": "negativa"},
            {"azione": "short", "simbolo": "ENI.MI", "quantita": 10, "motivo": "inventata"},
            {"azione": "compra", "simbolo": "ENEL.MI", "quantita": "tanti", "motivo": "non numero"},
            {"azione": "compra", "simbolo": "NONCE.MI", "quantita": 5, "motivo": "titolo inesistente"}]})
        self.lancia()
        c = self.conto()
        self.assertEqual(c["ordini"], [])
        self.assertEqual(len(c["ultimi_scartati"]), 4)
        self.assertEqual(c["contanti"], 100_000)

    # 5. Conto scritto a metà: il processo muore mentre scrive conto.json.
    def test_conto_scritto_a_meta(self):
        self.lancia()  # una sveglia buona lascia la copia in stato/storico
        p = self.avvia("meta", FINTO_ORA="2026-10-26T13:00", FINTO_PAUSA="scrittura_a_meta")
        self.aspetta("in_pausa")
        os.kill(p.pid, signal.SIGKILL)
        p.communicate()
        with self.assertRaises(ValueError):
            self.conto()
        r = self.lancia("meta", FINTO_ORA="2026-10-26T13:05")
        self.assertIn("era rovinato", self.messaggi(), r.stdout + r.stderr)
        self.assertEqual(self.conto()["ultima_sveglia"]["id"], "2026-10-26-meta")

    # 6. Orologio: la sveglia parte alle 17:15 ma Claude risponde dopo la chiusura.
    def test_orologio(self):
        r = self.lancia("chiusura", FINTO_ORA="2026-10-26T17:15", FINTO_ORA_DOPO="2026-10-26T17:31")
        c = self.conto()
        self.assertEqual(c["ordini"], [], r.stdout + r.stderr)
        self.assertIn("borsa chiusa", c["ultimi_scartati"][0]["perche"])

    # Lo stop gira anche senza cervello, e un titolo stoppato non si ricompra il giorno stesso.
    def test_stop_senza_cervello(self):
        self.lancia()
        self.cervello("giu")
        self.lancia("meta", FINTO_ORA="2026-10-26T13:00", FINTO_LISTINO='{"ISP.MI": 4.0}')
        c = self.conto()
        self.assertNotIn("ISP.MI", c["posizioni"])
        self.assertTrue(c["ordini"][-1]["motivo"].startswith("Stop automatico"))
        self.assertIn("Cervello non disponibile", self.messaggi())
        self.cervello(COMPRA_ISP)
        self.lancia("chiusura", FINTO_ORA="2026-10-26T17:15", FINTO_LISTINO='{"ISP.MI": 4.0}')
        self.assertIn("non si ricompra", self.conto()["ultimi_scartati"][0]["perche"])

    # La gabbia: un acquisto enorme viene ridotto al 10% del patrimonio e agli scambi del titolo.
    def test_gabbia(self):
        self.cervello({"analisi": "x", "testimone": "y", "ordini_condizionati": [], "ordini": [
            {"azione": "compra", "simbolo": "ENEL.MI", "quantita": 100_000, "motivo": "tutto"},
            {"azione": "compra", "simbolo": "SMALL.MI", "quantita": 100_000, "motivo": "piccola"}]})
        self.lancia()
        c = self.conto()
        self.assertLessEqual(c["posizioni"]["ENEL.MI"]["quantita"] * 9.0, 10_000)
        self.assertLessEqual(c["posizioni"]["SMALL.MI"]["quantita"] * 2.0, 2_000)

    # Sveglie perse col Mac spento: si elencano, non si recuperano.
    def test_sveglie_perse(self):
        self.lancia("chiusura", FINTO_ORA="2026-10-23T17:15")  # venerdì
        self.cervello({"analisi": "x", "testimone": "y", "ordini_condizionati": [], "ordini": []})
        self.lancia("meta", FINTO_ORA="2026-10-26T13:00")      # lunedì
        m = self.messaggi()
        self.assertIn("Sveglie saltate", m)
        for persa in ("23/10 18:03 pagella", "26/10 08:12 piano", "26/10 09:17 apertura"):
            self.assertIn(persa, m)
        self.assertNotIn("12:43 meta;", m)


    # La sentinella: esegue l'ordine condizionato quando il prezzo tocca la soglia, una volta sola.
    def test_sentinella(self):
        self.cervello({"analisi": "x", "testimone": "piano", "ordini": [], "ordini_condizionati": [
            {"azione": "compra", "simbolo": "ENEL.MI", "quantita": 100, "se": "sotto", "soglia": 8.5, "motivo": "ritracciamento"}]})
        self.lancia("piano", FINTO_ORA="2026-10-26T08:15")
        prima = (self.stato / "conto.json").read_text()
        r = self.lancia("sentinella", FINTO_ORA="2026-10-26T10:05")  # ENEL a 9: soglia non toccata
        self.assertIn("0 ordini eseguiti", r.stdout, r.stdout + r.stderr)
        self.assertEqual((self.stato / "conto.json").read_text(), prima, "senza scatti il conto non si riscrive")
        self.lancia("sentinella", FINTO_ORA="2026-10-26T10:35", FINTO_LISTINO='{"ENEL.MI": 8.4}')
        c = self.conto()
        self.assertEqual(c["posizioni"]["ENEL.MI"]["quantita"], 100)
        self.assertIn("eseguito", c["condizionati"][0]["esito"])
        self.assertIn("Sentinella", self.messaggi())
        self.lancia("sentinella", FINTO_ORA="2026-10-26T11:05", FINTO_LISTINO='{"ENEL.MI": 8.3}')
        self.assertEqual(self.conto()["posizioni"]["ENEL.MI"]["quantita"], 100, "l'ordine non si ripete")
        self.assertEqual(self.chiamate(), 1, "la sentinella non chiama Claude")
        # il giorno dopo l'ordine di ieri non vale più, e a borsa chiusa non lavora
        r = self.lancia("sentinella", FINTO_ORA="2026-10-26T18:05")
        self.assertIn("borsa chiusa", r.stdout)

    # Lo stop scatta anche fra una sveglia e l'altra, senza Claude.
    def test_sentinella_stop(self):
        self.lancia()
        self.lancia("sentinella", FINTO_ORA="2026-10-26T11:05", FINTO_LISTINO='{"ISP.MI": 4.0}')
        c = self.conto()
        self.assertNotIn("ISP.MI", c["posizioni"])
        self.assertTrue(c["ordini"][-1]["motivo"].startswith("Stop automatico"))
        self.assertEqual(self.chiamate(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
