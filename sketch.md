# Teljes fejlesztési menet: a tervezéstől a production-ig

Ez az útmutató a korábban megbeszélt architektúrát (FastAPI backend + SvelteKit frontend + PostgreSQL adatbázis + Open-Meteo adatforrás) ülteti át egy teljes, lépésről lépésre követhető fejlesztési folyamatba. A hangsúly a gyorsaságon és a mobil-első használaton van.

---

## 1. Tervezés és követelmények

### 1.1. Funkcionális követelmények

A rendszernek az alábbi fő funkciókat kell nyújtania:

- **Településenkénti napi jelentés**: mért és várható hőmérséklet, csapadék, szél, fagyveszély, talajmutatók.
- **Többnapos előrejelzés**: legalább 4 napra előre, településenkénti bontásban.
- **Döntéstámogató összegzés**: permetezés, betakarítás, talajmunka időablakok általános időjárási feltételek alapján (nem kultúra-/szerspecifikus ajánlás; az okot és a küszöböt is mutatja). *MVP utáni fázis*, az adatminőség és a szabályok szakmai jóváhagyása után.
- **Adatátláthatóság**: minden adat mellett forrás, típus (megfigyelés/modell/előrejelzés) és frissítési idő.
- **Fagyriasztás**: településszintű színkódolt figyelmeztetés.
- **Mobil-első, offline is működő felület**: PWA-ként telepíthető, gyors betöltés.
- **Automatikus frissítés**: napi cron job, amely legenerálja a jelentést és elérhetővé teszi az API-n.

### 1.2. Nem-funkcionális követelmények

- **Teljesítmény**: mért cél, pl. p95 első betöltés < 2 s átlagos 4G hálózaton és középkategóriás telefonon (Lighthouse/WebPageTest), interakció < 100 ms; cache-elt (ismételt) betöltés < 1 s.
- **Mobil optimalizálás**: reszponzív, érintésbarát, PWA.
- **Skálázhatóság**: több település, több felhasználó, bővíthető szabályrendszer.
- **Karbantarthatóság**: tiszta architektúra, tesztelhető üzleti logika.
- **Költséghatékonyság**: ingyenes adatforrás (Open-Meteo), minimális infrastruktúra.

### 1.3. Architektúra áttekintése

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Open-Meteo API  │────▶│  FastAPI Backend │────▶│  PostgreSQL     │
│  (időjárás adat) │     │  (ETL + API)     │     │  (adattár)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                 │                         │
                                 ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Döntési motor   │────▶│  SvelteKit      │
                        │  (szabályok)     │     │  Frontend (PWA) │
                        └──────────────────┘     └─────────────────┘
```

---

## 2. Technológiai stack és fejlesztői környezet

### 2.1. Választott stack

| Réteg | Technológia | Miért |
|-------|-------------|-------|
| Backend | **FastAPI** (Python) | Gyors, async, automatikus OpenAPI docs, Pydantic validáció |
| Frontend | **SvelteKit** (TypeScript) | Legkisebb bundle, kiváló mobil teljesítmény, PWA támogatás |
| Adatbázis | **PostgreSQL** | Robusztus, jól skálázható, JSONB támogatás |
| ORM | **SQLAlchemy 2.0** (async) | Típusos, async, jól integrálható FastAPI-val |
| Migráció | **Alembic** | Adatbázis-séma verziózás |
| Validáció | **Pydantic v2** | Request/response séma, automatikus dokumentáció |
| Frontend stílus | **Tailwind CSS v4** | Gyors UI fejlesztés, kis méret |
| PWA | **@vite-pwa/sveltekit** | Service worker, offline támogatás |
| Konténerizáció | **Docker + Docker Compose** | Egységes fejlesztői és production környezet |
| Reverse proxy | **Nginx** | SSL, statikus fájlok, terheléselosztás |
| CI/CD | **GitHub Actions** | Automatikus tesztelés és deploy |

### 2.2. Fejlesztői környezet beállítása

```bash
# 1. Projekt könyvtár létrehozása
mkdir agromet-app && cd agromet-app

# 2. Backend mappa és virtuális környezet
mkdir backend && cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic pydantic-settings httpx apscheduler jinja2

# 3. Frontend létrehozása SvelteKit-tel
cd ..
npx sv create frontend
# Válaszd: SvelteKit minimal, TypeScript, Tailwind CSS, ESLint, Prettier

# 4. Docker Compose fájl létrehozása a gyökérben
```

**Docker Compose** – egységes környezet minden fejlesztőnek:

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agromet
      POSTGRES_USER: agromet
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"   # csak helyben elérhető; productionben ne publikáld
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agromet -d agromet"]
      interval: 5s
      retries: 10

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://agromet:${DB_PASSWORD}@db:5432/agromet
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"

  worker:
    build: ./backend
    command: ["python", "-m", "app.worker"]
    environment:
      DATABASE_URL: postgresql+asyncpg://agromet:${DB_PASSWORD}@db:5432/agromet
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    environment:
      ORIGIN: http://localhost:3000
    ports:
      - "3000:3000"
    # fejlesztésben a /api hívásokat a Vite dev proxy (vite.config.ts: server.proxy) irányítja a backendhez

volumes:
  pgdata:
```

---

## 3. Backend fejlesztés (FastAPI)

### 3.1. Projektstruktúra

A FastAPI projektet **funkció-alapú** szervezéssel érdemes felépíteni, hogy a domain logika elkülönüljön az infrastruktúrától. Egy jól bevált struktúra:

```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── locations.py      # települések végpontjai
│   │       ├── reports.py        # napi jelentés
│   │       └── forecasts.py      # előrejelzés
│   ├── core/
│   │   ├── config.py             # Pydantic Settings
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py               # SQLAlchemy Base
│   │   ├── session.py            # async session factory
│   │   └── models.py             # ORM modellek
│   ├── schemas/                  # Pydantic sémák
│   │   ├── location.py
│   │   ├── weather.py
│   │   └── report.py
│   ├── services/                 # üzleti logika
│   │   ├── weather_fetcher.py    # Open-Meteo integráció
│   │   ├── decision_engine.py    # permetezés/betakarítás/fagy
│   │   └── report_builder.py     # jelentés összeállítás
│   ├── repository/               # adatbázis műveletek
│   │   └── weather_repo.py
│   ├── worker.py                 # ütemezett ETL (külön folyamat)
│   └── main.py                   # FastAPI belépési pont
├── alembic/                      # migrációk
├── tests/
├── pyproject.toml
└── Dockerfile
```

Ez a felosztás lehetővé teszi, hogy a `decision_engine.py`-t önállóan teszteld, anélkül hogy az adatbázis vagy az API futna.

### 3.2. Adatbázis-séma (PostgreSQL)

A séma tervezésénél érdemes **rétegekre bontani**: nyers mérések, napi aggregátumok és generált jelentések.

```sql
-- Települések
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    lat NUMERIC(9,6) NOT NULL,
    lon NUMERIC(9,6) NOT NULL,
    region TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Órás mérések/előrejelzések
CREATE TABLE hourly_weather (
    id BIGSERIAL PRIMARY KEY,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    temp NUMERIC(4,1),
    dew_point NUMERIC(4,1),
    precip NUMERIC(5,2),
    precip_prob SMALLINT,
    wind NUMERIC(4,1),
    wind_gust NUMERIC(4,1),
    humidity SMALLINT,
    soil_temp_6cm NUMERIC(4,1),      -- Open-Meteo: soil_temperature_6cm (nem 5 cm)
    soil_moisture NUMERIC(5,3),      -- m³/m³ (a megjelenítésnél tf%-ra váltva)
    et0 NUMERIC(4,2),
    -- 'observation' = tényleges megfigyelés/analízis, 'forecast' = előrejelzés
    source TEXT NOT NULL CHECK (source IN ('observation', 'forecast')),
    provider TEXT NOT NULL DEFAULT 'open-meteo',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),  -- mikor töltöttük le
    UNIQUE (location_id, ts, source)
);
CREATE INDEX idx_hourly_location_ts ON hourly_weather (location_id, ts DESC);

-- Napi összegzések
CREATE TABLE daily_summary (
    id BIGSERIAL PRIMARY KEY,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    temp_min NUMERIC(4,1),
    temp_max NUMERIC(4,1),
    surface_min NUMERIC(4,1),
    precip_mm NUMERIC(5,2),
    wind_max NUMERIC(4,1),
    frost_level TEXT,
    UNIQUE (location_id, date)
);

-- Generált jelentések (JSONB a rugalmasság miatt)
CREATE TABLE reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_reports_date ON reports (report_date DESC);
```

### 3.3. Open-Meteo integráció

Az Open-Meteo API ingyenes és nem igényel API kulcsot (nem kereskedelmi használatra; kereskedelmi felhasználásnál ellenőrizd a licencfeltételeket). A `services/weather_fetcher.py` feladata a lekérdezés és a válasz normalizálása.

> **Fontos:** a településkoordinátára adott érték modelladat, nem helyi állomásmérés. A múltbeli órákat a `past_days` paraméterrel kérd le, és `source='observation'` helyett csak akkor jelöld „mértnek” a UI-n, ha valódi állomásadatból származik; egyébként „modellezett (elmúlt 24 óra)” felirat kell. Hiányzó adatnál `null` és „nincs adat” jelenjen meg, ne becsült érték.

```python
# services/weather_fetcher.py
import httpx
from datetime import date, datetime, timezone
from app.schemas.weather import HourlyData

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m", "dew_point_2m", "precipitation",
    "precipitation_probability", "wind_speed_10m", "wind_gusts_10m",
    "relative_humidity_2m", "soil_temperature_6cm", "soil_moisture_1_to_3cm",
    "et0_fao_evapotranspiration",
]

DAILY_VARS = [
    "temperature_2m_min", "temperature_2m_max",
    "precipitation_sum", "wind_speed_10m_max",
]

async def fetch_forecast(lat: float, lon: float, days: int = 4) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
        "timezone": "Europe/Budapest",
        "forecast_days": days,
        "past_days": 1,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(OPEN_METEO_BASE, params=params)
        resp.raise_for_status()
        return resp.json()
```

### 3.4. Döntési motor

A `services/decision_engine.py` tartalmazza a szabályalapú logikát. A küszöbértékeket érdemes YAML-ből betölteni, hogy később konfigurálhatóak legyenek.

> **Megjegyzés:** a kimenet általános időjárási feltételeket jelez, nem kultúra- vagy készítményspecifikus ajánlást (a permetezés a növényvédő szer címkéje és a helyi előírások szerint dönthető el). Minden jelzéshez add vissza az okot, a használt küszöböt és az adat frissességét is. A szabályokat agronómus hagyja jóvá.

```python
# services/decision_engine.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import yaml

RULES = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "config" / "rules.yaml").read_text(encoding="utf-8")
)

@dataclass
class HourlyData:
    ts: datetime
    temp: float
    dew_point: float
    precip: float
    precip_prob: float
    wind: float
    wind_gust: float
    humidity: float
    soil_moisture: float

def is_spraying_ok(h: HourlyData, next_6h: list[HourlyData]) -> bool:
    r = RULES["spraying"]
    if h.wind > r["wind_max"] or h.wind_gust > r["wind_gust_max"]:
        return False
    if sum(x.precip for x in next_6h) > r["precip_next_6h_max"]:
        return False
    if not (r["temp_min"] <= h.temp <= r["temp_max"]):
        return False
    if not (r["humidity_min"] <= h.humidity <= r["humidity_max"]):
        return False
    if (h.temp - h.dew_point) < r["dew_point_delta_min"]:
        return False
    return True

def find_windows(hours, predicate, min_len=3, lookahead=6):
    """Összefüggő órák keresése, ahol a feltétel igaz.

    Az órákat időrendbe rendezi, a hiányzó órát (lyukat) ablaktörésnek veszi,
    és a hiányos előretekintésű (az adatsor végén lévő) órákat nem értékeli.
    """
    hours = sorted(hours, key=lambda h: h.ts)
    windows, run = [], []

    def close():
        if len(run) >= min_len:
            windows.append((run[0].ts, run[-1].ts))

    for i, h in enumerate(hours):
        ahead = hours[i + 1 : i + 1 + lookahead]
        complete = len(ahead) == lookahead and ahead[-1].ts - h.ts == timedelta(hours=lookahead)
        contiguous = not run or h.ts - run[-1].ts == timedelta(hours=1)
        if complete and predicate(h, ahead):
            if not contiguous:
                close()
                run.clear()
            run.append(h)
        else:
            close()
            run.clear()
    close()
    return windows
```

### 3.5. API végpontok

```python
# app/api/routes/reports.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.schemas.report import DailyReport, ForecastResponse
from app.services.report_builder import build_daily_report, build_forecast

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/today", response_model=DailyReport)
async def get_today_report(
    location: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    report = await build_daily_report(session, location)
    if not report:
        raise HTTPException(404, "Nincs jelentés ehhez a településhez")
    return report

@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    location: str = Query(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$"),  # slug
    days: int = Query(4, ge=1, le=7),
    session: AsyncSession = Depends(get_session),
):
    result = await build_forecast(session, location, days)
    if not result:
        raise HTTPException(404, "Ismeretlen település")
    return result
```

A FastAPI automatikusan generál OpenAPI dokumentációt a `/docs` végponton, ami megkönnyíti a frontend fejlesztést és a tesztelést.

### 3.6. Ütemezett adatgyűjtés

Az adatgyűjtést **külön worker folyamat** végezze (pl. `worker` service a Compose-ban), ne az API-ban: több Uvicorn worker esetén minden worker saját ütemezőt indítana, így az ETL többszörösen futna. Az ETL legyen idempotens (`INSERT ... ON CONFLICT DO UPDATE`), hibánál próbálkozzon újra (exponenciális késleltetéssel), és az API jelezze, ha az adat elavult (`fetched_at`).

```python
# app/worker.py  (indítás: python -m app.worker)
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.etl import run_hourly_etl

async def main():
    scheduler = AsyncIOScheduler(timezone="Europe/Budapest")
    scheduler.add_job(run_hourly_etl, "cron", minute=5, max_instances=1, coalesce=True)
    scheduler.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Frontend fejlesztés (SvelteKit)

### 4.1. Projekt inicializálás és struktúra

```bash
npx sv create frontend
# Válaszd: SvelteKit minimal, TypeScript, Tailwind CSS, ESLint, Prettier, Playwright
```

A frontend struktúrája:

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   │   ├── LocationCard.svelte
│   │   │   ├── ForecastTable.svelte
│   │   │   ├── SummaryBox.svelte
│   │   │   └── FrostAlertBadge.svelte
│   │   ├── api/
│   │   │   └── client.ts          # API hívások
│   │   ├── types.ts               # API válasz típusok (LocationReport, Summary, Forecast, DailyReport)
│   │   └── stores/
│   │       └── reports.ts         # Svelte store-ok
│   ├── routes/
│   │   ├── +page.svelte           # főoldal
│   │   ├── +layout.svelte         # közös layout
│   │   └── location/[slug]/
│   │       └── +page.svelte       # település részletei
│   └── service-worker.ts          # PWA service worker
├── static/
│   ├── manifest.json              # PWA manifest
│   └── icons/
└── svelte.config.js
```

### 4.2. API kliens

```typescript
// src/lib/api/client.ts
import type { DailyReport, Forecast } from "$lib/types";

// Azonos domain alatti relatív útvonal (Nginx proxyzza a backendhez),
// így a böngészőből nem kell konténernevet elérni.
const BASE = "/api";

async function getJson<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API hiba: ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchTodayReport = (location?: string) =>
  getJson<DailyReport>("/reports/today", location ? { location } : {});

export const fetchForecast = (location: string, days = 4) =>
  getJson<Forecast>("/reports/forecast", { location, days: String(days) });
```

### 4.3. Főoldal és komponensek

```svelte
<!-- src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from "svelte";
  import { fetchTodayReport } from "$lib/api/client";
  import type { LocationReport, Summary } from "$lib/types";
  import LocationCard from "$lib/components/LocationCard.svelte";
  import SummaryBox from "$lib/components/SummaryBox.svelte";

  let reports: LocationReport[] = [];
  let summary: Summary | null = null;
  let loading = true;
  let error: string | null = null;

  onMount(async () => {
    try {
      const data = await fetchTodayReport();
      reports = data.locations;
      summary = data.summary;
    } catch (e) {
      error = "Az adatok jelenleg nem érhetők el.";
    } finally {
      loading = false;
    }
  });
</script>

<main class="container mx-auto p-4 max-w-5xl">
  <h1 class="text-2xl font-bold mb-4">Napi időjárás – {new Date().toLocaleDateString("hu-HU")}</h1>

  {#if loading}
    <p>Betöltés…</p>
  {:else if error}
    <p role="alert" class="text-red-700">{error}</p>
  {:else}
    {#if summary}
      <SummaryBox {summary} />
    {/if}

    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {#each reports as report (report.location)}
        <LocationCard {report} />
      {/each}
    </div>
  {/if}
</main>
```

```svelte
<!-- src/lib/components/LocationCard.svelte -->
<script lang="ts">
  import type { LocationReport } from "$lib/types";
  export let report: LocationReport;
  const frostColor: Record<string, string> = {
    "nincs": "bg-green-100 border-green-500",
    "alacsony": "bg-yellow-100 border-yellow-500",
    "mérsékelt": "bg-orange-100 border-orange-500",
    "magas": "bg-red-100 border-red-500",
  };
</script>

<div class="border rounded-lg p-4 {frostColor[report.frost_level] ?? 'bg-white'}">
  <h2 class="font-semibold text-lg">{report.location}</h2>
  <p class="text-sm text-gray-600">
    {report.temp_min ?? "n/a"} – {report.temp_max ?? "n/a"} °C (várható: {report.forecast_min} – {report.forecast_max} °C)
  </p>
  <p class="text-xs text-gray-500">Frissítve: {new Date(report.fetched_at).toLocaleString("hu-HU")}</p>
  <p class="text-sm">Csapadék: {report.precip_mm} mm</p>
  <p class="text-sm">Szél: {report.wind_ms} m/s</p>
  {#if report.frost_level !== "nincs"}
    <p class="text-sm font-medium mt-2">⚠️ Fagyveszély: {report.frost_level}</p>
  {/if}
</div>
```

### 4.4. PWA beállítás

A `@vite-pwa/sveltekit` csomaggal minimális konfigurációval PWA-t készíthetsz:

```bash
npm install -D @vite-pwa/sveltekit
```

```typescript
// vite.config.ts
import { sveltekit } from "@sveltejs/kit/vite";
import { SvelteKitPWA } from "@vite-pwa/sveltekit";

export default {
  server: { proxy: { "/api": "http://localhost:8000" } },  // fejlesztői proxy
  plugins: [
    sveltekit(),
    SvelteKitPWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Agromet Időjárás",
        short_name: "Agromet",
        theme_color: "#16a34a",
        icons: [
          { src: "/icons/192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,json}"],
      },
    }),
  ],
};
```

A SvelteKit beépítetten támogatja a service workereket: ha létrehozol egy `src/service-worker.ts` fájlt, azt automatikusan bundleli és regisztrálja. **Ne használd egyszerre a `@vite-pwa/sveltekit` generált workerét és a saját `service-worker.ts`-t**: válassz egyet. Az alábbi kézi változat a statikus fájlokat cache-first, az API-t network-first módon kezeli, hogy ne maradjon korlátlanul elavult adat; a UI jelezze az adat `fetched_at` idejét offline módban.

```typescript
// src/service-worker.ts
/// <reference types="@sveltejs/kit" />
import { build, files, version } from "$service-worker";

const CACHE = `cache-${version}`;
const API_CACHE = "api-cache";
const ASSETS = [...build, ...files];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(async (keys) => {
      for (const key of keys) {
        if (key !== CACHE && key !== API_CACHE) await caches.delete(key);
      }
    })
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request)
        .then(async (res) => {
          if (res.ok) (await caches.open(API_CACHE)).put(event.request, res.clone());
          return res;
        })
        .catch(async () => (await caches.match(event.request)) ?? Response.error())
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached ?? fetch(event.request))
  );
});
```

---

## 5. Tesztelés

### 5.1. Backend tesztek

A döntési motor a legfontosabb tesztelendő komponens. Rögzített forgatókönyvekkel (fixture-ökkel) érdemes tesztelni:

```python
# tests/test_decision_engine.py
import pytest
from app.services.decision_engine import is_spraying_ok, find_windows

def make_hour(temp=15, dew=10, precip=0, wind=2, humidity=70, hour=9):
    from datetime import datetime
    from app.services.decision_engine import HourlyData
    return HourlyData(
        ts=datetime(2026, 10, 6, hour),
        temp=temp, dew_point=dew, precip=precip,
        precip_prob=0, wind=wind, wind_gust=wind + 2,
        humidity=humidity, soil_moisture=20,
    )

def test_spraying_ok_calm_morning():
    h = make_hour(wind=2, humidity=70)
    next_6h = [make_hour()] * 6
    assert is_spraying_ok(h, next_6h) is True

def test_spraying_not_ok_windy():
    h = make_hour(wind=6)
    next_6h = [make_hour()] * 6
    assert is_spraying_ok(h, next_6h) is False

def test_spraying_not_ok_rain_incoming():
    h = make_hour()
    next_6h = [make_hour(precip=1.0)] * 6
    assert is_spraying_ok(h, next_6h) is False

def test_find_windows_skips_incomplete_lookahead_and_gaps():
    hours = [make_hour(hour=h) for h in range(6, 20)]
    windows = find_windows(hours, is_spraying_ok, min_len=3)
    # az utolsó 6 óra nem értékelhető (hiányos előretekintés)
    assert windows == [(hours[0].ts, hours[7].ts)]
    gapped = hours[:4] + hours[6:]
    assert all(start >= hours[6].ts for start, _ in find_windows(gapped, is_spraying_ok))
```

```bash
pytest tests/ -v
```

### 5.2. Frontend tesztek

A SvelteKit-hez a **Vitest** (unit) és a **Playwright** (E2E) a bevált eszközök:

```typescript
// src/lib/components/LocationCard.test.ts
import { render, screen } from "@testing-library/svelte";
import LocationCard from "./LocationCard.svelte";

test("megjeleníti a település nevét", () => {
  render(LocationCard, {
    props: {
      report: {
        location: "Szarvasgede",
        temp_min: 1.2, temp_max: 24.9,
        forecast_min: 1, forecast_max: 17,
        precip_mm: 0.0, wind_ms: 3.8, frost_level: "mérsékelt",
        fetched_at: "2026-10-06T06:05:00Z",
      },
    },
  });
  expect(screen.getByText("Szarvasgede")).toBeInTheDocument();
  expect(screen.getByText(/Fagyveszély/)).toBeInTheDocument();
});
```

### 5.3. Integrációs tesztek

Az API végpontokat érdemes valós adatbázis ellen tesztelni (pl. `testcontainers`-szel vagy külön teszt adatbázissal). A `httpx.AsyncClient` segítségével az API-t közvetlenül hívhatod.

---

## 6. Deployment (production)

### 6.1. Docker multi-stage build

A backend és frontend külön Docker image-be kerül, a `docker-compose.prod.yml` pedig összeköti őket.

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app
RUN useradd -r -u 1001 app
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json .
RUN npm ci --omit dev
ENV NODE_ENV=production
CMD ["node", "build"]
```

### 6.2. Nginx reverse proxy

Az Nginx végzi az SSL terminációt, a statikus fájlok kiszolgálását és a két szolgáltatás összekötését.

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name agromet.example.com;

    ssl_certificate /etc/letsencrypt/live/agromet.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agromet.example.com/privkey.pem;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6.3. CI/CD pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e backend/ && pytest backend/tests/
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: cd frontend && npm ci && npm run test

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to server
        env:
          SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
          SSH_HOST: ${{ secrets.DEPLOY_HOST }}
        run: |
          install -m 600 /dev/null key && printf '%s\n' "$SSH_KEY" > key
          ssh -i key -o StrictHostKeyChecking=yes "$SSH_HOST" "cd /opt/agromet && git pull --ff-only && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head && docker compose -f docker-compose.prod.yml up -d"
          # a known_hosts bejegyzést előre rögzítsd (pl. secret vagy ssh-keyscan ellenőrzött ujjlenyomattal)
```

### 6.4. Adatbázis migráció

A production indulás előtt futtasd az Alembic migrációkat (a fenti pipeline a build után, az új konténerek indítása előtt futtatja őket, így hibás migráció esetén a régi verzió tovább fut). Visszafelé kompatibilis migrációkat írj, és deploy előtt készíts mentést.

```bash
alembic upgrade head
```

A migrációkat a CI/CD pipeline-ba is beépítheted, de érdemes külön lépésben, hogy hiba esetén ne álljon le a deploy.

---

## 7. Monitorozás és karbantartás

### 7.1. Health check

A FastAPI-hoz adj egy egyszerű health végpontot:

```python
@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}
```

### 7.2. Logging

Használj strukturált logolást (pl. `structlog` vagy `loguru`), és küldd a logokat egy központi helyre (pl. Loki, Datadog).

### 7.3. Hibakezelés

A FastAPI-ban központi exception handler-rel egységes hibaválaszokat adj:

```python
@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.exception("Váratlan hiba")
    return JSONResponse(status_code=500, content={"detail": "Belső hiba"})
```

### 7.4. Adatbázis karbantartás

- Rendszeres `VACUUM ANALYZE` a PostgreSQL-en.
- Régi órás adatok archiválása vagy particionálás (pl. havi partíciók).
- Backup: napi `pg_dump`, heti teljes mentés, távoli tárolóba.

### 7.5. Frissítések

- **Biztonsági frissítések**: havonta `npm audit` és `pip-audit`.
- **Adatforrás változások**: figyeld az Open-Meteo API változásait.
- **Küszöbértékek hangolása**: a gazdák visszajelzései alapján kalibráld a `rules.yaml`-t.

---

## 8. Összefoglaló ütemterv

| Fázis | Időtartam | Eredmény |
|-------|-----------|----------|
| **Tervezés** | 1 hét | Követelmények, architektúra, stack |
| **Környezet** | 2 nap | Docker Compose, projektstruktúra |
| **Backend MVP** | 2 hét | Open-Meteo integráció, adatbázis, API |
| **Döntési motor** | 1 hét (MVP után, szakmai jóváhagyással) | Fagy + általános időjárási feltételek (permetezés/betakarítás) |
| **Frontend MVP** | 2 hét | SvelteKit oldal, kártyák, összegzés |
| **PWA** | 3 nap | Service worker, manifest, offline |
| **Tesztelés** | 1 hét | Unit + integrációs tesztek |
| **Deployment** | 3 nap | Docker, Nginx, CI/CD |
| **Monitorozás** | folyamatos | Health check, logging, backup |

A teljes MVP **kb. 6-8 hét** alatt elkészíthető egy tapasztalt fejlesztővel (kezdeti becslés; az adatminőség és a döntési szabályok validálása, valamint a PWA tesztelése növelheti). Az **első MVP** a településlista, előrejelzés, fagyjelzés, adatforrás/frissesség jelzése és a mobilos UI; a permetezési/betakarítási ablakok ezután jönnek. A kulcs a **fokozatos iteráció**: először működjön a backend és az adatgyűjtés, aztán a döntési motor, végül a frontend és a PWA. A FastAPI és a SvelteKit kombinációja különösen alkalmas erre a projektre, mert mindkettő gyors fejlesztést és kiváló futásidejű teljesítményt nyújt.


Példa alkalmazás felépítés (illusztráció: a „Mért” érték a valóságban csak akkor nevezhető mértnek, ha állomásadatból származik; modelladatnál „modellezett” jelölés kell, a „(felt.)” jelölésű értékek pedig feltételezettek, nem szabad ténynek megjeleníteni):

NAPI IDŐJÁRÁS - 2026. október 6., kedd

1. Aktuális napi adatok - 2026. október 6.

Szarvasgede

Mért hőmérséklet (24 h): 1,2 - 24,9 °C
Felszíni min.: 0,3 °C
Várható hőmérséklet ma: 1 - 17 °C
Csapadék: Mért: 0,0 mm | Várható ma: 4,0 mm (16:00-21:00, 70%)
Szél: ÉNy 3,8 m/s (széllökés: 8,8 m/s, 14:00-17:00) | Max. széllökés (24 h): 6,8 m/s
Fagyveszély: Mérsékelt - hajnalban 1-2 °C, gyenge felszíni fagy valószínű
Talajmutatók: Talajhőmérséklet (5 cm): ~10-12 °C | Talajnedvesség: 18-22 tf% | Párolgás: 1,0-1,5 mm/nap

Pásztó

Mért hőmérséklet (24 h): 7,8 - 23,4 °C
Felszíni min.: 0,8 °C
Várható hőmérséklet ma: 2 - 16 °C
Csapadék: Mért: 0,2 mm | Várható ma: 5,2 mm (15:00-20:00, 75%)
Szél: ÉNy 3,2 m/s (széllökés: 7,5 m/s, 13:00-16:00) | Max. széllökés (24 h): 6,2 m/s
Fagyveszély: Mérsékelt - reggel 2 °C, felszínközeli fagy lehet
Talajmutatók: Talajhőmérséklet (5 cm): ~11-13 °C | Talajnedvesség: 20-24 tf% | Párolgás: 1,2-1,8 mm/nap

Heves

Mért hőmérséklet (24 h): (felt.) 6 - 24 °C
Felszíni min.: (felt.) 1,0 °C
Várható hőmérséklet ma: 3 - 17 °C
Csapadék: Mért: (felt.) 0,0 mm | Várható ma: 3,5 mm (16:00-20:00, 70%)
Szél: ÉNy 3,5 m/s | Max. széllökés (24 h): (felt.) 6,0 m/s
Fagyveszély: Alacsony-mérsékelt - hajnalban 3 °C, felszínközeli fagy nem kizárt
Talajmutatók: Talajhőmérséklet (5 cm): ~11-13 °C | Talajnedvesség: 18-22 tf% | Párolgás: 1,0-1,5 mm/nap

Kompolt

Mért hőmérséklet (24 h): (felt.) 6 - 23 °C
Felszíni min.: (felt.) 1,2 °C
Várható hőmérséklet ma: 3 - 17 °C
Csapadék: Mért: (felt.) 0,0 mm | Várható ma: 4,0 mm (16:00-21:00, 70%)
Szél: ÉNy 3,3 m/s
Fagyveszély: Alacsony-mérsékelt - 3 °C körül, gyenge fagy lehet
Talajmutatók: Talajhőmérséklet (5 cm): ~11-13 °C | Talajnedvesség: 18-22 tf% | Párolgás: 1,1-1,6 mm/nap

Hort

Mért hőmérséklet (24 h): (felt.) 7 - 24 °C
Felszíni min.: (felt.) 1,5 °C
Várható hőmérséklet ma: 4 - 17 °C
Csapadék: Mért: (felt.) 0,3 mm | Várható ma: 3,0 mm (17:00-21:00, 65%)
Szél: ÉNy 3,6 m/s
Fagyveszély: Alacsony - 4 °C körül, felszíni fagy nem valószínű
Talajmutatók: Talajhőmérséklet (5 cm): ~12-14 °C | Talajnedvesség: 16-20 tf% | Párolgás: 1,2-1,7 mm/nap

Gyöngyös

Mért hőmérséklet (24 h): 8,1 - 24,8 °C
Felszíni min.: hiányos
Várható hőmérséklet ma: 4 - 18 °C
Csapadék: Mért: 0,4 mm | Várható ma: 3,8 mm (16:00-20:00, 70%)
Szél: ÉNy 3,8 m/s
Fagyveszély: Alacsony - 4 °C körül, felszíni fagy nem valószínű
Talajmutatók: Talajhőmérséklet (5 cm): ~12-14 °C | Talajnedvesség: 18-22 tf% | Párolgás: 1,3-1,8 mm/nap

2. Következő napok előrejelzése - térségenként

Szarvasgede

Szerda (okt. 7.): 12-20 °C | Csapadék: 0 mm | Szél: 2-8 m/s
Megjegyzés: Borult. Fagyveszély: alacsony (hajnalban 12 °C). Talajhő: ~13-15 °C, nedvesség: 16-20 tf%, párolgás: 1,5-2,0 mm/nap.
Csütörtök (okt. 8.): 9-14 °C | Csapadék: 0 mm | Szél: 2-9 m/s
Megjegyzés: Borult, hűvös. Fagyveszély: alacsony (9 °C). Talajhő: ~12-14 °C, nedvesség: 18-22 tf%, párolgás: 1,0-1,5 mm/nap.
Péntek (okt. 9.): 8-14 °C | Csapadék: 0 mm | Szél: 2-5 m/s
Megjegyzés: Elszórt felhők. Fagyveszély: alacsony (8 °C). Talajhő: ~11-13 °C, nedvesség: 16-20 tf%, párolgás: 1,2-1,8 mm/nap.
Szombat (okt. 10.): 4-15 °C | Csapadék: 0 mm | Szél: 2 m/s
Megjegyzés: Részben felhős. Fagyveszély: mérsékelt (hajnalban 4 °C, talajmenti fagy lehetséges). Talajhő: ~10-12 °C, nedvesség: 14-18 tf%, párolgás: 1,0-1,4 mm/nap.

Pásztó

Szerda (okt. 7.): 12-23 °C | Csapadék: 0 mm | Szél: 1-3 m/s
Megjegyzés: Felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 16-20 tf%, párolgás: 1,8-2,2 mm/nap.
Csütörtök (okt. 8.): 11-21 °C | Csapadék: 0 mm | Szél: 1-4 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~13-15 °C, nedvesség: 18-22 tf%, párolgás: 1,5-2,0 mm/nap.
Péntek (okt. 9.): 9-17 °C | Csapadék: 0 mm | Szél: 3-15 m/s
Megjegyzés: Borult, szeles. Fagyveszély: alacsony (9 °C). Talajhő: ~12-14 °C, nedvesség: 16-20 tf%, párolgás: 1,2-1,6 mm/nap.
Szombat (okt. 10.): 9-14 °C | Csapadék: 3,2 mm | Szél: 6-20 m/s
Megjegyzés: Felhős, csapadékos. Fagyveszély: alacsony (9 °C). Talajhő: ~11-13 °C, nedvesség: 22-26 tf% (eső után), párolgás: 0,8-1,2 mm/nap.

Heves

Szerda (okt. 7.): 14-25 °C | Csapadék: 0 mm | Szél: 2-4 m/s
Megjegyzés: Tiszta. Fagyveszély: nincs. Talajhő: ~15-17 °C, nedvesség: 14-18 tf%, párolgás: 2,0-2,5 mm/nap.
Csütörtök (okt. 8.): 13-23 °C | Csapadék: 0 mm | Szél: 2-6 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 16-20 tf%, párolgás: 1,8-2,2 mm/nap.
Péntek (okt. 9.): 13-19 °C | Csapadék: 0 mm | Szél: 2-5 m/s
Megjegyzés: Elszórt felhők. Fagyveszély: nincs. Talajhő: ~13-15 °C, nedvesség: 16-20 tf%, párolgás: 1,5-2,0 mm/nap.
Szombat (okt. 10.): 10-16 °C | Csapadék: 0 mm | Szél: 2-5 m/s
Megjegyzés: Részben felhős. Fagyveszély: alacsony (10 °C). Talajhő: ~12-14 °C, nedvesség: 14-18 tf%, párolgás: 1,2-1,6 mm/nap.

Kompolt

Szerda (okt. 7.): 14-22 °C | Csapadék: 0 mm | Szél: 2-4 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 14-18 tf%, párolgás: 1,8-2,2 mm/nap.
Csütörtök (okt. 8.): 11-22 °C | Csapadék: 0 mm | Szél: 3-6 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 16-20 tf%, párolgás: 1,6-2,0 mm/nap.
Péntek (okt. 9.): 11-22 °C | Csapadék: 0 mm | Szél: 3-5 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 16-20 tf%, párolgás: 1,5-2,0 mm/nap.
Szombat (okt. 10.): 12-23 °C | Csapadék: 0 mm | Szél: 3-4 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~15-17 °C, nedvesség: 14-18 tf%, párolgás: 1,8-2,2 mm/nap.

Hort

Szerda (okt. 7.): 10-23 °C | Csapadék: 0 mm | Szél: 2-4 m/s
Megjegyzés: Részben felhős. Fagyveszély: alacsony (10 °C). Talajhő: ~13-15 °C, nedvesség: 16-20 tf%, párolgás: 1,8-2,2 mm/nap.
Csütörtök (okt. 8.): 9-18 °C | Csapadék: 0 mm | Szél: 2-5 m/s
Megjegyzés: Felhős. Fagyveszély: alacsony (9 °C). Talajhő: ~12-14 °C, nedvesség: 18-22 tf%, párolgás: 1,2-1,6 mm/nap.
Péntek (okt. 9.): 9-19 °C | Csapadék: 0 mm | Szél: 2-4 m/s
Megjegyzés: Részben felhős. Fagyveszély: alacsony (9 °C). Talajhő: ~12-14 °C, nedvesség: 16-20 tf%, párolgás: 1,2-1,6 mm/nap.
Szombat (okt. 10.): 7-17 °C | Csapadék: 0 mm | Szél: 2-3 m/s
Megjegyzés: Részben felhős. Fagyveszély: mérsékelt (hajnalban 7 °C, talajmenti fagy lehetséges). Talajhő: ~11-13 °C, nedvesség: 14-18 tf%, párolgás: 1,0-1,4 mm/nap.

Gyöngyös

Szerda (okt. 7.): 12-23 °C | Csapadék: 0 mm | Szél: 2-5 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 14-18 tf%, párolgás: 1,8-2,2 mm/nap.
Csütörtök (okt. 8.): 14-23 °C | Csapadék: 0 mm | Szél: 3-6 m/s
Megjegyzés: Részben felhős. Fagyveszély: nincs. Talajhő: ~14-16 °C, nedvesség: 16-20 tf%, párolgás: 1,6-2,0 mm/nap.
Péntek (okt. 9.): 13-21 °C | Csapadék: 2,7 mm | Szél: 3-7 m/s
Megjegyzés: Csapadékos. Fagyveszély: nincs. Talajhő: ~13-15 °C, nedvesség: 20-24 tf%, párolgás: 1,0-1,4 mm/nap.
Szombat (okt. 10.): 13-19 °C | Csapadék: 2,7 mm | Szél: 3-6 m/s
Megjegyzés: Csapadékos. Fagyveszély: nincs. Talajhő: ~13-15 °C, nedvesség: 22-26 tf%, párolgás: 0,8-1,2 mm/nap.

3. Rövid összegzés

Október 6-án mérsékelt fagyveszély: Szarvasgede, Pásztó.
Alacsony-mérsékelt fagyveszély: Heves, Kompolt.
Alacsony fagyveszély: Hort, Gyöngyös.
Csapadék ma: Több térségben 3-5 mm várható délután/este.
Szerda: Enyhülés, többnyire csapadék nélkül.
Csütörtök-Péntek: Változó felhőzet, kisebb eső csak helyenként.
Szombat: Ismét több helyen talajmenti fagy lehet, főleg Szarvasgede és Hort térségében.