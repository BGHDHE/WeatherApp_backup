<script lang="ts">
  import { onMount } from "svelte";
  import { fetchDaily } from "$lib/api";
  import type { DailyResponse, LocationDaily } from "$lib/types";

  let report: DailyResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");

  const dateFormatter = new Intl.DateTimeFormat("hu-HU", {
    year: "numeric", month: "long", day: "numeric", weekday: "long",
  });
  const updatedFormatter = new Intl.DateTimeFormat("hu-HU", { dateStyle: "short", timeStyle: "short" });

  onMount(() => {
    void load();
  });

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

  const frostClass = (level: string) =>
    ({ magas: "frost-high", mérsékelt: "frost-medium", alacsony: "frost-low", nincs: "frost-none" })[level] ?? "frost-unknown";

  function frost(l: LocationDaily): string {
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

    {#if loading}
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
        <span class="source-pill"><span aria-hidden="true">●</span> Modelladat</span>
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
                  <div><dt>Modellezett hőmérséklet (24 h)</dt><dd>{range(l.past_temp_min_c, l.past_temp_max_c)}</dd></div>
                  <div><dt>Várható hőmérséklet ma</dt><dd>{range(l.today_temp_min_c, l.today_temp_max_c)}</dd></div>
                  <div><dt>Csapadék, modellezett (24 h)</dt><dd>{num(l.past_precip_mm, "mm")}</dd></div>
                  <div><dt>Csapadék, várható ma</dt><dd>{rain(l)}</dd></div>
                  <div><dt>Szél</dt><dd>{wind(l)}</dd></div>
                  <div class="frost-line"><dt>Fagyveszély</dt><dd class={frostClass(l.frost_level)}>{frost(l)}</dd></div>
                  <div><dt>Talajhőmérséklet (6 cm)</dt><dd>{num(l.soil_temperature_c, "°C", 0)}</dd></div>
                  <div><dt>Talajnedvesség</dt><dd>{num(l.soil_moisture_percent, "%", 0)}</dd></div>
                  <div><dt>Párolgás</dt><dd>{num(l.evapotranspiration_mm, "mm/nap")}</dd></div>
                </dl>
              </article>
            {/each}
          </div>
        </section>
      {/each}
    {/if}
  </main>

  <footer>
    Modelladat, nem helyi állomásmérés: az „elmúlt 24 óra” modellezett érték, nem mért. A felszíni
    minimum nem érhető el ebből a forrásból. A talajnedvesség az Open-Meteo 0–7 cm-es rétegének
    térfogatszázaléka. A fagyjelzés általános tájékoztatás.
  </footer>
</div>