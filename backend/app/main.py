"""Ponto de entrada da API (FastAPI).

Uso (a partir da pasta backend/):
    uvicorn app.main:app --reload

Jogo:              http://localhost:8000
Docs interativas:  http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.contas import exigir_dono
from app.api.contas import router as contas_router
from app.api.routes import router
from app.core.config import FRONTEND_DIR
from app.db.conexao import init_db


class FrontendSempreAtual(StaticFiles):
    """Arquivos do frontend com `Cache-Control: no-cache`: o navegador
    guarda, mas pergunta ao servidor (ETag) se mudou antes de reusar.
    Sem isso ele reaproveita um módulo JS velho depois de uma atualização."""

    async def get_response(self, path, scope):
        resposta = await super().get_response(path, scope)
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta


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

app.include_router(contas_router)
# toda rota do jogo pede login e confere o dono do save (v2.1)
app.include_router(router, dependencies=[Depends(exigir_dono)])

# O frontend é servido pela própria API: mesmo endereço, então não
# precisa de CORS. Montado por último, as rotas da API têm prioridade;
# o resto ("/", "/js/...", "/style.css") cai nos arquivos de frontend/.
if FRONTEND_DIR.is_dir():
    app.mount("/", FrontendSempreAtual(directory=FRONTEND_DIR, html=True), name="frontend")
