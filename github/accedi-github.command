#!/bin/zsh
# Doppio clic: collega il Mac al TUO account GitHub (gioelemicozzi7@gmail.com).
# Se l'account non c'è ancora, crealo prima su github.com/signup con quella mail.
echo "Fra poco compare un codice di 8 caratteri e si apre il browser."
echo "Nel browser: entra con l'account di gioelemicozzi7@gmail.com (NON quello di Valeria),"
echo "incolla il codice e autorizza."
echo
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
echo
gh auth status --active
echo; read "?Premi Invio per chiudere."
