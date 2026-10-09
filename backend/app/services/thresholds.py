"""Az összes szabályküszöb egy helyen; az értékek ebben a fájlban módosíthatók (utána a backend újraindítása kell)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Threshold:
    key: str
    group: str
    label: str
    value: float
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
    Threshold("spray.max_wind_ms", "Permetezés", "Maximum szélsebesség", 5.0, "m/s", "A határértéknél erősebb átlagos szélben nem javasolt (elsodródás veszélye)."),
    Threshold("spray.max_gust_ms", "Permetezés", "Maximum széllökés", 8.0, "m/s", "A határértéknél erősebb széllökés esetén nem javasolt (elsodródás veszélye)."),
    Threshold("spray.min_temp_c", "Permetezés", "Minimum hőmérséklet", 5.0, "°C", "A minimális üzemi hőmérséklet alatt nem javasolt."),
    Threshold("spray.max_temp_c", "Permetezés", "Maximum hőmérséklet", 25.0, "°C", "A maximális üzemi hőmérséklet felett nem javasolt."),
    Threshold("spray.min_humidity_pct", "Permetezés", "Minimum páratartalom", 40.0, "%", "A határ alatt gyors a párolgás és az elsodródás (feltételes)."),
    Threshold("spray.max_humidity_pct", "Permetezés", "Maximum páratartalom", 90.0, "%", "A határ felett a permetlé nem szárad, lemosódhat (feltételes)."),
    Threshold("spray.dew_spread_c", "Permetezés", "Harmat (hőmérséklet – harmatpont)", 1.0, "°C", "Ennyi vagy kisebb különbségnél harmat/nedves levél várható (feltételes)."),
    Threshold("spray.min_delta_t_c", "Permetezés", "Minimum Delta T", 2.0, "°C", "A hőmérséklet és a nedves hőmérséklet különbsége; alatta párás, inverzióra hajlamos idő (feltételes)."),
    Threshold("spray.max_delta_t_c", "Permetezés", "Maximum Delta T", 8.0, "°C", "Felette gyors a cseppek párolgása (feltételes)."),
    Threshold("spray.bad_delta_t_c", "Permetezés", "Kedvezőtlen Delta T", 10.0, "°C", "Felette a cseppek elpárolognak, a permetezés nem javasolt."),
    Threshold("spray.inversion_dt_c", "Permetezés", "Inverzió (80 m – 2 m hőmérséklet)", 0.5, "°C", "Ennyivel melegebb a levegő 80 m-en, mint 2 m-en, gyenge szélben inverzió van."),
    Threshold("spray.inversion_max_wind_ms", "Permetezés", "Inverzió szélhatár", 3.0, "m/s", "Ennél gyengébb szélben alakul ki tartós inverzió."),
    Threshold("harvest.caution_humidity_pct", "Betakarítás", "Páratartalom (feltételes)", 80.0, "%", "A határ felett nedves a termény, betakarítás csak feltételesen."),
    Threshold("harvest.bad_humidity_pct", "Betakarítás", "Páratartalom (kedvezőtlen)", 90.0, "%", "A határ felett a betakarítás nem javasolt."),
    Threshold("tillage.frost_c", "Talajművelés és járhatóság", "Fagy (kedvezőtlen)", 0.0, "°C", "Ezen vagy ez alatt fagyos talaj/levegő miatt kedvezőtlen."),
    Threshold("tillage.frost_caution_c", "Talajművelés és járhatóság", "Fagyveszély (feltételes)", 2.0, "°C", "Ezen vagy ez alatt fagyveszély miatt feltételes."),
    Threshold("sowing.week_precip_wet_mm", "Vetés", "Csapadékos hét", 40.0, "mm", "A következő 7 nap csapadéka a határ felett vetés után eliszapolódást okozhat (feltételes)."),
    Threshold("sowing.week_precip_dry_mm", "Vetés", "Száraz hét", 3.0, "mm", "A következő 7 nap csapadéka a határ alatt a csírázás vízellátása bizonytalan (feltételes)."),
    Threshold("sowing.soil_cooling_c", "Vetés", "Talajhűlés trend", 2.0, "°C", "A talajhőmérséklet ennyivel vagy többel csökken a következő napokban (feltételes)."),
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


def get(key: str) -> float:
    return _BY_KEY[key].value
