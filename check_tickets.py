"""
Bot de verificare locuri CFR Calatori.

Flux confirmat pe baza paginilor reale trimise de utilizator:
  1. Navigheaza direct la URL-ul de cautare (fara reCAPTCHA, GET simplu):
     https://bilete.cfrcalatori.ro/ro-RO/Rute-trenuri/{DEP}/{ARR}?DepartureDate=...
  2. Gaseste cardul <li id="li-itinerary-N"> care contine numarul trenului cautat.
  3. Click pe butonul "Cumpara" (#button-itinerary-N-buy) - navigheaza direct
     la pasul 2 ("Clase si oferte"), fara panou/buton intermediar.
  4. Click pe "Verifica trenurile selectate" (#button-available-places).
  5. Citeste continutul modalului (#div-step-2-available-places-result) si cauta
     un rand "X locuri disponibile la clasa a 2-a".

GitHub Actions nu poate rula un "schedule" mai des de 1 data pe minut, deci
verificarea la 30 de secunde se face intr-o bucla in interiorul unei singure
rulari de job, timp de cateva ore; workflow-ul reporneste jobul periodic
(prin cron, ex. la fiecare 5 ore) ca sa acopere continuu tot intervalul.

Config prin variabile de mediu (setate ca GitHub Secrets / workflow env):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  DEPARTURE_SLUG          (ex: "Bucuresti-(toate-statiile)")
  ARRIVAL_SLUG            (ex: "Suceava-(toate-statiile)")
  TRAVEL_DATE             (format DD.MM.YYYY, ex: "03.07.2026")
  TRAIN_NUMBER            (ex: "553")
  TARGET_CLASS            (text de cautat in lista de locuri, ex: "clasa a 2-a")
  CHECK_INTERVAL_SECONDS  (implicit 30)
  MAX_RUNTIME_SECONDS     (implicit 21000 = 5h50m, sub limita de 6h a runnerelor gratuite)
"""

import os
import re
import time
import requests
from playwright.sync_api import sync_playwright

DEPARTURE_SLUG = os.environ.get("DEPARTURE_SLUG", "Bucuresti-(toate-statiile)")
ARRIVAL_SLUG = os.environ.get("ARRIVAL_SLUG", "Suceava-(toate-statiile)")
TRAVEL_DATE = os.environ.get("TRAVEL_DATE", "03.07.2026")
TRAIN_NUMBER = os.environ.get("TRAIN_NUMBER", "553")
TARGET_CLASS = os.environ.get("TARGET_CLASS", "clasa a 2-a")

CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "30"))
MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", "21000"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEARCH_URL = (
    f"https://bilete.cfrcalatori.ro/ro-RO/Rute-trenuri/{DEPARTURE_SLUG}/{ARRIVAL_SLUG}"
    f"?DepartureDate={TRAVEL_DATE}&TimeSelectionId=0&MinutesInDay=0"
    f"&OrderingTypeId=0&ConnectionsTypeId=1&BetweenTrainsMinimumMinutes=15"
)


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram nu e configurat, sar peste notificare. Mesaj:", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=15,
        )
        print("Telegram status:", resp.status_code, resp.text[:200])
    except Exception as e:
        print("Eroare trimitere Telegram:", e)


def accept_cookies(page):
    for text in ["Sunt de acord!", "Accept", "De acord"]:
        try:
            page.click(f"text={text}", timeout=3000)
            return
        except Exception:
            continue


def find_itinerary_index(page, train_number: str):
    """Cauta printre cardurile de itinerarii pe cel care contine numarul trenului."""
    items = page.locator("li[id^='li-itinerary-']")
    count = items.count()
    print(f"Am gasit {count} itinerarii in rezultate.")
    for i in range(count):
        item = items.nth(i)
        text = item.inner_text()
        if re.search(rf"\b{re.escape(train_number)}\b", text):
            item_id = item.get_attribute("id")  # ex: li-itinerary-2
            match = re.search(r"li-itinerary-(\d+)", item_id or "")
            if match:
                idx = match.group(1)
                print(f"Trenul {train_number} gasit in itinerariul index {idx}.")
                return idx
    return None


def check_once(browser) -> str:
    """
    Face o singura verificare completa (pagina noua, de la zero).
    Intoarce unul din: "found", "not_found", "train_missing", "error".
    """
    page = browser.new_page()
    try:
        print("Deschid:", SEARCH_URL)
        page.goto(SEARCH_URL, timeout=60000)
        accept_cookies(page)
        page.wait_for_timeout(3000)

        idx = find_itinerary_index(page, TRAIN_NUMBER)

        if idx is None:
            page.screenshot(path="debug_screenshot.png", full_page=True)
            print(f"Nu am gasit trenul {TRAIN_NUMBER} in rezultatele cautarii.")
            return "train_missing"

        try:
            page.click(f"#button-itinerary-{idx}-buy", timeout=10000)
            # click-ul pe "Cumpara" navigheaza direct la pasul 2
            # ("Clase si oferte") - nu mai exista un panou intermediar
            # cu buton separat "Continua".
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_selector(
                "#button-available-places", state="visible", timeout=15000
            )
        except Exception as e:
            page.screenshot(path="debug_screenshot.png", full_page=True)
            try:
                with open("debug_panel.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
            except Exception as e2:
                print("Nu am putut salva debug_panel.html:", e2)
            print("Eroare la selectarea trenului / avansarea la pasul 2:", e)
            return "error"

        try:
            page.click("#button-available-places", timeout=10000)
            page.wait_for_selector(
                "#div-loading-step-2-available-places.not-displayed",
                timeout=20000,
            )
            page.wait_for_timeout(1000)
        except Exception as e:
            page.screenshot(path="debug_screenshot.png", full_page=True)
            print("Eroare la verificarea locurilor disponibile:", e)
            return "error"

        result_text = page.locator("#div-step-2-available-places-result").inner_text()
        page.screenshot(path="debug_screenshot.png", full_page=True)

        print("Continut gasit:")
        print(result_text)

        target_found = TARGET_CLASS.lower() in result_text.lower()

        if target_found:
            seats_match = re.search(
                rf"(\d+)\s+locuri disponibile\s+(?:la|pentru)?\s*{re.escape(TARGET_CLASS)}",
                result_text,
                re.IGNORECASE,
            )
            seats_info = f"{seats_match.group(1)} locuri" if seats_match else "locuri disponibile"
            send_telegram(
                f"🚆 Loc liber gasit! Tren {TRAIN_NUMBER}, {TRAVEL_DATE}, "
                f"{TARGET_CLASS}: {seats_info}.\n"
                f"Cumpara rapid: {SEARCH_URL}"
            )
            print(f"GASIT: {TARGET_CLASS} are locuri disponibile ({seats_info}).")
            return "found"
        else:
            print(f"Inca nu sunt locuri la {TARGET_CLASS}.")
            return "not_found"
    finally:
        page.close()


def run():
    start_time = time.time()
    already_notified = False
    consecutive_errors = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        while time.time() - start_time < MAX_RUNTIME_SECONDS:
            iteration_start = time.time()
            try:
                status = check_once(browser)
            except Exception as e:
                print("Eroare neasteptata in check_once:", e)
                status = "error"

            if status == "found":
                # notifica o singura data cat timp raman locuri; daca
                # dispar si reapar, se trimite din nou o notificare noua
                already_notified = True
                consecutive_errors = 0
            elif status == "not_found":
                already_notified = False
                consecutive_errors = 0
            elif status == "train_missing":
                consecutive_errors = 0
                send_telegram(
                    f"⚠️ Botul CFR nu a gasit trenul {TRAIN_NUMBER} in rezultate "
                    f"pentru {TRAVEL_DATE}. Verifica manual: {SEARCH_URL}"
                )
            elif status == "error":
                consecutive_errors += 1
                # nu trimite alerta la fiecare eroare (ar spama la 30s),
                # doar daca esueaza repetat
                if consecutive_errors in (3, 10):
                    send_telegram(
                        f"⚠️ Botul CFR intampina erori repetate la verificarea "
                        f"trenului {TRAIN_NUMBER}. Verifica manual: {SEARCH_URL}"
                    )

            elapsed = time.time() - iteration_start
            sleep_for = max(0, CHECK_INTERVAL_SECONDS - elapsed)
            time.sleep(sleep_for)

        browser.close()

    print("Am atins limita de timp per job, ma opresc (workflow-ul va reporni jobul).")


if __name__ == "__main__":
    run()
