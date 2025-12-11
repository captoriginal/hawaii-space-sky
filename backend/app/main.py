from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow all origins in dev so file:// or other local setups can hit it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in dev, this is fine; we'll tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status():
    return {
        "message": "Phase 1 backend is alive, demo JSON coming soon!"
    }
