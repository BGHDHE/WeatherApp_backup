from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="Agromet Időjárás API",
    description="Települési időjárás-előrejelzések Open-Meteo adatokból.",
    version="0.1.0",
)
app.include_router(router)
