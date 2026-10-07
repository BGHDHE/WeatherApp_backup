from app.schemas import Location, Region

LOCATIONS = [
    Location(name="Szarvasgede", slug="szarvasgede", latitude=47.8213, longitude=19.6417, region="Nógrád"),
    Location(name="Pásztó", slug="paszto", latitude=47.9202, longitude=19.6983, region="Nógrád"),
    Location(name="Heves", slug="heves", latitude=47.60, longitude=20.2833, region="Heves"),
    Location(name="Kompolt", slug="kompolt", latitude=47.7422, longitude=20.2419, region="Heves"),
    Location(name="Kál", slug="kal", latitude=47.7333, longitude=20.2667, region="Heves"),
    Location(name="Hort", slug="hort", latitude=47.6908, longitude=19.7893, region="Heves"),
    Location(name="Gyöngyös", slug="gyongyos", latitude=47.7826, longitude=19.928, region="Heves"),
]

REGIONS = [
    Region(name="Szarvasgede–Pásztó", slug="szarvasgede-paszto", location_slugs=["szarvasgede", "paszto"]),
    Region(name="Hort–Gyöngyös", slug="hort-gyongyos", location_slugs=["hort", "gyongyos"]),
    Region(name="Kál–Kompolt–Heves", slug="kal-kompolt-heves", location_slugs=["kal", "kompolt", "heves"]),
]

_LOCATIONS_BY_SLUG = {location.slug: location for location in LOCATIONS}


def get_location(slug: str) -> Location | None:
    return _LOCATIONS_BY_SLUG.get(slug)