#!/bin/zsh
# Doppio clic: ricarica gli orari delle sveglie senza toccare il conto.
cd "$(dirname "$0")"
PLIST=~/Library/LaunchAgents/it.gioele.trader-claude.plist
sed "s#__CARTELLA__#$PWD#g" trader-claude.plist > "$PLIST"
launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "Fatto. Sveglie: 8:30 piano, 9:35 apertura, 13:00 metà seduta, 17:15 chiusura, venerdì 18:00 pagella."
