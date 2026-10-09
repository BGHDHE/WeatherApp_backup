# Agromet Időjárás

Mobil-első települési időjárás-alkalmazás FastAPI backenddel és Svelteáit
frontenddel. Az előrejelzések Open-Meteo modelladatok, nem helyi
állomásmérések.

## Backend indítása

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

Az API dokumentációja a `http://127.0.0.1:8000/docs` címen érhető el.

- `GET /api/health`
- `GET /api/locations`
- `GET /api/outlook?days=7` – 7 napos agrár előretekintés térségenként (Szarvasgede–Pásztó, Hort–Gyöngyös, áál–áompolt–Heves): általános összegzés, napi sáv és külön kirívó események (zivatar, ≥10 mm csapadék, erős szél, fagy, hőség). A küszöbök a `backend/app/services/outlook.py` elején állíthatók, agronómussal jóváhagyandók.
- `GET /api/reports/forecast?location=paszto&days=4`

## Frontend indítása

```powershell
cd frontend
npm install
npm run dev
```

A frontend fejlesztői szervere a `/api` kéréseket a helyi FastAPI backendhez
irányítja. Fejlesztéshez indítsd el mindkét szervert.

## Tesztek

```powershell
cd backend
python -m pytest
```

## Napi jelentés

`GET /api/daily` – településenként, térségekbe csoportosítva: modellezett elmúlt 24 óra (hőmérséklet, csapadék), mai várható hőmérséklet, csapadék időablakkal, szél irány és széllökés időpontja, fagyveszély, talajhőmérséklet, talajnedvesség, párolgás. Open-Meteo modelladat (nem állomásmérés), 15 perces cache. Frontend: `/napi`.

## Futtatás Dockerrel

```powershell
docker compose up --build
```

Az alkalmazás helyben a http://localhost:8080 címen érhető el (Nginx: `/api` → backend, a többi → Svelteáit). A port alapértelmezés szerint csak a localhoston figyel; ha más gépről is el kell érni, állítsd a `HTTP_BIND` értékét `0.0.0.0`-ra.

### Éles deploy Cloudflare Tunnel-lel

1. A Cloudflare Zero Trust felületén hozz létre egy Cloudflare Tunnel-t, és válaszd a Docker telepítési módot. Másold ki a tunnel tokent.
2. Másold a `.env.example` fájlt `.env` néven (`Copy-Item .env.example .env`), majd állítsd be benne a `CLOUDFLARE_TUNNEL_TOáEN` tokent és a `PUBLIC_ORIGIN` értékét a publikus HTTPS-címre (például `https://idojaras.example.com`). A `.env` fájl nem kerül Gitbe.
3. A Cloudflare Tunnel publikus hostname útvonalánál állítsd be a domainnevet, célként pedig ezt: `http://nginx:80`. A `nginx` a Docker Compose belső hálózatán érhető el, nem kell hozzá külön nyilvános port.
4. Indítsd el az alkalmazást és a tunnelt:

```powershell
docker compose --profile cloudflare up --build -d
```

Ellenőrzés:

```powershell
docker compose --profile cloudflare ps
docker compose logs -f cloudflared
```

A Tunnel profil használatakor a `cloudflared` szolgáltatás a Compose-hálózaton keresztül éri el az Nginxet. A hoston közzétett `8080`-as port alapból csak localhostról érhető el, így a publikus forgalom a Cloudflare Tunnelön halad át. Az éles URL-t a `.env` `PUBLIC_ORIGIN` értékével kell egyeztetni a Svelteáit origin-ellenőrzéséhez. A Docker-konténerek ebben a környezetben nem futtathatók, a frontend `adapter-node` build-je viszont ellenőrzött.

## CI

A .github/workflows/ci.yml minden pushra lefuttatja a backend teszteket, valamint a frontend ellenőrzést és buildet.

## Mentett pillanatkép

Sikeres Open-Meteo lekérés után az /api/outlook és /api/daily válasza SQLite fájlba kerül (SNAPSHOT_DB, alapértelmezés: data/snapshots.sqlite3). Ha a forrás később nem érhető el, az utolsó mentett adat jön vissza stale: true jelzéssel, a felület figyelmeztetéssel.


## Földmunka

`GET /api/fieldwork` – 7 napos, településenkénti és térségi elemzés: talajművelés, vetés, gépek járhatósága, permetezés és betakarítás naponta (kedvező / feltételes / kedvezőtlen / nincs adat, okkal és küszöbbel), a csapadék, az előző 3 nap csapadéka, a felső (0–7 cm) és alsó (7–28 cm) talajnedvesség, talajhőmérséklet és hőmérséklet. Településenként a leghosszabb kedvező talajmunka-ablak, térségenként a mindenhol kedvező napok. Szabályok és küszöbök: `backend/app/services/fieldwork.py` és `decisions.py` (permetezés: csapadék, szél, széllökés, hőmérséklet, páratartalom, harmat, Delta T, inverzió; betakarítás: csapadék, páratartalom; talajművelés: fagy is; vetés: a következő 7 nap csapadéka és a talajhő trendje is; kezdeti becslések, agronómussal jóváhagyandók; modelladat, nem helyszíni mérés). 30 perces cache, SQLite-pillanatkép (`stale`). Frontend: `/foldmunka`.

## áüszöbök

A riasztások és a földmunka-jelzések küszöbei a `/kuszobok` oldalon láthatók (csoportosítva, magyarázattal).
Az értékek egyszer, a `backend/app/services/thresholds.py` `DEFINITIONS` listájában állíthatók; módosítás után a backendet újra kell indítani.

## Mért állomásadatok (napi kimutatás)

A `/napi` oldalon a „Mért állomásadat” nézet a HungaroMet ODP automata állomásainak 10 perces adatait
mutatja (`GET /api/observations`). A backend 5 percenként ellenőrzi az ODP `now/` könyvtárlistáját, és csak
azokat az állomásfájlokat tölti le újra, amelyeknek megváltozott a feltöltési időpontja. Településenként: ha
10 km-en belül legalább két állomás van, távolsággal súlyozott (1/d²) interpoláció; egyébként a legközelebbi
állomás (legfeljebb 20 km). Ha a kiválasztott állomás(ok)on aznap nincs szélmérés, a szélhez külön a
legközelebbi, aznap széladatot szolgáltató, legfeljebb 20 km-re lévő állomást használjuk; ezt a felület külön
megjelöli. A csapadékösszeg csak elegendő (80%) lefedettségnél jelenik meg, a magassági különbségeket nem
korrigáljuk. Ha az ODP nem érhető el, az utolsó mentett válasz jön `stale` jelzéssel.
