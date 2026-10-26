# Far partire le sveglie dall'iPhone all'ora esatta

L'iPhone non fa il lavoro: all'orario giusto dice a GitHub «parti adesso», e GitHub parte
in pochi secondi invece di aspettare in coda. Se l'iPhone è spento o scarico, la sveglia
parte lo stesso con gli orari di GitHub. Se partono tutte e due, la seconda si ferma da sola.

## 1. Il codice che permette all'iPhone di avviare le sveglie (una volta sola)
Fallo dall'iPhone, con Safari, entrando in GitHub con il tuo account (GioeleMicozzi):
1. Apri **github.com/settings/personal-access-tokens/new**
2. **Token name:** `iPhone trader`
3. **Expiration:** la durata più lunga che ti propone (poi va rifatto alla scadenza)
4. **Repository access:** *Only select repositories* → **trader-claude**
5. **Permissions** → *Repository permissions* → **Actions** → **Read and write**
6. **Generate token** e copia il codice che inizia con `github_pat_`.

Con questo codice si possono solo avviare le sveglie di trader-claude: non legge le tue
altre cose e non può cambiare il codice. Non mandarlo a nessuno.

## 2. Il Comando Rapido «Sveglia trader»
App **Comandi Rapidi** → **+** in alto → **Aggiungi azione** → cerca **URL** →
**Ottieni contenuti dell'URL**. Poi:
1. Tocca «URL» e incolla:
   `https://api.github.com/repos/GioeleMicozzi/trader-claude/actions/workflows/sveglia.yml/dispatches`
2. Tocca la freccina **>** accanto all'azione per vedere tutte le opzioni:
   - **Metodo:** POST
   - **Intestazioni** → *Aggiungi nuova intestazione*, due volte:
     - chiave `Authorization`, valore `Bearer ` seguito dal codice (es. `Bearer github_pat_…`, con lo spazio)
     - chiave `Accept`, valore `application/vnd.github+json`
   - **Corpo richiesta:** JSON → *Aggiungi nuovo campo* → **Testo** → chiave `ref`, valore `main`
3. In alto rinomina il comando in **Sveglia trader** → **Fine**.

**Prova:** tocca il comando una volta. Se non compare nessun errore, dimmelo:
controllo su GitHub che la sveglia sia partita (a borsa chiusa si ferma subito, senza ordini).

## 3. Le cinque automazioni
Comandi Rapidi → scheda **Automazione** → **+** → **Ora del giorno**:
- imposta l'ora, scegli **Settimanale** e i giorni, poi **Esegui immediatamente**
  (così non chiede conferma) → **Avanti** → scegli **Sveglia trader**.

| Ora   | Giorni           | Sveglia      |
|-------|------------------|--------------|
| 08:12 | lun–ven          | piano        |
| 09:17 | lun–ven          | apertura     |
| 12:43 | lun–ven          | metà seduta  |
| 16:52 | lun–ven          | chiusura     |
| 18:03 | solo venerdì     | pagella      |

Il trader capisce da solo quale sveglia fare guardando l'ora di Roma.
