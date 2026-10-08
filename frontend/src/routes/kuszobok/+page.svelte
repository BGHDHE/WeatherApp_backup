<script lang="ts">
  import { onMount } from "svelte";
  import { fetchThresholds } from "$lib/api";
  import { ACTIVITY_OPTIONS, loadSelection, saveSelection } from "$lib/fieldworkSettings";
  import type { ThresholdItem, ThresholdsResponse } from "$lib/types";

  let selected: string[] = $state([]);

  function toggle(key: string, checked: boolean) {
    selected = checked ? [...selected, key] : selected.filter((k) => k !== key);
    saveSelection(selected);
  }

  let data: ThresholdsResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");

  onMount(() => {
    selected = loadSelection();
    void load();
  });

  async function load() {
    loading = true;
    error = "";
    try {
      data = await fetchThresholds();
    } catch {
      error = "A küszöbértékek jelenleg nem érhetők el. Kérjük, próbáld újra később.";
    } finally {
      loading = false;
    }
  }

  const num = (v: number) => v.toLocaleString("hu-HU", { maximumFractionDigits: 2 });

  let groups = $derived.by(() => {
    const map = new Map<string, ThresholdItem[]>();
    for (const t of data?.thresholds ?? []) {
      map.set(t.group, [...(map.get(t.group) ?? []), t]);
    }
    return [...map.entries()];
  });
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
      <a href="/napi">Napi kimutatás</a>
      <a href="/">Előrejelzés</a>
      <a href="/foldmunka">Földmunka</a>
      <a href="/kuszobok" aria-current="page">Beállítások</a>
    </nav>
  </header>

  <main>
    <section class="daily-region" aria-labelledby="fw-settings">
      <h2 id="fw-settings" class="daily-region-title">Földmunka összefoglaló</h2>
      <p class="region-summary">Válaszd ki, mely munkákról készüljön szöveges összefoglaló a Földmunka oldalon.</p>
      <div class="fw-options">
        {#each ACTIVITY_OPTIONS as o (o.key)}
          <label class="fw-option">
            <input type="checkbox" checked={selected.includes(o.key)} onchange={(e) => toggle(o.key, e.currentTarget.checked)} />
            {o.label}
          </label>
        {/each}
      </div>
    </section>

    <section class="intro" aria-labelledby="page-subtitle">
      <h2 id="page-subtitle">Küszöbértékek</h2>
    </section>

    {#if loading}
      <p class="status-panel" role="status">Küszöbértékek betöltése…</p>
    {:else if error}
      <div class="error-panel" role="alert">
        <span>{error}</span>
        <button class="retry-button" onclick={load}>Újrapróbálás</button>
      </div>
    {:else if data}

      {#each groups as [group, items] (group)}
        <section class="daily-region" aria-labelledby="g-{group}">
          <h2 id="g-{group}" class="daily-region-title">{group}</h2>
          <div class="fw-scroll">
            <table class="fw-table kuszob-table">
              <thead>
                <tr>
                  <th scope="col" class="col-label">Küszöb</th>
                  <th scope="col" class="col-value">Érték</th>
                  <th scope="col" class="col-desc">Mit jelent</th>
                </tr>
              </thead>
              <tbody>
                {#each items as t (t.key)}
                  <tr>
                    <th scope="row" class="col-label">{t.label}</th>
                    <td class="col-value"><strong>{num(t.value)} {t.unit}</strong></td>
                    <td class="col-desc kuszob-desc">{t.description}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>
      {/each}
    {/if}
  </main>
</div>

<style>
  .fw-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
    margin-top: 8px;
  }

  .fw-option {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .kuszob-table {
    width: 100%;
    table-layout: fixed;
    border-collapse: collapse;
  }

  .kuszob-table th,
  .kuszob-table td {
    text-align: left !important;
    padding-left: 0;
  }

  .col-label {
    width: 30%;
  }

  .col-value {
    width: 10%;
  }

  .col-desc {
    width: 50%;
  }
</style>