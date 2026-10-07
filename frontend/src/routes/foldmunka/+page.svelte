<script lang="ts">
  import { onMount } from "svelte";
  import { fetchFieldwork } from "$lib/api";
  import type { FieldworkDay, FieldworkResponse } from "$lib/types";

  let report: FieldworkResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");

  const weekday = new Intl.DateTimeFormat("hu-HU", { weekday: "short" });
  const dayMonth = new Intl.DateTimeFormat("hu-HU", { month: "numeric", day: "numeric" });
  const updatedFormatter = new Intl.DateTimeFormat("hu-HU", { dateStyle: "short", timeStyle: "short" });
  const localDate = (iso: string) => new Date(`${iso}T12:00:00`);

  onMount(() => {
    void load();
  });

  async function load() {
    loading = true;
    error = "";
    try {
      report = await fetchFieldwork();
    } catch {
      error = "A földmunka-elemzés most nem érhető el. Próbáld újra később.";
    } finally {
      loading = false;
    }
  }

  const NA = "–";
  const n = (v: number | null, unit = "", digits = 1) =>
    v === null ? NA : `${v.toLocaleString("hu-HU", { maximumFractionDigits: digits })}${unit ? " " + unit : ""}`;
  const statusClass = (s: string) =>
    ({ kedvező: "window-ok", feltételes: "window-warn", kedvezőtlen: "window-bad" })[s] ?? "window-na";
  const label = (a: string) => a[0].toUpperCase() + a.slice(1);

  function tip(day: FieldworkDay, activity: string): string {
    const a = day.assessments.find((x) => x.activity === activity);
    return a ? `${a.status} – ${a.reason}\nKüszöb: ${a.threshold}` : "";
  }
  type Tip = { x: number; y: number; status: string; reason: string; threshold: string; cls: string };
  let tipState: Tip | null = $state(null);

  function showTip(event: Event, day: FieldworkDay, activity: string) {
    const a = day.assessments.find((x) => x.activity === activity);
    if (!a) return;
    const r = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const half = 150;
    const x = Math.min(Math.max(r.left + r.width / 2, half + 8), window.innerWidth - half - 8);
    tipState = { x, y: r.bottom + 8, status: a.status, reason: a.reason, threshold: a.threshold, cls: statusClass(a.status) };
  }
  const hideTip = () => (tipState = null);
  const status = (day: FieldworkDay, activity: string) =>
    day.assessments.find((x) => x.activity === activity)?.status ?? "nincs adat";
  const activities = ["talajművelés", "vetés", "permetezés", "betakarítás"] as const;
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
      <a href="/napi">Napi kimutatás</a>
      <a href="/">Előrejelzés</a>
      <a href="/foldmunka" aria-current="page">Földmunka</a>
      <a href="/kuszobok">Küszöbök</a>
    </nav>
  </header>

  <main>
    <section class="intro" aria-labelledby="page-title">
      <h1 id="page-title">Munkaműveletek időjárási ablakai</h1>
    </section>

    {#if loading}
      <p class="status-panel" role="status">Földmunka-elemzés betöltése…</p>
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
        <span class="source-pill"><span aria-hidden="true">●</span> Modell-előrejelzés</span>
        <span>Forrás: Open-Meteo</span>
        <span>Frissítve: {updatedFormatter.format(new Date(report.fetched_at))}</span>
      </div>


      {#each report.regions as region (region.slug)}
        <section class="daily-region" aria-labelledby="fw-{region.slug}">
          <h2 id="fw-{region.slug}" class="daily-region-title">{region.name}</h2>
          <p class="region-summary">{region.summary}</p>

          <div class="daily-grid">
            {#each region.locations as loc (loc.slug)}
              <article class="daily-card fw-card">
                <h3>{loc.name}</h3>
                <p class="fw-summary">{loc.summary}</p>
                <p class="fw-week">Heti csapadék: <strong>{n(loc.precipitation_week_mm, "mm")}</strong></p>

                <div class="fw-scroll">
                  <table class="fw-table">
                    <thead>
                      <tr>
                        <th scope="col">Nap</th>
                        {#each loc.days as day (day.date)}
                          <th scope="col">{weekday.format(localDate(day.date))}<br /><small>{dayMonth.format(localDate(day.date))}</small></th>
                        {/each}
                      </tr>
                    </thead>
                    <tbody>
                      {#each activities as activity}
                        <tr>
                          <th scope="row">{label(activity)}</th>
                          {#each loc.days as day (day.date)}
                            <td><button type="button" class="window-dot dot-btn {statusClass(status(day, activity))}" aria-label={tip(day, activity).replace("\n", ". ")} onmouseenter={(e) => showTip(e, day, activity)} onmouseleave={hideTip} onfocus={(e) => showTip(e, day, activity)} onblur={hideTip}>{status(day, activity) === "kedvező" ? "✓" : status(day, activity) === "kedvezőtlen" ? "✕" : status(day, activity) === "feltételes" ? "~" : "?"}</button></td>
                          {/each}
                        </tr>
                      {/each}
                      <tr><th scope="row">Csapadék (mm)</th>{#each loc.days as day (day.date)}<td>{n(day.precipitation_mm)}</td>{/each}</tr>
                      <tr><th scope="row">Előző 3 nap (mm)</th>{#each loc.days as day (day.date)}<td>{n(day.precipitation_prev_3d_mm)}</td>{/each}</tr>
                      <tr><th scope="row">Felső réteg (%)</th>{#each loc.days as day (day.date)}<td>{n(day.topsoil_moisture_percent, "", 0)}</td>{/each}</tr>
                      <tr><th scope="row">Alsó réteg (%)</th>{#each loc.days as day (day.date)}<td>{n(day.subsoil_moisture_percent, "", 0)}</td>{/each}</tr>
                      <tr><th scope="row">Talaj (°C)</th>{#each loc.days as day (day.date)}<td>{n(day.soil_temperature_c, "", 0)}</td>{/each}</tr>
                      <tr><th scope="row">Min / max (°C)</th>{#each loc.days as day (day.date)}<td>{n(day.temp_min_c, "", 0)} / {n(day.temp_max_c, "", 0)}</td>{/each}</tr>
                    </tbody>
                  </table>
                </div>
              </article>
            {/each}
          </div>
        </section>
      {/each}
    {/if}
  </main>

  {#if tipState}
    <div class="tip" style="left: {tipState.x}px; top: {tipState.y}px" aria-hidden="true">
      <div class="tip-status {tipState.cls}">{tipState.status}</div>
      <p class="tip-reason">{tipState.reason}</p>
      <p class="tip-threshold"><span>Küszöb</span> {tipState.threshold}</p>
    </div>
  {/if}
</div>