"""Az összes szabályküszöb egy helyen, hogy szakmailag átnézhető és felülírható legyen.

Felülírás: JSON fájl (THRESHOLDS_FILE, alapértelmezés: data/thresholds.json), pl.
{"approved_by": "Kovács Anna", "approved_on": "2026-10-20", "values": {"spray.max_gust_ms": 6}}
Az érvénytelen vagy ismeretlen kulcsokat figyelmen kívül hagyjuk. Változtatás után a backend újraindítása kell.
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Threshold:
    key: str
    group: str
    label: str
    default: float
    unit: str
    description: str


DEFINITIONS: list[Threshold] = [
    Threshold("frost.high_c", "Fagyveszély", "Magas fagyveszély", 0.0, "°C", "A napi minimum eléri vagy meghaladja a kritikus fagyhatárt."),
    Threshold("frost.moderate_c", "Fagyveszély", "Mérsékelt fagyveszély", 2.0, "°C", "A napi minimum a mérsékelt fagyveszélyi küszöb alatt marad."),
    Threshold("frost.low_c", "Fagyveszély", "Alacsony fagyveszély", 5.0, "°C", "A napi minimum az enyhe fagyveszélyi küszöb alatt marad."),
    Threshold("outlook.heavy_rain_mm", "Kirívó események (előrejelzés)", "Jelentős csapadék", 10.0, "mm", "A napi csapadék eléri a riasztási küszöböt."),
    Threshold("outlook.strong_gust_ms", "Kirívó események (előrejelzés)", "Erős széllökés", 17.0, "m/s", "A napi legerősebb széllökés eléri a riasztási küszöböt."),
    Threshold("outlook.frost_c", "Kirívó események (előrejelzés)", "Fagyriasztás", 2.0, "°C", "A napi minimum a fagyriasztási küszöb alá esik."),
    Threshold("outlook.heat_c", "Kirívó események (előrejelzés)", "Hőségriasztás", 33.0, "°C", "A napi maximum meghaladja a hőségriasztási küszöböt."),
    Threshold("outlook.wet_day_mm", "Kirívó események (előrejelzés)", "Csapadékos nap", 1.0, "mm", "A napi csapadékösszeg alapján esős napnak számít."),
    Threshold("spray.max_precip_mm", "Permetezés", "Maximum csapadék", 0.5, "mm", "A megengedettnél több csapadék esetén nem javasolt."),
    Threshold("spray.max_gust_ms", "Permetezés", "Maximum széllökés", 8.0, "m/s", "A határértéknél erősebb szélben nem javasolt (elsodródás veszélye)."),
    Threshold("spray.min_temp_c", "Permetezés", "Minimum hőmérséklet", 5.0, "°C", "A minimális üzemi hőmérséklet alatt nem javasolt."),
    Threshold("spray.max_temp_c", "Permetezés", "Maximum hőmérséklet", 25.0, "°C", "A maximális üzemi hőmérséklet felett nem javasolt."),
    Threshold("harvest.max_precip_mm", "Betakarítás", "Maximum csapadék", 1.0, "mm", "A kritikus csapadékmennyiség felett nem javasolt."),
    Threshold("tillage.ok_precip_mm", "Talajművelés és járhatóság", "Kedvező csapadék", 1.0, "mm", "Ennyi napi csapadékig a talajállapot még kedvező."),
    Threshold("tillage.bad_precip_mm", "Talajművelés és járhatóság", "Kedvezőtlen csapadék", 5.0, "mm", "Ettől a csapadékmennyiségtől a talajállapot már kedvezőtlen."),
    Threshold("tillage.ok_prev3_mm", "Talajművelés és járhatóság", "Kedvező előző 3 napi csapadék", 10.0, "mm", "Az előző 3 nap csapadékösszege alapján még kedvező."),
    Threshold("tillage.bad_prev3_mm", "Talajművelés és járhatóság", "Kedvezőtlen előző 3 napi csapadék", 20.0, "mm", "Az előző 3 nap csapadékösszege alapján már kedvezőtlen."),
    Threshold("tillage.ok_subsoil_pct", "Talajművelés és járhatóság", "Alsó réteg nedvessége (kedvező)", 35.0, "%", "Az alsó réteg (7–28 cm) nedvessége a megengedett határon belül van."),
    Threshold("tillage.bad_subsoil_pct", "Talajművelés és járhatóság", "Alsó réteg nedvessége (kedvezőtlen)", 40.0, "%", "Az alsó réteg nedvessége alapján már túl nedves (átázott)."),
    Threshold("traffic.ok_topsoil_pct", "Talajművelés és járhatóság", "Felső réteg nedvessége (kedvező)", 35.0, "%", "A felső réteg (0–7 cm) nedvessége alapján még teherbíró."),
    Threshold("traffic.bad_topsoil_pct", "Talajművelés és járhatóság", "Felső réteg nedvessége (kedvezőtlen)", 40.0, "%", "A felső réteg nedvessége alapján túl vizes, nehezen járható."),
    Threshold("sowing.ok_soil_temp_c", "Vetés", "Kedvező talajhőmérséklet", 8.0, "°C", "A talajhőmérséklet (6 cm) eléri a vetéshez szükséges szintet."),
    Threshold("sowing.bad_soil_temp_c", "Vetés", "Túl hideg talaj", 4.0, "°C", "A talajhőmérséklet a csírázáshoz szükséges érték alatt van."),
    Threshold("sowing.dry_topsoil_pct", "Vetés", "Túl száraz felső réteg", 15.0, "%", "A felső réteg nedvessége a kritikus szint alatt van (feltételes)."),
]

_BY_KEY = {t.key: t for t in DEFINITIONS}


@dataclass(frozen=True)
class Overrides:
    values: dict[str, float]
    approved_by: str | None
    approved_on: str | None


def _path() -> Path:
    return Path(os.environ.get("THRESHOLDS_FILE", "data/thresholds.json"))


def load_overrides(path: Path | None = None) -> Overrides:
    path = path or _path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Overrides({}, None, None)
    except (OSError, ValueError) as exc:
        logger.warning("Küszöbfájl nem olvasható (%s), az alapértékek érvényesek", exc)
        return Overrides({}, None, None)
    if not isinstance(raw, dict):
        return Overrides({}, None, None)
    values: dict[str, float] = {}
    for key, value in (raw.get("values") or {}).items():
        if key in _BY_KEY and isinstance(value, (int, float)) and not isinstance(value, bool):
            values[key] = float(value)
        else:
            logger.warning("Érvénytelen küszöb figyelmen kívül hagyva: %s", key)
    approved_by = raw.get("approved_by")
    approved_on = raw.get("approved_on")
    return Overrides(
        values,
        approved_by if isinstance(approved_by, str) else None,
        approved_on if isinstance(approved_on, str) else None,
    )


_overrides = load_overrides()


def get(key: str) -> float:
    return _overrides.values.get(key, _BY_KEY[key].default)


def overrides() -> Overrides:
    return _overrides