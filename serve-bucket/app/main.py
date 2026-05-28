from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes_editor import router as editor_router
from app.routes_proxy import router as proxy_router

BASE_DIR = Path(__file__).parent.parent
EDITOR_DIR = BASE_DIR / "editor"

app = FastAPI(title="paf-serve-bucket")

# Editor SPA: mount static files. index.html is served at /editor/.
app.mount("/editor", StaticFiles(directory=str(EDITOR_DIR), html=True), name="editor")

# API routes (declared before proxy so they take precedence)
app.include_router(editor_router)

# Catch-all bucket proxy (must be last)
app.include_router(proxy_router)
