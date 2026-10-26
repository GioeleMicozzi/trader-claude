#!/bin/zsh
# Doppio clic: installa Timestral, azzera il conto di prova e avvia il trader in automatico.
set -e
cd "$(dirname "$0")"
export SSL_CERT_FILE="$(.venv/bin/python -c 'import certifi; print(certifi.where())')"

echo "1/4  Installo Timestral (da github.com/mistralai/timestral)…"
uv pip install -q --python .venv/bin/python "git+https://github.com/mistralai/timestral.git"

echo "2/4  Scarico il modello e provo una previsione…"
.venv/bin/python -c "
import numpy as np, previsioni
f = previsioni._carica().forecast(np.random.default_rng(0).standard_normal(500).cumsum(), prediction_length=5)
print('   previsione di prova:', np.round(np.ravel(f.median), 2))
"

echo "3/4  Azzero il conto (si riparte da 100.000 € finti)…"
rm -rf stato && mkdir stato

echo "4/4  Avvio il giro automatico negli orari di borsa…"
PLIST=~/Library/LaunchAgents/it.gioele.trader-claude.plist
sed "s#__CARTELLA__#$PWD#g" trader-claude.plist > "$PLIST"
launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
# Primo giro subito, così si vede che parte da solo (se la borsa è chiusa non fa niente).
launchctl kickstart gui/$(id -u)/it.gioele.trader-claude

echo
echo "Fatto. Il trader gira da solo dal lunedì al venerdì, alle 8:30, 9:35, 13:00, 17:15 e il venerdì alle 18:00 la pagella."
echo "Risultati: dashboard.html in questa cartella."
