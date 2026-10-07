from datetime import datetime, timedelta, timezone

from app.schemas import Location, Region
from app.services.observations import (
    Obs,
    Station,
    build_observations,
    local_offset,
    parse_index,
    parse_meta,
    parse_station_csv,
    select_stations,
)

LOC = Location(name="Teszt", slug="teszt", latitude=47.7, longitude=19.8, region="Heves")
REGION = Region(name="Teszt", slug="teszt", location_slugs=["teszt"])
LATEST = datetime(2026, 10, 7, 7, 0, tzinfo=timezone.utc)


def obs(**kw):
    base = dict(precip=0.0, temp=10.0, humidity=50.0, wind=2.0, wind_dir=270.0, gust=4.0)
    base.update(kw)
    return Obs(**base)


def series(**kw):
    start = LATEST - timedelta(hours=24)
    return {start + timedelta(minutes=10 * i): obs(**kw) for i in range(1, 145)}


def run(stations, data):
    return build_observations(
        {s.id: s for s in stations}, data, LATEST, regions=[REGION], locations=[LOC]
    ).regions[0].locations[0]


def test_parse_meta_keeps_latest_row_and_index():
    meta = parse_meta(
        "StationNumber;StartDate; EndDate;Latitude;Longitude;Elevation;StationName;RegioName;EOR\n"
        "  1; 19950101;20040101; 47.0;  19.0; 100.0;Régi;X;EOR\n"
        "  1; 20050101;20261007; 47.5;  19.5; 120.0;Új;X;EOR\n"
    )
    station, end = meta["1"]
    assert (station.name, station.latitude, end) == ("Új", 47.5, "20261007")
    assert parse_index('<a href="HABP_10M_13704_now.zip">HABP_10M_13704_now.zip</a>   2026-10-07 07:10  6.3K') == {
        "13704": "2026-10-07 07:10"
    }


def test_parse_station_csv_handles_missing_and_flagged_values():
    text = (
        "##Meta\n\nStationNumber; Time; r; Q_r; t; Q_t; fs; Q_fs;EOR\n"
        "1;202610070700; 0.4;; 8.4;; -999;;EOR\n"
        "1;202610070710; 0.2;1; 8.5;; 3.0;;EOR\n"
    )
    data = parse_station_csv(text)
    first, second = sorted(data)
    assert data[first].precip == 0.4 and data[first].wind is None
    assert data[second].precip is None and data[second].wind == 3.0


def test_local_offset_follows_eu_summer_time():
    assert local_offset(datetime(2026, 10, 7, tzinfo=timezone.utc)) == timedelta(hours=2)
    assert local_offset(datetime(2026, 12, 7, tzinfo=timezone.utc)) == timedelta(hours=1)
    assert local_offset(datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)) == timedelta(hours=2)
    assert local_offset(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)) == timedelta(hours=1)


def test_select_stations_uses_interpolation_only_with_multiple_stations_within_10km():
    near_a = Station("a", "A", 47.70, 19.81)
    near_b = Station("b", "B", 47.71, 19.80)
    far = Station("c", "C", 47.85, 19.80)
    method, picked = select_stations(LOC, [near_a, near_b, far])
    assert method == "interpoláció" and [s.id for s, _ in picked] == ["a", "b"]
    method, picked = select_stations(LOC, [near_a, far])
    assert method == "legközelebbi állomás" and [s.id for s, _ in picked] == ["a"]
    method, picked = select_stations(LOC, [Station("d", "D", 47.85, 19.8)])
    assert method == "legközelebbi állomás" and picked[0][0].id == "d"
    assert select_stations(LOC, [Station("e", "E", 48.5, 19.8)]) == ("nincs adat", [])


def test_interpolation_weights_closer_station_more():
    a = Station("a", "A", 47.70, 19.80)
    b = Station("b", "B", 47.76, 19.80)
    result = run([a, b], {"a": series(temp=10.0), "b": series(temp=20.0)})
    assert result.method == "interpoláció"
    assert 10.0 < result.latest_temp_c < 15.0
    assert [s.name for s in result.stations] == ["A", "B"]


def test_precipitation_sums_and_wind_extremes():
    a = Station("a", "A", 47.70, 19.80)
    data = series(precip=0.1)
    data[LATEST] = obs(precip=0.1, gust=11.0, wind=6.0)
    result = run([a], {"a": data})
    assert result.past_precip_mm == 14.4
    assert result.gust_max_ms == 11.0 and result.gust_time == "09:00"
    assert result.wind_max_ms == 6.0 and result.wind_direction == "Ny"
    assert result.today_temp_min_c == 10.0


def test_precipitation_is_none_when_coverage_is_poor_but_temperature_stays():
    a = Station("a", "A", 47.70, 19.80)
    sparse = {ts: o for i, (ts, o) in enumerate(series().items()) if i % 4 == 0 or ts == LATEST}
    result = run([a], {"a": sparse})
    assert result.past_precip_mm is None and result.precip_today_mm is None
    assert result.past_temp_max_c == 10.0


def test_stale_station_is_ignored_and_no_station_gives_no_data():
    a = Station("a", "A", 47.70, 19.80)
    old = {ts - timedelta(hours=3): o for ts, o in series().items()}
    assert run([Station("z", "Z", 48.9, 21.0)], {"z": series()}).method == "nincs adat"
    both = run([a, Station("b", "B", 47.71, 19.80)], {"a": old, "b": series()})
    assert [s.name for s in both.stations] == ["B"]
