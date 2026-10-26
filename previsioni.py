"""Previsioni dei prezzi con Timestral, in locale sulla CPU."""
import numpy as np

import config

_modello = None


def _carica():
    global _modello
    if _modello is None:
        from timestral import TimestralForecaster
        # Solo CPU: Timestral usa float64, che la GPU del Mac (MPS) non supporta.
        _modello = TimestralForecaster.from_pretrained(config.MODELLO_TIMESTRAL, device="cpu")
    return _modello


def prevedi(prezzi):
    """Per ogni titolo: mediana e forbice 10–90% dei prossimi giorni, in % sull'ultimo prezzo."""
    modello = _carica()
    out = {}
    for simbolo, d in prezzi.items():
        serie = np.array(d["chiusure"][-config.GIORNI_STORICO:], dtype=float)
        # Il modello lavora sui logaritmi: le variazioni percentuali pesano uguale a ogni livello di prezzo.
        f = modello.forecast(np.log(serie), prediction_length=config.GIORNI_PREVISIONE)
        base = d["ultimo"]
        perc = lambda x: [round((float(np.exp(v)) / base - 1) * 100, 2) for v in np.ravel(x)]
        out[simbolo] = {
            "mediana_%": perc(f.median),
            "basso10_%": perc(f.quantile(0.1)),
            "alto90_%": perc(f.quantile(0.9)),
        }
    return out
