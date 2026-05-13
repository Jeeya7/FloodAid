from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

# create the FastAPI app — this is the whole backend in one object
app = FastAPI(title="FloodAid API")

# CORS lets our Flutter app talk to this backend
# without this, the browser blocks requests coming from a different origin
# allow_origins=["*"] means any frontend can call us [fine for our demo, but in production we'd want to lock this down]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # who can call us
    allow_credentials=False,   # we don't use cookies so this is fine
    allow_methods=["*"],       # allow GET, POST, etc
    allow_headers=["*"],       # allow any headers
)

# plug in all our routes from routes.py under the /api prefix
# so /health becomes /api/health, /resources becomes /api/resources, etc.
app.include_router(router, prefix="/api")