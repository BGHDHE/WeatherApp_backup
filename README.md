# Agromet Időjárás

Mobil-első települési időjárás-alkalmazás FastAPI backenddel és SvelteKit
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
- `GET /api/outlook?days=7` – 7 napos agrár előretekintés térségenként (Szarvasgede–Pásztó, Hort–Gyöngyös, Kál–Kompolt–Heves): általános összegzés, napi sáv és külön kirívó események (zivatar, ≥10 mm csapadék, erős szél, fagy, hőség). A küszöbök a `backend/app/services/outlook.py` elején állíthatók, agronómussal jóváhagyandók.
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

```
docker compose up --build
```

Az alkalmazás a http://localhost:8080 címen érhető el (Nginx: `/api` → backend, a többi → SvelteKit). Éles környezetben állítsd be a `PUBLIC_ORIGIN` környezeti változót a publikus URL-re (HTTPS-sel). A Docker-képek ebben a környezetben nem voltak kipróbálhatók (a Docker nincs telepítve), a frontend `adapter-node` build-je viszont ellenőrzött.

## CI

A .github/workflows/ci.yml minden pushra lefuttatja a backend teszteket, valamint a frontend ellenőrzést és buildet.

## Mentett pillanatkép

Sikeres Open-Meteo lekérés után az /api/outlook és /api/daily válasza SQLite fájlba kerül (SNAPSHOT_DB, alapértelmezés: data/snapshots.sqlite3). Ha a forrás később nem érhető el, az utolsó mentett adat jön vissza stale: true jelzéssel, a felület figyelmeztetéssel.


## Földmunka

`GET /api/fieldwork` – 7 napos, településenkénti és térségi elemzés: talajművelés, vetés, gépek járhatósága, permetezés és betakarítás naponta (kedvező / feltételes / kedvezőtlen / nincs adat, okkal és küszöbbel), a csapadék, az előző 3 nap csapadéka, a felső (0–7 cm) és alsó (7–28 cm) talajnedvesség, talajhőmérséklet és hőmérséklet. Településenként a leghosszabb kedvező talajmunka-ablak, térségenként a mindenhol kedvező napok. Szabályok és küszöbök: `backend/app/services/fieldwork.py` és `decisions.py` (permetezés: csapadék, széllökés, hőmérséklet; betakarítás: csapadék; kezdeti becslések, agronómussal jóváhagyandók; modelladat, nem helyszíni mérés). 30 perces cache, SQLite-pillanatkép (`stale`). Frontend: `/foldmunka`.

## Küszöbök és szakmai jóváhagyás

A riasztások és a földmunka-jelzések küszöbei a `/kuszobok` oldalon láthatók (csoportosítva, alapértékkel,
magyarázattal). Az oldalról CSV tölthető le vagy nyomtatható, így az agronómus átnézheti és jóváhagyhatja.

Módosítás: másold a `backend/thresholds.example.json` fájlt `backend/data/thresholds.json` néven
(vagy add meg a `THRESHOLDS_FILE` környezeti változót), írd át az értékeket, töltsd ki az `approved_by`
és `approved_on` mezőt, majd indítsd újra a backendet. Az ismeretlen vagy érvénytelen kulcsok az alapértéket kapják.
Dockerben a `data/` kötet (`snapshots:/app/data`) a fájlt is megőrzi.
