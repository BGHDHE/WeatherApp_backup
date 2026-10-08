<script lang="ts">
  import { onMount } from "svelte";
  import { fetchOutlook } from "$lib/api";
  import type { OutlookDay, OutlookResponse } from "$lib/types";

  let outlook: OutlookResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");

  const weekday = new Intl.DateTimeFormat("hu-HU", { weekday: "short" });
  const dayMonth = new Intl.DateTimeFormat("hu-HU", { month: "numeric", day: "numeric" });
  const updatedFormatter = new Intl.DateTimeFormat("hu-HU", {
    dateStyle: "short",
    timeStyle: "short",
  });

  onMount(() => {
    void load();
  });

  async function load() {
    loading = true;
    error = "";
    try {
      outlook = await fetchOutlook(7);
    } catch {
      error = "Az előretekintés most nem érhető el. Próbáld újra később.";
    } finally {
      loading = false;
    }
  }

  const localDate = (iso: string) => new Date(`${iso}T12:00:00`);

  function temp(value: number | null): string {
    return value === null ? "–" : `${Math.round(value)}°`;
  }

  function rain(day: OutlookDay): string {
    if (day.precipitation_max_mm === null) return "Nincs adat";
    return day.precipitation_max_mm < 0.5 ? "száraz" : `${Math.round(day.precipitation_max_mm)} mm`;
  }

  function gust(day: OutlookDay): string {
    return day.wind_gust_max_ms === null ? "–" : `${Math.round(day.wind_gust_max_ms)} m/s`;
  }

  const conditionSymbol: Record<string, string> = {
    száraz: "☀",
    csapadék: "☂",
    zivatar: "⚡",
    "nincs adat": "?",
  };
</script>

<svelte:head>
  <title>Angelika Farm Időjárás</title>
  <meta name="description" content="7 napos időjárási előretekintés művelési térségenként." />
</svelte:head>

<div class="app-shell">
  <header class="topbar">
    <a class="brand" href="/" aria-label="Időjárás főoldal">
      <span class="brand-mark" aria-hidden="true">A</span>
      <span>Angelika Farm Időjárás<span class="brand-dot">.</span></span>
    </a>
    <nav class="topnav" aria-label="Főmenü">
      <a href="/napi">Napi Kimutatás</a>
      <a href="/" aria-current="page">Előrejelzés</a>
      <a href="/foldmunka">Földmunka</a>
      <a href="/kuszobok">Küszöbök</a>
    </nav>
  </header>

  <main>
    <section class="intro" aria-labelledby="page-title">
      <h1 id="page-title">Mire számíthatunk a héten?</h1>
    </section>

    {#if loading}
      <p class="status-panel" role="status">Előretekintés betöltése…</p>
    {:else if error}
      <div class="error-panel" role="alert">
        <span>{error}</span>
        <button class="retry-button" onclick={load}>Újrapróbálom</button>
      </div>
    {:else if outlook}
      {#if outlook.stale}
        <p class="stale-note" role="status">A forrás most nem érhető el, az utoljára mentett adatokat látod.</p>
      {/if}
      <div class="provenance">
        <span class="source-pill"><span aria-hidden="true">●</span> Modell-előrejelzés</span>
        <span>Forrás: Open-Meteo</span>
        <span>Frissítve: {updatedFormatter.format(new Date(outlook.fetched_at))}</span>
      </div>

      <div class="region-list">
        {#each outlook.regions as region (region.slug)}
          <section class="region-card" aria-labelledby="region-{region.slug}">
            <div class="region-head">
              <h2 id="region-{region.slug}">{region.name}</h2>
            </div>
            <p class="region-summary">{region.summary}</p>

            {#if region.alerts.length > 0}
              <ul class="alert-list" aria-label="Kirívó események">
                {#each region.alerts as alert (alert.date + alert.kind)}
                  <li class="alert alert-{alert.kind}">
                    <span class="alert-icon" aria-hidden="true">⚠</span>
                    <span>{alert.message}</span>
                  </li>
                {/each}
              </ul>
            {/if}

            <div class="week-strip" role="list">
              {#each region.days as day (day.date)}
                <div class="week-day" class:wet={day.condition !== "száraz"} role="listitem">
                  <span class="week-name">{weekday.format(localDate(day.date))}</span>
                  <span class="week-date">{dayMonth.format(localDate(day.date))}</span>
                  <span class="week-symbol" aria-label={day.condition}>{conditionSymbol[day.condition]}</span>
                  <strong>{temp(day.temp_max_c)}</strong>
                  <span class="week-min">{temp(day.temp_min_c)}</span>
                  <span class="week-rain">{rain(day)}</span>
                  <span class="week-wind" aria-label={`Maximális széllökés: ${gust(day)}`}>Széllökés {gust(day)}</span>
                </div>
              {/each}
            </div>          </section>
        {/each}
      </div>
    {/if}
  </main>
</div>