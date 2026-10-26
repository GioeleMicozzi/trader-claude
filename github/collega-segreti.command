#!/bin/zsh
# Doppio clic: mette le chiavi del trader nei «Secrets» del repository GitHub.
# Le chiavi vanno dritte a GitHub (cifrate): non vengono stampate né salvate in altri file.
set -e
cd "$(dirname "$0")/.."

echo "1/2  Telegram: prendo token e chat del bot da stato/telegram.json…"
.venv/bin/python -c "import json; print(json.load(open('stato/telegram.json'))['token'], end='')" | gh secret set TELEGRAM_TOKEN
.venv/bin/python -c "import json; print(json.load(open('stato/telegram.json'))['chat_id'], end='')" | gh secret set TELEGRAM_CHAT_ID

echo
echo "2/2  Claude: adesso parte «claude setup-token»."
echo "     Si apre il browser: accedi e autorizza. Poi qui sotto compare un token che inizia con sk-ant-oat:"
echo "     selezionalo tutto e copialo (⌘C). Se va a capo su più righe, copia tutte le righe."
echo
claude setup-token
echo
TOKEN=$(osascript -e 'text returned of (display dialog "Incolla qui il token di Claude (⌘V). Resta nascosto e va dritto a GitHub:" default answer "" with hidden answer)')
TOKEN=${TOKEN//[[:space:]]/}
if [[ "$TOKEN" != sk-ant-* ]]; then
    echo "Non sembra un token di Claude (deve iniziare con sk-ant-). Rilancia questo file."
    read "?Premi Invio per chiudere."; exit 1
fi
printf '%s' "$TOKEN" | gh secret set CLAUDE_CODE_OAUTH_TOKEN
unset TOKEN

echo
echo "Fatto. Segreti salvati su GitHub:"
gh secret list
echo; read "?Premi Invio per chiudere."
