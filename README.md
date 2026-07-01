# Bot verificare locuri CFR Calatori

Verifica automat, la fiecare 15 minute, daca s-au eliberat locuri pentru o
ruta/data/tren specificat pe bilete.cfrcalatori.ro si trimite notificare pe
Telegram. Ruleaza gratuit in cloud (GitHub Actions) - nu necesita nimic
instalat sau drepturi de admin pe calculatorul tau.

## Pasul 1 - Creeaza un bot de Telegram (2 minute)

1. Deschide Telegram, cauta contul **@BotFather**.
2. Trimite comanda `/newbot` si urmeaza instructiunile (alegi un nume).
3. La final iti da un **token** (arata cam asa: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
   Salveaza-l, e nevoie mai jos.
4. Trimite orice mesaj botului tau nou creat (ex: "salut"), altfel nu poate
   sa iti raspunda mai tarziu.
5. Afla-ti `chat_id`: deschide in browser adresa de mai jos, inlocuind
   `<TOKEN>` cu tokenul tau, dupa ce ai trimis mesajul de la pasul 4:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Cauta in raspunsul JSON campul `"chat":{"id": 123456789 ...}` - acel
   numar e `chat_id`-ul tau.

## Pasul 2 - Creeaza repository-ul pe GitHub

1. Mergi pe https://github.com si logheaza-te (sau creeaza cont, gratuit).
2. Click pe "+" -> "New repository". Nume: `cfr-ticket-bot` (sau orice).
   Poate fi public sau privat (public = minute nelimitate gratuite pe
   GitHub Actions).
3. Dupa creare, foloseste butonul "Add file" -> "Upload files" din
   interfata web si incarca toate fisierele din acest folder, pastrand
   structura de directoare (inclusiv folderul `.github/workflows/`).

## Pasul 3 - Adauga secretele (token-urile), fara sa le pui in cod

In repository: **Settings -> Secrets and variables -> Actions -> New
repository secret**. Adauga doua secrete:

- `TELEGRAM_BOT_TOKEN` = tokenul de la Pasul 1
- `TELEGRAM_CHAT_ID` = chat_id-ul de la Pasul 1

## Pasul 4 - Ajusteaza ruta/data/trenul daca e nevoie

Fisierul e deja configurat pentru trenul IC 553, București Nord → Suceava,
03.07.2026, clasa a 2-a. Daca vrei sa schimbi ceva, deschide
`.github/workflows/check-tickets.yml` direct in browser (creion/edit) si
modifica aceste linii:

```yaml
DEPARTURE_SLUG: "Bucuresti-(toate-statiile)"
ARRIVAL_SLUG: "Suceava-(toate-statiile)"
TRAVEL_DATE: "03.07.2026"
TRAIN_NUMBER: "553"
TARGET_CLASS: "clasa a 2-a"
```

Pentru alte orase, foloseste acelasi format de slug (nume-cu-liniute,
exact cum apare in URL-ul de pe site cand faci o cautare manuala).

## Pasul 5 - Porneste manual prima rulare

In repository: tab **Actions** -> selecteaza workflow-ul "Verifica locuri
CFR" -> buton **Run workflow**. Asteapta sa termine (1-2 minute).

Deschide rularea si descarca artifact-ul **debug-screenshot** - e o
captura a paginii asa cum a vazut-o botul. Daca formularul nu a fost
completat corect (statii/data gresite), trimite-mi acel screenshot si
ajustez selectorii din `check_tickets.py`.

## Cum functioneaza dupa configurare

- Workflow-ul ruleaza automat la fiecare 15 minute.
- Daca gaseste semne ca trenul cautat are locuri disponibile, iti trimite
  un mesaj pe Telegram cu link direct catre site.
- Poti opri oricand botul dezactivand workflow-ul din tab-ul Actions, sau
  stergand repository-ul.

## Limitari de stiut

- Scriptul e construit pe baza structurii reale a site-ului (verificata
  din paginile pe care mi le-ai trimis), deci ar trebui sa functioneze
  din prima. Daca CFR isi schimba site-ul intre timp, selectorii se pot
  strica - in acest caz descarca artifact-ul `debug-screenshot` din
  Actions si trimite-mi-l din nou, ca sa actualizez scriptul.
- Nu incalca nimic ilegal - e o simpla verificare periodica a unei
  pagini publice, echivalenta cu a reincarca manual pagina des. Totusi,
  daca CFR blocheaza IP-uri care fac cereri foarte dese, mareste
  intervalul din cron (`*/15` inseamna la 15 minute; poti pune `*/30`).
- Botul verifica un singur tren (IC 553) si o singura clasa (a 2-a).
  Daca vrei sa monitorizezi mai multe trenuri/clase, pot extinde
  scriptul.
