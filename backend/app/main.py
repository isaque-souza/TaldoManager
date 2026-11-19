"""Ponto de entrada da API (FastAPI).

Uso (a partir da pasta backend/):
    uvicorn app.main:app --reload

Jogo:              http://localhost:8000
Docs interativas:  http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.contas import exigir_dono
from app.api.exibicao import ExibicaoMiddleware
from app.api.contas import router as contas_router
from app.api.routes import router
from app.core.config import FRONTEND_DIR
from app.db.conexao import conectar, init_db
from scripts import mundos

log = logging.getLogger("taldo")


class FrontendSempreAtual(StaticFiles):
    """Arquivos do frontend com `Cache-Control: no-cache`: o navegador
    guarda, mas pergunta ao servidor (ETag) se mudou antes de reusar.
    Sem isso ele reaproveita um módulo JS velho depois de uma atualização."""

    async def get_response(self, path, scope):
        resposta = await super().get_response(path, scope)
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta


def conferir_mundos():
    """Os mundos (v2.7) que algum save usa e não estão íntegros no disco —
    o save não abriria. Só avisa no log: o resto do jogo segue."""
    conn = conectar()
    try:
        usados = {r[0] for r in conn.execute("SELECT DISTINCT mundo FROM simulacao")}
    finally:
        conn.close()
    ruins = {}
    for mundo in sorted(usados | {mundos.MUNDO_PADRAO}):
        try:
            mundos.verificar(mundo)
        except mundos.MundoIndisponivel as e:
            ruins[mundo] = str(e)
            log.error("Mundo indisponível: %s", e)
    return ruins


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conferir_mundos()
    yield


app = FastAPI(
    title="Taldo Manager API",
    description="API para simular temporadas e navegar nos resultados.",
    version="1.0.0",
    lifespan=lifespan,
)


# nomes de exibição no lugar das chaves "apif:<id>" (v2.7); o v1 passa igual
app.add_middleware(ExibicaoMiddleware)


@app.exception_handler(mundos.MundoIndisponivel)
async def mundo_indisponivel(request: Request, exc: mundos.MundoIndisponivel):
    """Save cujo mundo (v2.7) sumiu ou foi alterado: erro claro, nunca um
    500 genérico — e nunca carregar outro mundo no lugar."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.include_router(contas_router)
# toda rota do jogo pede login e confere o dono do save (v2.1)
app.include_router(router, dependencies=[Depends(exigir_dono)])

# O frontend é servido pela própria API: mesmo endereço, então não
# precisa de CORS. Montado por último, as rotas da API têm prioridade;
# o resto ("/", "/js/...", "/style.css") cai nos arquivos de frontend/.
if FRONTEND_DIR.is_dir():
    app.mount("/", FrontendSempreAtual(directory=FRONTEND_DIR, html=True), name="frontend")
