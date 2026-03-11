from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import events, fighters, fights, predictions

app = FastAPI(title="NeuralFight", version="0.1.0", description="AI-powered UFC fight predictor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(fighters.router)
app.include_router(fights.router)
app.include_router(predictions.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
