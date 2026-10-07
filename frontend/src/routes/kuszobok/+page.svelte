<script lang="ts">
  import { onMount } from "svelte";
  import { fetchThresholds } from "$lib/api";
  import type { ThresholdItem, ThresholdsResponse } from "$lib/types";

  let data: ThresholdsResponse | null = $state(null);
  let loading = $state(true);
  let error = $state("");

  onMount(() => {
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

  function exportCsv() {
    if (!data) return;
    const cell = (s: string) => `"${s.replace(/"/g, '""')}"`;
    const rows = [
      ["Csoport", "Küszöb megnevezése", "Mértékegység", "Érvényes érték", "Magyarázat", "Agronómus jóváhagyja (igen/nem)", "Javasolt érték", "Megjegyzés"],
      ...data.thresholds.map((t) => [t.group, t.label, t.unit, String(t.value), t.description, "", "", ""]),
    ];
    const csv = "\ufeff" + rows.map((r) => r.map(cell).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "kuszobertekek-jovahagyasra.csv";
    a.click();
    URL.revokeObjectURL(url);
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
      <a href="/napi">Napi kimutatás</a>
      <a href="/">Előrejelzés</a>
      <a href="/foldmunka">Földmunka</a>
      <a href="/kuszobok" aria-current="page">Küszöbök</a>
    </nav>
  </header>

  <main>
    <section class="intro" aria-labelledby="page-title">
      <h1 id="page-title">Működési küszöbértékek</h1>
    </section>

    {#if loading}
      <p class="status-panel" role="status">Küszöbértékek betöltése…</p>
    {:else if error}
      <div class="error-panel" role="alert">
        <span>{error}</span>
        <button class="retry-button" onclick={load}>Újrapróbálás</button>
      </div>
    {:else if data}
      {#if data.approved}
        <p class="approval approval-ok" role="status">Jóváhagyta: {data.approved_by}, {data.approved_on}</p>
      {:else}
        <p class="stale-note" role="status">Agronómiai felülvizsgálat szükséges.</p>
      {/if}

      <div class="no-print kuszob-actions">
        <button class="retry-button" onclick={() => window.print()}>Nyomtatás</button>
      </div>

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
                    <td class="col-value"><strong>{num(t.value)} {t.unit}</strong>{#if t.overridden} <span class="override-tag">módosított</span>{/if}</td>
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