from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI()

# Allow all origins in dev so file:// or other local setups can hit it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in dev, this is fine; we'll tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
