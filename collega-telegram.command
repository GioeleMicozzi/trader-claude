#!/bin/zsh
# Doppio clic dopo aver creato il bot con BotFather.
cd "$(dirname "$0")"
.venv/bin/python collega_telegram.py
echo; read "?Premi Invio per chiudere."
