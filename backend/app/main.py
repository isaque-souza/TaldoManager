"""Ponto de entrada da API (FastAPI).

Uso (a partir da pasta backend/):
    uvicorn app.main:app --reload

Jogo:              http://localhost:8000
Docs interativas:  http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import FRONTEND_DIR
from app.db.conexao import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Taldo Manager API",
    description="API para simular temporadas e navegar nos resultados.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

# O frontend é servido pela própria API: mesmo endereço, então não
# precisa de CORS. Montado por último, as rotas da API têm prioridade;
# o resto ("/", "/js/...", "/style.css") cai nos arquivos de frontend/.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
