from app.schemas import FieldworkAssessment
from app.services import thresholds

# Kezdeti küszöbök; éles használat előtt agronómussal jóváhagyandók.
# Napi összesített adatból számolnak, ezért szándékosan óvatosak.
SPRAY_MAX_WIND_MS = thresholds.get("spray.max_wind_ms")
SPRAY_MAX_GUST_MS = thresholds.get("spray.max_gust_ms")
SPRAY_MAX_PRECIP_MM = thresholds.get("spray.max_precip_mm")
SPRAY_MIN_TEMP_C = thresholds.get("spray.min_temp_c")
SPRAY_MAX_TEMP_C = thresholds.get("spray.max_temp_c")
HARVEST_MAX_PRECIP_MM = thresholds.get("harvest.max_precip_mm")
HARVEST_CAUTION_RH = thresholds.get("harvest.caution_humidity_pct")
HARVEST_BAD_RH = thresholds.get("harvest.bad_humidity_pct")
SPRAY_MIN_RH = thresholds.get("spray.min_humidity_pct")
SPRAY_MAX_RH = thresholds.get("spray.max_humidity_pct")
SPRAY_DEW_SPREAD_C = thresholds.get("spray.dew_spread_c")
SPRAY_MIN_DELTA_T = thresholds.get("spray.min_delta_t_c")
SPRAY_MAX_DELTA_T = thresholds.get("spray.max_delta_t_c")
SPRAY_BAD_DELTA_T = thresholds.get("spray.bad_delta_t_c")
SPRAY_INVERSION_DT_C = thresholds.get("spray.inversion_dt_c")
SPRAY_INVERSION_MAX_WIND_MS = thresholds.get("spray.inversion_max_wind_ms")

SPRAY_THRESHOLD = (
    f"csapadék ≤ {SPRAY_MAX_PRECIP_MM:g} mm, szél ≤ {SPRAY_MAX_WIND_MS:g} m/s, széllökés ≤ {SPRAY_MAX_GUST_MS:g} m/s, "
    f"hőmérséklet {SPRAY_MIN_TEMP_C:g}–{SPRAY_MAX_TEMP_C:g} °C, "
    f"páratartalom {SPRAY_MIN_RH:g}–{SPRAY_MAX_RH:g}%, Delta T {SPRAY_MIN_DELTA_T:g}–{SPRAY_MAX_DELTA_T:g} °C "
    f"(> {SPRAY_BAD_DELTA_T:g} kedvezőtlen), nincs harmat (T–harmatpont > {SPRAY_DEW_SPREAD_C:g} °C), "
    f"nincs inverzió (80 m ≤ 2 m + {SPRAY_INVERSION_DT_C:g} °C vagy szél > {SPRAY_INVERSION_MAX_WIND_MS:g} m/s)"
)
HARVEST_THRESHOLD = (
    f"csapadék ≤ {HARVEST_MAX_PRECIP_MM:g} mm, páratartalom ≤ {HARVEST_CAUTION_RH:g}% "
    f"(> {HARVEST_BAD_RH:g}% kedvezőtlen)"
)


def _a(activity, status, reason, threshold) -> FieldworkAssessment:
    return FieldworkAssessment(activity=activity, status=status, reason=reason, threshold=threshold)


def assess_spraying(
    precip, gust, temp_min, temp_max, precip_scale=1.0, wind=None,
    humidity=None, delta_t=None, dew_spread=None, inversion=None,
) -> FieldworkAssessment:
    if None in (precip, gust, temp_min, temp_max):
        return _a("permetezés", "nincs adat", "Hiányos adat", SPRAY_THRESHOLD)
    problems, cautions = [], []
    if precip > SPRAY_MAX_PRECIP_MM * precip_scale:
        problems.append(f"csapadék {precip:g} mm")
    if wind is not None and wind > SPRAY_MAX_WIND_MS:
        problems.append(f"szél {wind:g} m/s")
    if gust > SPRAY_MAX_GUST_MS:
        problems.append(f"széllökés {gust:g} m/s")
    if temp_min < SPRAY_MIN_TEMP_C:
        problems.append(f"hideg ({temp_min:g} °C)")
    if temp_max > SPRAY_MAX_TEMP_C:
        problems.append(f"meleg ({temp_max:g} °C)")
    if inversion:
        problems.append("hőmérsékleti inverzió (elsodródás veszélye)")
    if delta_t is not None:
        if delta_t > SPRAY_BAD_DELTA_T:
            problems.append(f"túl magas Delta T ({delta_t:g} °C, gyors párolgás)")
        elif delta_t > SPRAY_MAX_DELTA_T:
            cautions.append(f"magas Delta T ({delta_t:g} °C)")
        elif delta_t < SPRAY_MIN_DELTA_T:
            cautions.append(f"alacsony Delta T ({delta_t:g} °C)")
    if humidity is not None:
        if humidity < SPRAY_MIN_RH:
            cautions.append(f"száraz levegő ({humidity:g}% páratartalom)")
        elif humidity > SPRAY_MAX_RH:
            cautions.append(f"nagyon párás levegő ({humidity:g}%)")
    if dew_spread is not None and dew_spread <= SPRAY_DEW_SPREAD_C:
        cautions.append("harmat, nedves levél")
    if problems:
        return _a("permetezés", "kedvezőtlen", ", ".join(problems + cautions), SPRAY_THRESHOLD)
    if cautions:
        return _a("permetezés", "feltételes", ", ".join(cautions), SPRAY_THRESHOLD)
    return _a("permetezés", "kedvező", "A feltételek a küszöbökön belül vannak", SPRAY_THRESHOLD)


def assess_harvest(precip, precip_scale=1.0, humidity=None) -> FieldworkAssessment:
    if precip is None:
        return _a("betakarítás", "nincs adat", "Hiányos adat", HARVEST_THRESHOLD)
    if precip > HARVEST_MAX_PRECIP_MM * precip_scale:
        return _a("betakarítás", "kedvezőtlen", f"csapadék {precip:g} mm", HARVEST_THRESHOLD)
    if humidity is not None:
        if humidity > HARVEST_BAD_RH:
            return _a("betakarítás", "kedvezőtlen", f"nagyon párás levegő ({humidity:g}%)", HARVEST_THRESHOLD)
        if humidity > HARVEST_CAUTION_RH:
            return _a("betakarítás", "feltételes", f"párás levegő ({humidity:g}%), nedves termény", HARVEST_THRESHOLD)
    return _a("betakarítás", "kedvező", "Száraz idő várható", HARVEST_THRESHOLD)