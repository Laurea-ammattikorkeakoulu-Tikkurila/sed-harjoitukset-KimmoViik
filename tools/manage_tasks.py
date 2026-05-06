#!/usr/bin/env python3
"""
Ylläpitäjä-skripti tehtävä-tiedostojen salaukseen, purkamiseen
ja opiskelijalle vietävän Markdown-listan luomiseen.

Käyttö:
  python manage_tasks.py generate-key - Luo uusi Fernet-avain
  python manage_tasks.py decrypt      - Purkaa tehtavat.txt.enc -> tehtavat.txt
  python manage_tasks.py encrypt      - Salaa tehtavat.txt -> tehtavat.txt.enc (+ markdown-vienti)
  python manage_tasks.py student-md   - Luo tehtävistä Markdown-listan (ilman vastauksia)

Ympäristömuuttuja TASK_KEY vaaditaan encrypt/decrypt-toimintoihin.

Kommentit tehtavat.txt-tiedostossa:
  Rivit jotka alkavat '---' ohitetaan kommenttina. Esim:
    --- SED-harjoitukset
    # Korvaa sana foo sanalla bar
    sed 's/foo/bar/g' data/file.txt
"""

import sys
import os

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    print("❌ 'cryptography'-kirjasto puuttuu. Asenna: pip install cryptography")
    sys.exit(1)

ENC_FILE = "data/tasks/tehtavat.txt.enc"
PLAIN_FILE = "data/tasks/tehtavat.txt"
STUDENT_MD = "./tehtavat_student.md"


def get_key() -> bytes:
    """Lue salausavain ympäristömuuttujasta TASK_KEY."""
    key = os.environ.get("TASK_KEY")
    if not key:
        print("❌ Ympäristömuuttuja TASK_KEY puuttuu.")
        print("   Luo avain: python manage_tasks.py generate-key")
        print("   Aseta se:  export TASK_KEY='avain_tähän'")
        sys.exit(1)
    return key.encode()


def generate_key():
    """Luo uusi Fernet-avain ja tulosta se."""
    key = Fernet.generate_key().decode()
    print(f"🔑 Uusi Fernet-avain:\n\n   {key}\n")
    print("Tallenna tämä avain turvallisesti:")
    print("  1. GitHub: Settings → Secrets → Codespaces → TASK_KEY")
    print("  2. Lokaalisti: export TASK_KEY='" + key + "'")


def decrypt():
    """Purkaa salatun tiedoston"""
    if not os.path.exists(ENC_FILE):
        print(f"❌ Tiedostoa {ENC_FILE} ei löydy")
        sys.exit(1)

    try:
        f = Fernet(get_key())
        encrypted = open(ENC_FILE, 'rb').read()
        decrypted = f.decrypt(encrypted)

        with open(PLAIN_FILE, 'wb') as out:
            out.write(decrypted)

        print(f"✅ Tiedosto purettu: {ENC_FILE} -> {PLAIN_FILE}")
    except InvalidToken:
        print("❌ TASK_KEY on virheellinen — purkaminen epäonnistui.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Virhe purkamisessa: {e}")
        sys.exit(1)


def encrypt():
    """Salaa tavallisen tiedoston Fernetillä ja exportaa Markdown-lista"""
    if not os.path.exists(PLAIN_FILE):
        print(f"❌ Tiedostoa {PLAIN_FILE} ei löydy")
        sys.exit(1)

    try:
        f = Fernet(get_key())
        content = open(PLAIN_FILE, 'rb').read()
        encrypted = f.encrypt(content)

        with open(ENC_FILE, 'wb') as out:
            out.write(encrypted)

        print(f"✅ Tiedosto salattu: {PLAIN_FILE} -> {ENC_FILE}")
    except Exception as e:
        print(f"❌ Virhe salaamisessa: {e}")
        sys.exit(1)

    # Exportaa opiskelijoiden Markdown-lista automaattisesti salauksen jälkeen
    print("📝 Viedään opiskelijoiden Markdown-lista...")
    export_student_markdown()


def export_student_markdown(output=STUDENT_MD):
    """Luo Markdown-tiedosto, joka sisältää numeroidun listan tehtävistä ilman vastauksia.

    Lukee ensisijaisesti plain-tekstitiedoston (`PLAIN_FILE`). Jos sitä ei ole,
    yrittää purkaa sisällön `ENC_FILE`-tiedostosta ilman tallentamista.
    Ohittaa kommenttirivit jotka alkavat '---'.
    """
    content = None
    if os.path.exists(PLAIN_FILE):
        with open(PLAIN_FILE, 'r', encoding='utf-8') as fh:
            content = fh.read()
    elif os.path.exists(ENC_FILE):
        try:
            f = Fernet(get_key())
            encrypted = open(ENC_FILE, 'rb').read()
            content = f.decrypt(encrypted).decode('utf-8')
        except InvalidToken:
            print("❌ TASK_KEY on virheellinen — ei voitu lukea tehtäviä.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Virhe lukemisessa {ENC_FILE}: {e}")
            sys.exit(1)
    else:
        print(f"❌ Ei löydy {PLAIN_FILE} tai {ENC_FILE}")
        sys.exit(1)

    lines = content.splitlines()
    tasks = []
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
        # Odotetaan, että tehtävän kuvaus alkaa rivillä '#' ja seuraava ei-tyhjä rivi on vastaus
        if line.startswith('#'):
            desc = line.lstrip('#').strip()
            tasks.append(desc)
        i += 1

    # Rakennetaan markdown
    md_lines = ["# Tehtävät", "", "Seuraavat tehtävät — vastaukset jätetty pois.", ""]
    for idx, t in enumerate(tasks, start=1):
        md_lines.append(f"{idx}. {t}")
    md = "\n".join(md_lines) + "\n"

    # Varmista hakemisto
    out_dir = os.path.dirname(output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        with open(output, 'w', encoding='utf-8') as fh:
            fh.write(md)
        print(f"✅ Markdown luotu: {output}")
    except Exception as e:
        print(f"❌ Virhe kirjoitettaessa {output}: {e}")
        sys.exit(1)


def show_help():
    """Näytä ohje"""
    print(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "generate-key":
        generate_key()
    elif cmd == "decrypt":
        decrypt()
    elif cmd == "encrypt":
        encrypt()
    elif cmd in ("student-md", "export-md", "markdown"):
        export_student_markdown()
    elif cmd == "help" or cmd == "-h" or cmd == "--help":
        show_help()
    else:
        print(f"❌ Tuntematon komento: {cmd}")
        print()
        show_help()
        sys.exit(1)
