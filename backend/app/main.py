from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import patients, documents, notes

app = FastAPI(
    title="ClinFlow API",
    description="AI-powered clinical continuity-of-care platform.",
    version="0.1.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow the React dev server (localhost:5173) in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(patients.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(notes.router, prefix="/api")


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "ClinFlow API"}
