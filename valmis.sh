#!/usr/bin/env bash
# Lähetä harjoituksen tulokset GitHub Classroomiin.
# Käyttää nykyistä branchia, ei pakota my/solution-nimeä.
set -e

# 1) Päivitä results.json check-tilassa (epäonnistuminen ei pysäytä)
python3 harjoitus.pyc --check || true

# 2) Lisää tulokset committiin
git add output/results.json configs/tila.json 2>/dev/null || true

# 3) Committaa (ei kaadu jos ei muutoksia)
if git diff --cached --quiet; then
  echo "ℹ️  Ei uusia muutoksia committoitavaksi."
else
  git commit -m "Lisää harjoituksen tulos"
fi

# 4) Pushaa nykyiseen branchiin
CURRENT=$(git rev-parse --abbrev-ref HEAD)
echo "📤 Pushataan branchiin: $CURRENT"
if git push origin "$CURRENT"; then
  echo "✅ Tulokset lähetetty branchiin '$CURRENT'."
  echo "   GitHub Actions ajaa autogradingin automaattisesti."
else
  echo "❌ Push epäonnistui. Tarkista verkkoyhteys ja että sinulla on push-oikeudet."
  exit 1
fi
