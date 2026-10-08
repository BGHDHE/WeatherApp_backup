<script lang="ts">
  import { onMount } from "svelte";
  import { fetchDaily, fetchObservations } from "$lib/api";
  import type {
    DailyResponse,
    LocationDaily,
    LocationObservation,
    ObservationResponse,
  } from "$lib/types";

  let report: DailyResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");
  let view: "model" | "measured" = $state("measured");
  let observed: ObservationResponse | null = $state(null);
  let obsLoading = $state(false);
  let obsError = $state("");

  const dateFormatter = new Intl.DateTimeFormat("hu-HU", {
    year: "numeric", month: "long", day: "numeric", weekday: "long",
  });
  const updatedFormatter = new Intl.DateTimeFormat("hu-HU", { dateStyle: "short", timeStyle: "short" });

  const REFRESH_MS = 5 * 60 * 1000;

  onMount(() => {
    void loadObserved();
    void load();
    const timer = setInterval(() => {
      if (view === "measured") void loadObserved(true);
    }, REFRESH_MS);
    return () => clearInterval(timer);
  });

  async function loadObserved(quiet = false) {
    if (!quiet) obsLoading = true;
    obsError = "";
    try {
      observed = await fetchObservations();
    } catch {
      if (!quiet || !observed) obsError = "A mért állomásadatok most nem érhetők el. Próbáld újra később.";
    } finally {
      obsLoading = false;
    }
  }

  function select(next: "model" | "measured") {
    view = next;
    if (next === "measured") void loadObserved(observed !== null);
  }

  async function load() {
    loading = true;
    error = "";
    try {
      report = await fetchDaily();
    } catch {
      error = "A napi jelentés most nem érhető el. Próbáld újra később.";
    } finally {
      loading = false;
    }
  }

  const NA = "nincs adat";
  const num = (v: number | null, unit: string, digits = 1) =>
    v === null ? NA : `${v.toLocaleString("hu-HU", { maximumFractionDigits: digits })} ${unit}`;
  const range = (a: number | null, b: number | null) =>
    a === null || b === null ? NA : `${a.toLocaleString("hu-HU")} – ${b.toLocaleString("hu-HU")} °C`;

  function rain(l: LocationDaily): string {
    if (l.precip_today_mm === null) return NA;
    if (l.precip_window === null) return `${num(l.precip_today_mm, "mm")}`;
    const prob = l.precip_probability_max === null ? "" : `, ${l.precip_probability_max}%`;
    return `${num(l.precip_today_mm, "mm")} (${l.precip_window}${prob})`;
  }

  function wind(l: LocationDaily): string {
    if (l.wind_max_ms === null) return NA;
    const dir = l.wind_direction ? `${l.wind_direction} ` : "";
    const gust = l.gust_max_ms === null ? "" : ` (széllökés: ${num(l.gust_max_ms, "m/s")}${l.gust_time ? `, ${l.gust_time}` : ""})`;
    return `${dir}${num(l.wind_max_ms, "m/s")}${gust}`;
  }

  function getModelLocation(slug: string): LocationDaily | null {
    if (!report) return null;
    for (const region of report.regions) {
      const loc = region.locations.find((l) => l.slug === slug);
      if (loc) return loc;
    }
    return null;
  }

  const combinedLocationGroups = [
    { name: "Hort–Gyöngyös", slugs: ["hort", "gyongyos"] },
    { name: "Kál–Kompolt", slugs: ["kal", "kompolt"] },
  ];

  function displayRegions<
    TLocation extends { name: string; slug: string },
    TRegion extends { name: string; slug: string; locations: TLocation[] },
  >(regions: TRegion[]): TRegion[] {
    const hortRegion = regions.find((region) => region.slug === "hort-gyongyos");
    const kalRegion = regions.find((region) => region.slug === "kal-kompolt-heves");
    if (!hortRegion || !kalRegion) return regions;

    return regions
      .filter((region) => region.slug !== hortRegion.slug)
      .map((region) =>
        region.slug === kalRegion.slug
          ? {
              ...region,
              name: "Kál–Heves–Gyöngyös",
              locations: [...region.locations, ...hortRegion.locations],
            }
          : region,
      );
  }

  function groupLocations<T extends { name: string; slug: string }>(
    locations: T[],
  ): { key: string; name: string; locations: T[] }[] {
    const bySlug = new Map(locations.map((location) => [location.slug, location]));
    const grouped = new Set<string>();
    const result: { key: string; name: string; locations: T[] }[] = [];

    for (const location of locations) {
      if (grouped.has(location.slug)) continue;
      const pair = combinedLocationGroups.find((candidate) =>
        candidate.slugs.includes(location.slug) && candidate.slugs.every((slug) => bySlug.has(slug)),
      );
      if (!pair) {
        result.push({ key: location.slug, name: location.name, locations: [location] });
        continue;
      }

      const members = pair.slugs.map((slug) => bySlug.get(slug)).filter((item): item is T => item !== undefined);
      members.forEach((item) => grouped.add(item.slug));
      result.push({ key: pair.slugs.join("-"), name: pair.name, locations: members });
    }
    return result;
  }

  function average(values: (number | null)[]): number | null {
    const known = values.filter((value): value is number => value !== null);
    return known.length === 0 ? null : known.reduce((sum, value) => sum + value, 0) / known.length;
  }

  function lowest(values: (number | null)[]): number | null {
    const known = values.filter((value): value is number => value !== null);
    return known.length === 0 ? null : Math.min(...known);
  }

  function highest(values: (number | null)[]): number | null {
    const known = values.filter((value): value is number => value !== null);
    return known.length === 0 ? null : Math.max(...known);
  }

  const frostRanks = { "nincs adat": 0, nincs: 1, alacsony: 2, mérsékelt: 3, magas: 4 };

  function combinedFrost<T extends { frost_level: keyof typeof frostRanks }>(locations: T[]): T["frost_level"] {
    return locations.reduce(
      (highestRisk, location) =>
        frostRanks[location.frost_level] > frostRanks[highestRisk] ? location.frost_level : highestRisk,
      locations[0].frost_level,
    );
  }

  function mergeDaily(locations: LocationDaily[]): LocationDaily {
    const windiest = locations.reduce((current, location) =>
      (location.wind_max_ms ?? -Infinity) > (current.wind_max_ms ?? -Infinity) ? location : current,
    );
    const gustiest = locations.reduce((current, location) =>
      (location.gust_max_ms ?? -Infinity) > (current.gust_max_ms ?? -Infinity) ? location : current,
    );
    const first = locations[0];
    const windows = [...new Set(locations.map((location) => location.precip_window).filter(Boolean))];
    const precipitationProbability = average(locations.map((location) => location.precip_probability_max));
    return {
      ...first,
      past_temp_min_c: lowest(locations.map((location) => location.past_temp_min_c)),
      past_temp_max_c: highest(locations.map((location) => location.past_temp_max_c)),
      past_precip_mm: average(locations.map((location) => location.past_precip_mm)),
      past_gust_max_ms: highest(locations.map((location) => location.past_gust_max_ms)),
      today_temp_min_c: lowest(locations.map((location) => location.today_temp_min_c)),
      today_temp_max_c: highest(locations.map((location) => location.today_temp_max_c)),
      precip_today_mm: average(locations.map((location) => location.precip_today_mm)),
      precip_window: windows.length === 1 ? windows[0] : null,
      precip_probability_max: precipitationProbability === null ? null : Math.round(precipitationProbability),
      wind_max_ms: average(locations.map((location) => location.wind_max_ms)),
      wind_direction: windiest.wind_direction,
      gust_max_ms: highest(locations.map((location) => location.gust_max_ms)),
      gust_time: gustiest.gust_time,
      frost_level: combinedFrost(locations),
      frost_min_temp_c: lowest(locations.map((location) => location.frost_min_temp_c)),
      soil_temperature_c: average(locations.map((location) => location.soil_temperature_c)),
      soil_moisture_percent: average(locations.map((location) => location.soil_moisture_percent)),
      evapotranspiration_mm: average(locations.map((location) => location.evapotranspiration_mm)),
    };
  }

  function mergeObservations(locations: LocationObservation[]): LocationObservation {
    const windiest = locations.reduce((current, location) =>
      (location.wind_max_ms ?? -Infinity) > (current.wind_max_ms ?? -Infinity) ? location : current,
    );
    const allStations = locations.flatMap((location) => location.stations ?? []);
    const stations = [...new Map(allStations.map((station) => [station.name, station])).values()];
    return {
      ...locations[0],
      method: locations.every((location) => location.method === "nincs adat")
        ? "nincs adat"
        : locations.some((location) => location.method === "interpoláció")
          ? "interpoláció"
          : "legközelebbi állomás",
      stations,
      wind_stations: [
        ...new Map(
          locations
            .flatMap((location) => location.wind_stations ?? [])
            .map((station) => [station.name, station]),
        ).values(),
      ],
      latest_time: highestTime(locations.map((location) => location.latest_time)),
      latest_temp_c: average(locations.map((location) => location.latest_temp_c)),
      latest_humidity_percent: average(locations.map((location) => location.latest_humidity_percent)),
      latest_wind_ms: average(locations.map((location) => location.latest_wind_ms)),
      past_temp_min_c: lowest(locations.map((location) => location.past_temp_min_c)),
      past_temp_max_c: highest(locations.map((location) => location.past_temp_max_c)),
      past_precip_mm: average(locations.map((location) => location.past_precip_mm)),
      past_gust_max_ms: highest(locations.map((location) => location.past_gust_max_ms)),
      today_temp_min_c: lowest(locations.map((location) => location.today_temp_min_c)),
      today_temp_max_c: highest(locations.map((location) => location.today_temp_max_c)),
      precip_today_mm: average(locations.map((location) => location.precip_today_mm)),
      wind_max_ms: average(locations.map((location) => location.wind_max_ms)),
      wind_direction: windiest.wind_direction,
      gust_max_ms: highest(locations.map((location) => location.gust_max_ms)),
      gust_time: locations.reduce((current, location) =>
        (location.gust_max_ms ?? -Infinity) > (current.gust_max_ms ?? -Infinity) ? location : current,
      ).gust_time,
      frost_level: combinedFrost(locations),
      frost_min_temp_c: lowest(locations.map((location) => location.frost_min_temp_c)),
    };
  }

  function highestTime(values: (string | null)[]): string | null {
    return values.filter((value): value is string => value !== null).sort().at(-1) ?? null;
  }

  function modelLocationsFor(group: LocationObservation[]): LocationDaily[] {
    return group
      .map((location) => getModelLocation(location.slug))
      .filter((location): location is LocationDaily => location !== null);
  }

  const timeFormatter = new Intl.DateTimeFormat("hu-HU", { hour: "2-digit", minute: "2-digit" });

  function latest(l: LocationObservation): string {
    if (l.latest_temp_c === null) return NA;
    const humidity = l.latest_humidity_percent === null ? "" : `, páratartalom ${num(l.latest_humidity_percent, "%", 0)}`;
    return `${num(l.latest_temp_c, "°C")}${humidity}`;
  }

  const stationList = (l: LocationObservation) =>
    l.stations.map((s) => `${s.name} (${s.distance_km.toLocaleString("hu-HU")} km)`).join(", ");

  const frostClass = (level: string) =>
    ({ magas: "frost-high", mérsékelt: "frost-medium", alacsony: "frost-low", nincs: "frost-none" })[level] ?? "frost-unknown";

  function frost(l: LocationDaily | LocationObservation): string {
    if (l.frost_level === "nincs adat") return "Nincs adat";
    const temp = l.frost_min_temp_c === null ? "" : ` (minimum ${num(l.frost_min_temp_c, "°C")})`;
    return `${l.frost_level[0].toUpperCase()}${l.frost_level.slice(1)}${temp}`;
  }
</script>

<svelte:head>
  <title>Angelika Farm Időjárás</title>
</svelte:head>

<div class="app-shell">
  <header class="topbar">
    <a class="brand" href="/" aria-label="Időjárás főoldal">
      <span class="brand-mark" aria-hidden="true">A</span>
      <span>Angelika Farm Időjárás<span class="brand-dot">.</span></span>
    </a>
    <nav class="topnav" aria-label="Főmenü">
      <a href="/napi" aria-current="page">Napi kimutatás</a>
      <a href="/">Előrejelzés</a>
      <a href="/foldmunka">Földmunka</a>
      <a href="/kuszobok">Küszöbök</a>
    </nav>
  </header>

  <main>
    <section class="intro" aria-labelledby="page-title">
      <h1 id="page-title">{report ? dateFormatter.format(new Date(`${report.date}T12:00:00`)) : "Mai jelentés"}</h1>
    </section>

    <div class="view-switch" role="tablist" aria-label="Adatforrás">
      <button role="tab" aria-selected={view === "measured"} class:active={view === "measured"} onclick={() => select("measured")}>Állomásadat</button>
      <button role="tab" aria-selected={view === "model"} class:active={view === "model"} onclick={() => select("model")}>Modelladat</button>
    </div>

    {#if view === "measured"}
      {#if obsLoading}
        <p class="status-panel" role="status">Állomásadatok betöltése…</p>
      {:else if obsError}
        <div class="error-panel" role="alert">
          <span>{obsError}</span>
          <button class="retry-button" onclick={() => loadObserved()}>Újrapróbálom</button>
        </div>
      {:else if observed}
        {#if observed.stale}
          <p class="stale-note" role="status">A forrás most nem érhető el, az utoljára mentett adatokat látod.</p>
        {/if}
        <div class="provenance">
          <span>Forrás: HungaroMet ODP</span>
          {#if observed.as_of}<span>Legfrissebb mérés: {timeFormatter.format(new Date(observed.as_of))}</span>{/if}
        </div>

        {#each displayRegions(observed.regions) as region (region.slug)}
          <section class="daily-region" aria-labelledby="o-{region.slug}">
            <h2 id="o-{region.slug}" class="daily-region-title">{region.name}</h2>
            <div class="daily-grid">
              {#each groupLocations(region.locations) as group (group.key)}
                {@const l = mergeObservations(group.locations)}
                {@const modelLocations = modelLocationsFor(group.locations)}
                <article class="daily-card">
                  <h3>{group.name}</h3>
                  {#if l.method === "nincs adat"}
                    <p class="fw-week">Nincs elég közeli (20 km-en belüli) mérőállomás.</p>
                  {:else}
                    <p class="station-note">
                      {l.method === "interpoláció" ? "Interpolált érték" : "Legközelebbi állomás"}: {stationList(l)}
                    </p>
                    <dl>
                      <div class="frost-line"><dt>Legfrissebb mérés</dt><dd>{latest(l)}</dd></div>
                      <div class="frost-line"><dt>Hőmérséklet, mért (24 h)</dt><dd>{range(l.past_temp_min_c, l.past_temp_max_c)}</dd></div>
                      <div class="frost-line"><dt>Hőmérséklet ma</dt><dd>{range(l.today_temp_min_c, l.today_temp_max_c)}</dd></div>
                      <div class="frost-line"><dt>Csapadék, mért (24 h)</dt><dd>{num(l.past_precip_mm, "mm")}</dd></div>
                      <div class="frost-line"><dt>Csapadék ma</dt><dd>{num(l.precip_today_mm, "mm")}</dd></div>
                      <div class="frost-line"><dt>Szél</dt><dd>{modelLocations.length ? wind(mergeDaily(modelLocations)) : NA}</dd></div>
                      <div class="frost-line"><dt>Fagy</dt><dd class={frostClass(l.frost_level)}>{frost(l)}</dd></div>
                    </dl>
                  {/if}
                </article>
              {/each}
            </div>
          </section>
        {/each}
      {/if}
    {:else if loading}
      <p class="status-panel" role="status">Napi jelentés betöltése…</p>
    {:else if error}
      <div class="error-panel" role="alert">
        <span>{error}</span>
        <button class="retry-button" onclick={load}>Újrapróbálom</button>
      </div>
    {:else if report}
      {#if report.stale}
        <p class="stale-note" role="status">A forrás most nem érhető el, az utoljára mentett adatokat látod.</p>
      {/if}
      <div class="provenance">
        <span>Forrás: Open-Meteo</span>
        <span>Frissítve: {updatedFormatter.format(new Date(report.fetched_at))}</span>
      </div>

      {#each displayRegions(report.regions) as region (region.slug)}
        <section class="daily-region" aria-labelledby="r-{region.slug}">
          <h2 id="r-{region.slug}" class="daily-region-title">{region.name}</h2>
          <div class="daily-grid">
            {#each groupLocations(region.locations) as group (group.key)}
              {@const l = mergeDaily(group.locations)}
              <article class="daily-card">
                <h3>{group.name}</h3>
                <dl>
                  <div class="frost-line"><dt>Modellezett hőmérséklet (24 h)</dt><dd>{range(l.past_temp_min_c, l.past_temp_max_c)}</dd></div>
                  <div class="frost-line"><dt>Várható hőmérséklet ma</dt><dd>{range(l.today_temp_min_c, l.today_temp_max_c)}</dd></div>
                  <div class="frost-line"><dt>Csapadék, modellezett (24 h)</dt><dd>{num(l.past_precip_mm, "mm")}</dd></div>
                  <div class="frost-line"><dt>Csapadék, várható ma</dt><dd>{rain(l)}</dd></div>
                  <div class="frost-line"><dt>Szél</dt><dd>{wind(l)}</dd></div>
                  <div class="frost-line"><dt>Fagyveszély</dt><dd class={frostClass(l.frost_level)}>{frost(l)}</dd></div>
                  <div class="frost-line"><dt>Talajhőmérséklet (6 cm)</dt><dd>{num(l.soil_temperature_c, "°C", 0)}</dd></div>
                  <div class="frost-line"><dt>Talajnedvesség</dt><dd>{num(l.soil_moisture_percent, "%", 0)}</dd></div>
                  <div class="frost-line"><dt>Párolgás</dt><dd>{num(l.evapotranspiration_mm, "mm/nap")}</dd></div>
                </dl>
              </article>
            {/each}
          </div>
        </section>
      {/each}
    {/if}
  </main>
</div>