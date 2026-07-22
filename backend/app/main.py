from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, domains, scans

app = FastAPI(title="VulnScan Pro API")

# The frontend (Vite dev server on :5173) and the API (:8000) are different
# origins per the browser's same-origin policy, so the browser blocks the
# frontend's JS from reading responses unless the API explicitly allows it
# via these headers. This is a browser-enforced rule, not a server one -
# curl/Postman never needed this. allow_credentials + Authorization header
# is what lets the JWT bearer token flow through.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(domains.router)
app.include_router(scans.router)


@app.get("/health")
def health():
    return {"status": "ok"}
