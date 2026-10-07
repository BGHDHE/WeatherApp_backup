<script lang="ts">
  import { onMount } from "svelte";
  import { fetchDaily, fetchObservations } from "$lib/api";
  import type { DailyResponse, LocationDaily, LocationObservation, ObservationResponse } from "$lib/types";

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
  <title>Angelika Farm AgroSense</title>
</svelte:head>

<div class="app-shell">
  <header class="topbar">
    <a class="brand" href="/" aria-label="AgroSense főoldal">
      <span class="brand-mark" aria-hidden="true">A</span>
      <span>Angelika Farm AgroSense<span class="brand-dot">.</span></span>
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
      <button role="tab" aria-selected={view === "measured"} class:active={view === "measured"} onclick={() => select("measured")}>Mért állomásadat</button>
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

        {#each observed.regions as region (region.slug)}
          <section class="daily-region" aria-labelledby="o-{region.slug}">
            <h2 id="o-{region.slug}" class="daily-region-title">{region.name}</h2>
            <div class="daily-grid">
              {#each region.locations as l (l.slug)}
                {@const modelLoc = getModelLocation(l.slug)}
                <article class="daily-card">
                  <h3>{l.name}</h3>
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
                      <div class="frost-line"><dt>Szél</dt><dd>{modelLoc ? wind(modelLoc) : NA}</dd></div>
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

      {#each report.regions as region (region.slug)}
        <section class="daily-region" aria-labelledby="r-{region.slug}">
          <h2 id="r-{region.slug}" class="daily-region-title">{region.name}</h2>
          <div class="daily-grid">
            {#each region.locations as l (l.slug)}
              <article class="daily-card">
                <h3>{l.name}</h3>
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