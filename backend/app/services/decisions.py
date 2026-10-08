from app.schemas import FieldworkAssessment
from app.services import thresholds

# Kezdeti küszöbök; éles használat előtt agronómussal jóváhagyandók.
# Napi összesített adatból számolnak, ezért szándékosan óvatosak.
SPRAY_MAX_GUST_MS = thresholds.get("spray.max_gust_ms")
SPRAY_MAX_PRECIP_MM = thresholds.get("spray.max_precip_mm")
SPRAY_MIN_TEMP_C = thresholds.get("spray.min_temp_c")
SPRAY_MAX_TEMP_C = thresholds.get("spray.max_temp_c")
HARVEST_MAX_PRECIP_MM = thresholds.get("harvest.max_precip_mm")

SPRAY_THRESHOLD = (
    f"csapadék ≤ {SPRAY_MAX_PRECIP_MM:g} mm, széllökés ≤ {SPRAY_MAX_GUST_MS:g} m/s, "
    f"hőmérséklet {SPRAY_MIN_TEMP_C:g}–{SPRAY_MAX_TEMP_C:g} °C"
)
HARVEST_THRESHOLD = f"csapadék ≤ {HARVEST_MAX_PRECIP_MM:g} mm"


def _a(activity, status, reason, threshold) -> FieldworkAssessment:
    return FieldworkAssessment(activity=activity, status=status, reason=reason, threshold=threshold)


def assess_spraying(precip, gust, temp_min, temp_max, precip_scale=1.0) -> FieldworkAssessment:
    if None in (precip, gust, temp_min, temp_max):
        return _a("permetezés", "nincs adat", "Hiányos adat", SPRAY_THRESHOLD)
    problems = []
    if precip > SPRAY_MAX_PRECIP_MM * precip_scale:
        problems.append(f"csapadék {precip:g} mm")
    if gust > SPRAY_MAX_GUST_MS:
        problems.append(f"széllökés {gust:g} m/s")
    if temp_min < SPRAY_MIN_TEMP_C:
        problems.append(f"hideg ({temp_min:g} °C)")
    if temp_max > SPRAY_MAX_TEMP_C:
        problems.append(f"meleg ({temp_max:g} °C)")
    if problems:
        return _a("permetezés", "kedvezőtlen", ", ".join(problems), SPRAY_THRESHOLD)
    return _a("permetezés", "kedvező", "A feltételek a küszöbökön belül vannak", SPRAY_THRESHOLD)


def assess_harvest(precip, precip_scale=1.0) -> FieldworkAssessment:
    if precip is None:
        return _a("betakarítás", "nincs adat", "Hiányos adat", HARVEST_THRESHOLD)
    if precip > HARVEST_MAX_PRECIP_MM * precip_scale:
        return _a("betakarítás", "kedvezőtlen", f"csapadék {precip:g} mm", HARVEST_THRESHOLD)
    return _a("betakarítás", "kedvező", "Száraz idő várható", HARVEST_THRESHOLD)