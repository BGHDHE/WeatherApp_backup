import type { DailyResponse, FieldworkResponse, OutlookResponse, ThresholdsResponse } from "$lib/types";

export async function fetchOutlook(days = 7): Promise<OutlookResponse> {
  const response = await fetch(`/api/outlook?days=${days}`);
  if (!response.ok) {
    throw new Error(`API hiba (${response.status})`);
  }
  return response.json() as Promise<OutlookResponse>;
}
export async function fetchDaily(): Promise<DailyResponse> {
  const response = await fetch("/api/daily");
  if (!response.ok) {
    throw new Error(`API hiba (${response.status})`);
  }
  return response.json() as Promise<DailyResponse>;
}

export async function fetchFieldwork(): Promise<FieldworkResponse> {
  const response = await fetch("/api/fieldwork");
  if (!response.ok) {
    throw new Error(`API hiba (${response.status})`);
  }
  return response.json() as Promise<FieldworkResponse>;
}

export async function fetchThresholds(): Promise<ThresholdsResponse> {
  const response = await fetch("/api/thresholds");
  if (!response.ok) {
    throw new Error(`API hiba (${response.status})`);
  }
  return response.json() as Promise<ThresholdsResponse>;
}
