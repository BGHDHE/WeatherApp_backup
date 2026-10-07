export type Condition = "száraz" | "csapadék" | "zivatar" | "nincs adat";
export type AlertKind = "zivatar" | "csapadék" | "szél" | "fagy" | "hőség";

export interface OutlookDay {
  date: string;
  temp_min_c: number | null;
  temp_max_c: number | null;
  precipitation_max_mm: number | null;
  wind_gust_max_ms: number | null;
  condition: Condition;
}

export interface OutlookAlert {
  date: string;
  kind: AlertKind;
  locations: string[];
  message: string;
}

export interface RegionOutlook {
  name: string;
  slug: string;
  locations: string[];
  summary: string;
  days: OutlookDay[];
  alerts: OutlookAlert[];
}

export interface OutlookResponse {
  provider: "open-meteo";
  source_type: "forecast";
  fetched_at: string;
  timezone: string;
  regions: RegionOutlook[];
  stale: boolean;
}
export type FrostLevel = "nincs adat" | "nincs" | "alacsony" | "mérsékelt" | "magas";

export interface LocationDaily {
  name: string;
  slug: string;
  past_temp_min_c: number | null;
  past_temp_max_c: number | null;
  past_precip_mm: number | null;
  past_gust_max_ms: number | null;
  today_temp_min_c: number | null;
  today_temp_max_c: number | null;
  precip_today_mm: number | null;
  precip_window: string | null;
  precip_probability_max: number | null;
  wind_max_ms: number | null;
  wind_direction: string | null;
  gust_max_ms: number | null;
  gust_time: string | null;
  frost_level: FrostLevel;
  frost_min_temp_c: number | null;
  soil_temperature_c: number | null;
  soil_moisture_percent: number | null;
  evapotranspiration_mm: number | null;
}

export interface RegionDaily {
  name: string;
  slug: string;
  locations: LocationDaily[];
}

export interface DailyResponse {
  provider: "open-meteo";
  source_type: "forecast";
  fetched_at: string;
  timezone: string;
  date: string;
  as_of: string;
  regions: RegionDaily[];
  stale: boolean;
}

export type FieldworkStatus = "kedvező" | "feltételes" | "kedvezőtlen" | "nincs adat";

export interface FieldworkAssessment {
  activity: "talajművelés" | "vetés" | "gépek járhatósága" | "permetezés" | "betakarítás";
  status: FieldworkStatus;
  reason: string;
  threshold: string;
}

export interface FieldworkDay {
  date: string;
  precipitation_mm: number | null;
  precipitation_prev_3d_mm: number | null;
  temp_min_c: number | null;
  temp_max_c: number | null;
  soil_temperature_c: number | null;
  topsoil_moisture_percent: number | null;
  subsoil_moisture_percent: number | null;
  wind_gust_max_ms: number | null;
  assessments: FieldworkAssessment[];
}

export interface FieldworkLocation {
  name: string;
  slug: string;
  summary: string;
  precipitation_week_mm: number | null;
  best_tillage_window: string | null;
  days: FieldworkDay[];
}

export interface FieldworkRegion {
  name: string;
  slug: string;
  summary: string;
  locations: FieldworkLocation[];
}

export interface FieldworkResponse {
  provider: "open-meteo";
  source_type: "forecast";
  fetched_at: string;
  timezone: string;
  regions: FieldworkRegion[];
  stale: boolean;
}

export interface ThresholdItem {
  key: string;
  group: string;
  label: string;
  unit: string;
  description: string;
  default: number;
  value: number;
  overridden: boolean;
}

export interface ThresholdsResponse {
  approved: boolean;
  approved_by: string | null;
  approved_on: string | null;
  thresholds: ThresholdItem[];
}

export interface StationRef {
  name: string;
  distance_km: number;
  observed_at: string | null;
}

export interface LocationObservation {
  name: string;
  slug: string;
  method: "interpoláció" | "legközelebbi állomás" | "nincs adat";
  stations: StationRef[];
  latest_time: string | null;
  latest_temp_c: number | null;
  latest_humidity_percent: number | null;
  latest_wind_ms: number | null;
  past_temp_min_c: number | null;
  past_temp_max_c: number | null;
  past_precip_mm: number | null;
  past_gust_max_ms: number | null;
  today_temp_min_c: number | null;
  today_temp_max_c: number | null;
  precip_today_mm: number | null;
  wind_max_ms: number | null;
  wind_direction: string | null;
  gust_max_ms: number | null;
  gust_time: string | null;
  frost_level: "nincs adat" | "nincs" | "alacsony" | "mérsékelt" | "magas";
  frost_min_temp_c: number | null;
}

export interface RegionObservation {
  name: string;
  slug: string;
  locations: LocationObservation[];
}

export interface ObservationResponse {
  provider: "odp.met.hu";
  source_type: "observation";
  fetched_at: string;
  timezone: string;
  date: string;
  as_of: string | null;
  regions: RegionObservation[];
  stale: boolean;
}
