#!/usr/bin/env python3
import subprocess
import shlex
import json
import re
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    print("❌ 'cryptography'-kirjasto puuttuu. Asenna: pip install cryptography")
    sys.exit(1)

# Ladataan konfiguraatio `configs/config.json`. Jos sitä ei ole,
# käytetään kovakoodattuja oletuksia.
CONFIG_PATH = Path("configs/config.json")

def load_config(path: Path) -> Dict[str, Any]:
    defaults = {
        "tehtavat_tiedosto": "data/tasks/tehtavat.txt.enc",
        "tila_tiedosto": "configs/tila.json",
        "results_file": "output/results.json",
        "timeout_seconds": 3,
        "allowed_commands": ["sed", "sort", "wc", "uniq", "head", "tail", "cat"],
    }
    if not path.exists():
        return defaults
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        # merge defaults with provided config
        for k, v in defaults.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return defaults


CONFIG = load_config(CONFIG_PATH)

TEHTAVAT_TIEDOSTO = CONFIG["tehtavat_tiedosto"]
TILA_TIEDOSTO = CONFIG["tila_tiedosto"]
RESULTS_FILE = CONFIG["results_file"]
TIMEOUT_SECONDS = int(CONFIG.get("timeout_seconds", 3))
SALLITUT_KOMENNOT = tuple(CONFIG.get("allowed_commands", []))

# ---------- Apufunktiot ----------

def lue_tehtavat(tiedosto: str) -> List[Tuple[str, str]]:
    """Lue tehtävät salatusta tiedostosta.

    Tiedosto on Fernet-salattu (AES). Salausavain luetaan
    ympäristömuuttujasta TASK_KEY.
    Tehtäväformaatti: kuvaus aloitetaan merkillä '#' ja seuraava
    ei-tyhjä rivi on oikea komento. Kommenttirivit alkavat '---' ja ohitetaan.
    Palauttaa listan `(kuvaus, oikea_komento)` -tupleja.
    """
    p = Path(tiedosto)
    if not p.exists():
        return []

    key = os.environ.get("TASK_KEY")
    if not key:
        print("❌ Ympäristömuuttuja TASK_KEY puuttuu.")
        print("   Aja tämä harjoitus GitHub Codespacessa,")
        print("   tai aseta TASK_KEY ympäristömuuttuja.")
        sys.exit(1)

    try:
        f = Fernet(key.encode())
        encrypted = p.read_bytes()
        decoded = f.decrypt(encrypted).decode('utf-8')
    except InvalidToken:
        print("❌ TASK_KEY on virheellinen — tehtäviä ei voitu purkaa.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Virhe tehtävien purkamisessa: {e}")
        sys.exit(1)

    lines = decoded.splitlines()
    tehtavat: List[Tuple[str, str]] = []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Ohita kommenttirivit jotka alkavat '---'
        if line.startswith('---'):
            i += 1
            continue

        # Uusi muoto: kuvaus-rivi alkaa '#'
        if line.startswith('#'):
            kuvaus = line.lstrip('#').strip()
            # etsi seuraava ei-tyhjä rivi komennoksi
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            oikea = lines[j].strip() if j < n else ""
            tehtavat.append((kuvaus, oikea))
            i = j + 1
            continue

        # Muoto: kuvaus on jo käsitelty yllä (#-rivinä); muuten ohitetaan
        i += 1

    return tehtavat


# Kielletyt raakapatternit: komentokorvaukset ja rivinvaihdot.
# Shlex ei erottele näitä omiksi tokeneiksi, joten ne tarkistetaan
# ennen parsintaa raakamerkkijonosta.
_KIELLETYT_RAAKAPATTERNIT = re.compile(r'\$\(|\$\{|`|\n|\r')

# Kaikki merkit jotka shlex käsittelee operaattoreina.
_PUNCTUATION = set('|;&><')


def turvallinen_komento(cmd: str) -> bool:
    """Tarkista, että komento käyttää vain sallittuja ohjelmia.

    Sallitaan putkitetut komennot (esim. "sed ... | wc -l"). Putkien
    etsiminen tehdään shlex-lekserillä, jotta lainausmerkkien sisällä
    olevat '|'-merkit (esim. regexissä 'a|b') eivät riko jakoa.

    Estetään komentorivin erikoismerkit: ;  &&  ||  >  >>  <  <<
    sekä komentokorvaukset ($(...), `...`, ${...}) ja rivinvaihdot.
    """
    # Vaihe 1: hylkää komentokorvaukset ja rivinvaihdot raakatekstistä,
    # koska shlex ei erottele niitä omiksi tokeneiksi.
    if _KIELLETYT_RAAKAPATTERNIT.search(cmd):
        return False

    # Vaihe 2: tokenisoi shlex-lekserillä. Laajennettu punctuation_chars
    # tekee merkeistä ; & < > erillisiä operaattoritokeneja.
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars='|;&><')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except Exception:
        return False

    if not tokens:
        return False

    # Vaihe 3: jaa tokenit putkivaiheisiin; hylkää kaikki muut operaattorit.
    stages: List[List[str]] = [[]]
    for tok in tokens:
        if tok == '|':
            stages.append([])
        elif tok and all(c in _PUNCTUATION for c in tok):
            # Mikä tahansa shell-operaattori paitsi yksittäinen | → hylkää
            return False
        else:
            stages[-1].append(tok)

    # Vaihe 4: tarkista, että jokaisen vaiheen ensimmäinen tokeni on sallittu.
    for stage in stages:
        if not stage:
            return False
        if stage[0] not in SALLITUT_KOMENNOT:
            return False
    return True


def aja_komento(cmd):
    try:
        # Käytä timeout-arvoa konfiguraatiosta
        res = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        # Palauta stdout ilman loppurivejä
        return res.stdout.strip()
    except Exception as e:
        return f"(virhe: {e})"


def lataa_tila():
    p = Path(TILA_TIEDOSTO)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def tallenna_tila(tila):
    p = Path(TILA_TIEDOSTO)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tila, ensure_ascii=False, indent=2), encoding='utf-8')


def rakenna_results(tila: Dict[str, Any], yhteensa: int, opiskelijatiedot: Dict[str, str]) -> Dict[str, Any]:
    """Rakenna results.json-rakenne nykyisestä tilasta."""
    per_task = []
    oikein = 0
    for i in range(yhteensa):
        ts = tila.get(str(i))
        if isinstance(ts, dict):
            status = ts.get("status") or "ei_vastattu"
            student_cmd = ts.get("student_cmd")
        else:
            status = ts if ts is not None else "ei_vastattu"
            student_cmd = None
        if status == "oikein":
            oikein += 1
        per_task.append({"id": i, "status": status, "student_cmd": student_cmd})

    return {
        "nimi": opiskelijatiedot.get("nimi", ""),
        "opiskelijanumero": opiskelijatiedot.get("opiskelijanumero", ""),
        "score": oikein,
        "total": yhteensa,
        "per_task": per_task,
    }


def kirjoita_results(results: Dict[str, Any]) -> None:
    """Kirjoita results.json levylle."""
    p = Path(RESULTS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def print_intro() -> None:
    """Tulosta opiskelijalle kattava aloitusohjeistus."""
    print("""
================================================================
  TERVETULOA — Linux CLI: sed-harjoitus
================================================================

Mitä tämä on?
  Tämä on Laurea AMK:n Linux-kurssin harjoitus, jossa opit
  käyttämään komentoriviä ja etenkin sed-komentoa. Tehtäviä
  on yhteensä 18, ja ohjelma tarkistaa vastauksesi automaattisesti.

Mitä teet?
  Ohjelma näyttää sinulle yhden tehtävän kerrallaan. Kirjoita
  Linux-komento, joka tuottaa halutun lopputuloksen. Ohjelma
  vertaa komentosi tulostusta oikeaan vastaukseen.

Sallitut komennot:
  sed, sort, wc, uniq, head, tail, cat
  (voit myös putkittaa niitä, esim. `sed ... | wc -l`)

Data-tiedostot (kansio `data/`):
  - kirja.txt          — romaaniteksti (korvaukset, poistot, muotoilu)
  - asiakastiedot.txt  — nimiä, puhelimia, hetuja, IP:tä, sähköposteja
  - log.txt            — järjestelmälokirivit (login/logout/Error/Warning)

Navigointi interaktiivisessa moodissa:
  skip   — siirry seuraavaan tehtävään
  lista  — näytä kaikkien tehtävien tilanne
  apua   — näytä tämä ohjeistus uudelleen
  exit   — tallenna tila ja poistu

Edistyminen:
  - Vastauksesi tallentuvat automaattisesti.
  - Voit jatkaa koska tahansa käynnistämällä ohjelman uudestaan.
  - Kun olet ratkaissut kaikki tehtävät, ohjelma näyttää
    palautusohjeet automaattisesti onnitteluiden jälkeen.

Säännöt:
  - Tekoälyapurit (Copilot, Claude, ChatGPT, Codeium jne.) eivät
    ole tässä harjoituksessa sallittuja — tarkoitus on oppia itse.

Apua:
  - Lue `Ohjeet/Ohjeet.md` lisäohjeita varten.
  - Jos jäät jumiin, kysy opettajalta.

================================================================
""")


def tulosta_palautusohjeet() -> None:
    """Tulosta palautusohjeet kun kaikki tehtävät on suoritettu."""
    print("""
================================================================
  🎉 ONNITTELUT — kaikki tehtävät suoritettu!
================================================================

Lähetä tuloksesi GitHub Classroomiin yhdellä komennolla:

    bash valmis.sh

Skripti tekee puolestasi:
  1. Päivittää output/results.json (--check)
  2. Committaa tulokset
  3. Pushaa nykyiseen branchiin
  4. GitHub Actions ajaa autogradingin automaattisesti

Jos haluat tehdä sen käsin nykyiseen branchiisi:

    python3 harjoitus.py --check
    git add output/results.json configs/tila.json
    git commit -m "Lisää harjoituksen tulos"
    git push origin $(git rev-parse --abbrev-ref HEAD)

Jos push epäonnistuu, tarkista että olet kirjautunut GitHubiin
ja että sinulla on kirjoitusoikeudet repositorioon. Kysy
tarvittaessa opettajalta apua.
================================================================
""")


def paivita_results_opiskelijatiedot(opiskelijatiedot: Dict[str, str]) -> None:
    """Kirjoita nimi ja opiskelijanumero results.json-tiedostoon."""
    p = Path(RESULTS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)

    nykyinen: Dict[str, Any] = {}
    if p.exists():
        try:
            nykyinen = json.loads(p.read_text(encoding='utf-8'))
            if not isinstance(nykyinen, dict):
                nykyinen = {}
        except Exception:
            nykyinen = {}

    nykyinen["nimi"] = opiskelijatiedot.get("nimi", "")
    nykyinen["opiskelijanumero"] = opiskelijatiedot.get("opiskelijanumero", "")
    p.write_text(json.dumps(nykyinen, ensure_ascii=False, indent=2), encoding='utf-8')


def nollaa_tehtavien_tila(tila: Dict[str, Any]) -> None:
    """Poista kaikki tehtäväkohtaiset avaimet tilasta, mutta säilytä nimi/opiskelijanumero."""
    for key in [k for k in list(tila.keys()) if k.isdigit()]:
        del tila[key]


def varmista_opiskelijatiedot(tila: Dict[str, Any], kysy_kayttajalta: bool = False) -> Dict[str, Any]:
    """Varmista, että tilassa on opiskelijan nimi ja opiskelijanumero.

    Jos nimi tai opiskelijanumero muuttuu aiemmin tallennetusta, tehtävien
    eteneminen nollataan automaattisesti — uuden opiskelijan ei pidä
    periä edellisen tuloksia.
    """
    nimi = tila.get("nimi")
    opiskelijanumero = tila.get("opiskelijanumero")

    if not kysy_kayttajalta:
        opiskelijatiedot = {
            "nimi": nimi or "",
            "opiskelijanumero": opiskelijanumero or ""
        }
        paivita_results_opiskelijatiedot(opiskelijatiedot)
        return opiskelijatiedot

    vanha_nimi = nimi
    vanha_numero = opiskelijanumero

    # Kysy nimi. Jos tallennettu nimi on olemassa, tarjoa se oletuksena.
    while True:
        if vanha_nimi:
            vastaus = input(f"👤 Anna nimesi [{vanha_nimi}]: ").strip()
            uusi_nimi = vastaus if vastaus else vanha_nimi
        else:
            uusi_nimi = input("👤 Anna nimesi: ").strip()
        if uusi_nimi:
            break
        print("⚠️  Nimi ei voi olla tyhjä.")

    # Kysy opiskelijanumero samalla tavalla.
    while True:
        if vanha_numero:
            vastaus = input(f"🆔 Anna opiskelijanumerosi [{vanha_numero}]: ").strip()
            uusi_numero = vastaus if vastaus else vanha_numero
        else:
            uusi_numero = input("🆔 Anna opiskelijanumerosi: ").strip()
        if uusi_numero:
            break
        print("⚠️  Opiskelijanumero ei voi olla tyhjä.")

    # Jos opiskelijan identiteetti eroaa aiemmasta, nollaa tehtävien eteneminen.
    # Vertailu normalisoidaan: strip + lower, jotta pelkkä kirjainkoon
    # tai ylimääräisten välilyöntien ero ei nollaa edistymistä.
    norm = lambda s: (s or "").strip().lower()
    identiteetti_muuttui = (norm(uusi_nimi) != norm(vanha_nimi)) or (norm(uusi_numero) != norm(vanha_numero))
    if identiteetti_muuttui and any(k.isdigit() for k in tila.keys()):
        print("\n🔄 Opiskelijatiedot muuttuivat — nollataan tehtävien eteneminen.")
        nollaa_tehtavien_tila(tila)

    tila["nimi"] = uusi_nimi
    tila["opiskelijanumero"] = uusi_numero

    opiskelijatiedot = {
        "nimi": uusi_nimi,
        "opiskelijanumero": uusi_numero,
    }
    paivita_results_opiskelijatiedot(opiskelijatiedot)
    return opiskelijatiedot

# ---------- CI / CHECK ----------

def check_mode():
    tehtavat = lue_tehtavat(TEHTAVAT_TIEDOSTO)
    tila = lataa_tila()
    opiskelijatiedot = varmista_opiskelijatiedot(tila, kysy_kayttajalta=False)

    oikein = 0
    yhteensa = len(tehtavat)
    changed = False

    print("🔍 CHECK-MODE - Validoidaan uudelleen")

    for i in range(yhteensa):
        task_status = tila.get(str(i))

        # Jos tehtävä on vastauksessa objektina (uusi muoto)
        if isinstance(task_status, dict):
            status = task_status.get("status")
            student_cmd = task_status.get("student_cmd")
            correct_cmd = tehtavat[i][1]  # Lue oikea komento tehtävät-tiedostosta

            if status == "oikein" and student_cmd and correct_cmd:
                # Validoi uudelleen ajamalla komennot
                student_res = aja_komento(student_cmd)
                correct_res = aja_komento(correct_cmd)

                student_lines = sorted(student_res.splitlines()) if student_res else []
                correct_lines = sorted(correct_res.splitlines()) if correct_res else []

                if student_lines == correct_lines:
                    oikein += 1
                else:
                    # Validointi epäonnistui - merkitse väärin
                    tila[str(i)]["status"] = "väärin"
                    changed = True
            elif status == "oikein":
                oikein += 1
        # Vanha muoto (string)
        elif task_status == "oikein":
            oikein += 1

    # Jos jotain muuttui tilassa, tallenna se
    if changed:
        tallenna_tila(tila)

    # Rakenna koneellisesti luettava tulos ja kirjoita levylle
    results = rakenna_results(tila, yhteensa, opiskelijatiedot)
    kirjoita_results(results)

    print(json.dumps(results, ensure_ascii=False))

    print(f"Oikein: {oikein}/{yhteensa}")

    if oikein == yhteensa:
        print("✅ Kaikki tehtävät oikein")
        sys.exit(0)
    else:
        print("❌ Kaikki tehtävät eivät ole oikein")
        sys.exit(1)

# ---------- Interaktiivinen ----------

def interactive_mode(show_intro: bool = True):
    if show_intro:
        print_intro()

    tehtavat = lue_tehtavat(TEHTAVAT_TIEDOSTO)
    tila = lataa_tila()
    tila_olemassa = Path(TILA_TIEDOSTO).exists()

    # Pyydä opiskelijatiedot. Jos identiteetti muuttuu, tila nollataan.
    opiskelijatiedot = varmista_opiskelijatiedot(tila, kysy_kayttajalta=True)
    tallenna_tila(tila)

    def sync_results():
        results = rakenna_results(tila, len(tehtavat), opiskelijatiedot)
        kirjoita_results(results)

    # Alkutilanteen synkronointi, jotta results.json on ajan tasalla
    sync_results()

    skipped_this_session = set()

    def is_completed(task_id):
        """Tarkista onko tehtävä valmis"""
        status = tila.get(str(task_id))
        if isinstance(status, dict):
            return status.get("status") == "oikein"
        return status == "oikein"

    # Aloita aina ensimmäisestä tehtävästä (indeksi 0) ja etene järjestyksessä.
    # Jo ratkaistut tehtävät näytetään lyhyesti ja ohitetaan automaattisesti,
    # jotta opiskelija näkee edistymisensä ensimmäisestä tehtävästä alkaen.
    current = 0
    while True:
        if current >= len(tehtavat):
            remaining = [k for k in range(len(tehtavat)) if not is_completed(k)]
            if not remaining:
                print("\n🎉 Kaikki tehtävät suoritettu!")
                tulosta_palautusohjeet()
            else:
                print(f"\nℹ️  Tehtäviä tekemättä: {len(remaining)}. Voit palata niihin käynnistämällä ohjelman uudestaan.")
            return

        i = current

        # Jos tehtävä on jo ratkaistu tai skipattu tässä sessiossa,
        # näytä se lyhyesti ja siirry seuraavaan.
        if is_completed(i):
            ts = tila.get(str(i), {})
            prev_cmd = ts.get("student_cmd") if isinstance(ts, dict) else None
            print(f"\n✅ Tehtävä {i+1}/{len(tehtavat)} jo ratkaistu" + (f": {prev_cmd}" if prev_cmd else ""))
            current += 1
            continue

        if i in skipped_this_session:
            current += 1
            continue

        kuvaus, oikea = tehtavat[i]

        print(f"\n📝 Tehtävä {i+1}/{len(tehtavat)}")
        print(f"{i+1}. {kuvaus}")

        cmd = input("💻 Komento (skip / exit / lista / apua): ").strip()

        if not cmd:
            print("⚠️  Syötä komento tai käytä skip/exit/lista/apua")
            continue

        if cmd == "apua":
            print_intro()
            continue

        if cmd == "exit":
            tallenna_tila(tila)
            sync_results()
            print("💾 Tila tallennettu.")
            # Näytä montako tehtävää on vielä tekemättä ja ohje palata niihin
            remaining = [i for i in range(len(tehtavat)) if not is_completed(i)]
            tehdyt = sum(1 for i in range(len(tehtavat)) if is_completed(i))
            total = len(tehtavat)
            if remaining:
                print(f"ℹ️  Tehty: {tehdyt}/{total}. Tehtäviä tekemättä: {len(remaining)}. Voit palata niihin käynnistämällä ohjelman uudestaan.")
            else:
                print(f"\n🎉 Kaikki tehtävät suoritettu! Tehty: {tehdyt}/{total}")
                tulosta_palautusohjeet()
            return

        if cmd == "lista":
            print("\n📋 Tehtävien status:")
            for j in range(len(tehtavat)):
                task_status = tila.get(str(j))
                # Jos tehtävä on tallennettu objektina
                if isinstance(task_status, dict):
                    if task_status.get("status") == "oikein":
                        status_msg = "✅ Oikein"
                    elif task_status.get("status") == "väärin":
                        status_msg = "❌ Väärin"
                    else:
                        status_msg = "⏳ Skipattu"
                else:
                    # Ei tallennettua tilaa
                    if j in skipped_this_session:
                        status_msg = "⏳ Skipattu"
                    elif task_status is None:
                        status_msg = "⏳ Ei vastattu"
                    elif task_status == "oikein":
                        status_msg = "✅ Oikein"
                    elif task_status == "väärin":
                        status_msg = "❌ Väärin"
                    else:
                        status_msg = "⏳ Ei vastattu"

                print(f"{status_msg:<15} {j+1}. {tehtavat[j][0]}")
            print()
            continue

        if cmd == "skip":
            skipped_this_session.add(i)
            print(f"⏭️  Tehtävä {i+1} skipattu. Seuraavaan...")
            continue

        if not turvallinen_komento(cmd):
            print("❌ Komento ei ole sallittu tässä harjoituksessa.")
            continue

        # Suoritetaan komennot
        opiskelija_res = aja_komento(cmd)
        oikea_res = aja_komento(oikea)

        # Jos komento epäonnistui (returncode != 0) tai stdout tyhjä, merkitään väärin
        if not opiskelija_res:
            print("❌ Sinun komennollasi ei tullut tulosta tai se epäonnistui.")
            tila[str(i)] = {
                "status": "väärin",
                "student_cmd": cmd
            }
        else:
            # Verrataan rivit järjestettynä listana (duplikaatit säilyvät)
            opiskelija_lines = sorted(opiskelija_res.splitlines())
            oikea_lines = sorted(oikea_res.splitlines()) if oikea_res else []

            # Tulostetaan tulokset ja vertailu
            print("— Oikea vastaus —")
            print(oikea_res)
            print("— Sinun vastaus —")
            print(opiskelija_res)
            print("— Vertailtavat rivit (järjestettynä) —")
            print("Oikea:", oikea_lines)
            print("Sinun:", opiskelija_lines)

            if opiskelija_lines == oikea_lines:
                print("✅ Oikein")
                tila[str(i)] = {
                    "status": "oikein",
                    "student_cmd": cmd
                }
            else:
                print("❌ Väärin")
                # Näytetään erot set-muodossa
                oikea_set = set(oikea_lines)
                opiskelija_set = set(opiskelija_lines)
                only_oikea = sorted(oikea_set - opiskelija_set)
                only_sinu = sorted(opiskelija_set - oikea_set)
                if only_oikea:
                    print("Rivejä vain oikeassa tuloksessa:")
                    for r in only_oikea:
                        print(f"+ {r}")
                if only_sinu:
                    print("Rivejä vain sinun tuloksessasi:")
                    for r in only_sinu:
                        print(f"- {r}")
                tila[str(i)] = {
                    "status": "väärin",
                    "student_cmd": cmd
                }

        tallenna_tila(tila)
        sync_results()


# ---------- MAIN ----------

if __name__ == "__main__":
    if "--check" in sys.argv or "--ci" in sys.argv:
        check_mode()
    else:
        show_intro = "--no-intro" not in sys.argv
        interactive_mode(show_intro=show_intro)
