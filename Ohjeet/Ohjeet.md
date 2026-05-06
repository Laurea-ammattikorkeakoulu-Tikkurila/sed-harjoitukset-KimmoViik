# Ohjeet harjoitukseen

Tervetuloa! Tämä ohje kertoo, miten sed-komentoriviharjoitukset tehdään ja miten ajat harjoitusohjelman.

## Harjoittelu paikallisesti
Yritä ratkaista annetut tehtävät ensin komentoriviä käyttäen. Harjoituksissa käytettävät tiedostot löytyvät hakemistosta nimeltä `data`. Harjoitusten oikeat vastaukset saat testattua ajamalla sovelluksen jonka käyttö kuvataan alla. Sitä kannattaa ajaa esim. toisessa terminaalissa.

## Sovelluksen ajaminen

Kun avaat tämän harjoituksen GitHub Codespacessa, ohjelma **käynnistyy automaattisesti** terminaalissa.

> **Ensimmäisellä kerralla** VSCode kysyy luvan automaattisen tehtävän ajoon viestillä:
> *"This workspace has tasks (Käynnistä harjoitus) defined... Do you want to allow automatic tasks to run in all trusted workspaces?"*
> Valitse **Allow** — tämän jälkeen ohjelma käynnistyy ilman erillistä kysymystä kaikissa harjoituksissa.

Jos käynnistys ei jostain syystä onnistu, voit ajaa sen käsin:

```bash
python3 harjoitus.pyc
```

Ohjelma näyttää aluksi kattavan aloitusohjeistuksen ja antaa sitten tehtäviä yksi kerrallaan. Kirjoita sed-komento, joka tuottaa halutun lopputuloksen — ohjelma vertaa komentosi tulostusta oikeaan vastaukseen. Samaan lopputulokseen voi päästä monella eri komennolla.

Oikeat vastaukset tallentuvat automaattisesti, ja voit jatkaa harjoittelua käynnistämällä ohjelman uudestaan.

Komennot:
- `skip`  — siirry seuraavaan tehtävään
- `lista` — näytä tehtävien tila
- `apua`  — näytä aloitusohjeistus uudelleen
- `exit`  — tallenna tila ja poistu

## Tärkeää tietoa sed-komennosta

- `sed 's/vanha/uusi/'` — korvaa ensimmäisen osuman rivillä
- `sed 's/vanha/uusi/g'` — korvaa kaikki osumat rivillä
- `sed '/pattern/d'` — poista rivit joilla pattern esiintyy
- `sed -n '10,20p'` — tulosta vain rivit 10-20
- `sed -E` — laajennettu regex (käytä tätä monimutkaisemmissa patterneissa)

## Tärkeää — tekoälyapurit
Tekoälyapurit (GitHub Copilot, Claude, ChatGPT, Codeium ym.) **eivät ole sallittuja** tässä harjoituksessa. Tarkoitus on oppia Linux-komentorivin käyttöä itse.

## Tulosten lähettäminen

Kun olet saanut kaikki tehtävät tehtyä, ohjelma näyttää sinulle palautusohjeet automaattisesti onnitteluiden jälkeen. Sinun ei tarvitse muistaa git-komentoja etukäteen.

## Tukea saatavilla
Jos tarvitset apua tehtävissä kysy opettajalta.

*** Onnea harjoituksiin! ***
