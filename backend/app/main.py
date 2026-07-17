from fastapi import FastAPI

from app.api.routes import auth, domains, scans

app = FastAPI(title="VulnScan Pro API")

app.include_router(auth.router)
app.include_router(domains.router)
app.include_router(scans.router)


@app.get("/health")
def health():
    return {"status": "ok"}
