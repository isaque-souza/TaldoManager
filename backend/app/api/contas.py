"""Rotas de conta (v2.1) e a checagem de dono que protege as rotas do jogo.

O login vive num cookie HttpOnly: o frontend é servido pela própria API
(mesmo endereço), então o navegador manda o cookie em todo `fetch` sem o
JavaScript precisar ver o token.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.services import conta_service
from app.services.conta_service import ContaInvalida, MuitasTentativas

COOKIE = "taldo_sessao"

# rotas do jogo que não pedem login: saúde e o catálogo da seed
_PUBLICAS = ("/health", "/clubes")

router = APIRouter(prefix="/conta", tags=["conta"])


class Credenciais(BaseModel):
    nome: str
    senha: str


class Usuario(BaseModel):
    id: int
    nome: str


def _cookie_seguro():
    # no servidor com HTTPS, TALDO_COOKIE_SEGURO=1: o cookie só anda cifrado
    return os.environ.get("TALDO_COOKIE_SEGURO") == "1"


def _ip(request):
    return request.client.host if request.client else "?"


def _por_cookie(response, token):
    response.set_cookie(
        COOKIE, token,
        max_age=int(conta_service.DURACAO_SESSAO.total_seconds()),
        httponly=True, samesite="lax", secure=_cookie_seguro(),
    )


def sessao_atual(request: Request):
    """{id, nome} de quem está logado, ou None."""
    return conta_service.usuario_da_sessao(request.cookies.get(COOKIE))


def id_do_usuario(usuario=Depends(sessao_atual)):
    return usuario["id"] if usuario else None


def exigir_dono(request: Request, usuario=Depends(sessao_atual)):
    """Dependência das rotas do jogo: pede login e só deixa passar quem é
    dono do save (ou da carreira) do caminho. O save de outro técnico
    responde 404, como se não existisse."""
    caminho = request.url.path
    if caminho.startswith(_PUBLICAS):
        return
    if usuario is None:
        raise HTTPException(status_code=401, detail="Entre na sua conta")
    sim_id = _id_do_caminho(request, "simulacao_id")
    if sim_id is not None and not conta_service.pode_ver_simulacao(usuario["id"], sim_id):
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
    carreira_id = _id_do_caminho(request, "carreira_id")
    if carreira_id is not None and not conta_service.pode_ver_carreira(
        usuario["id"], carreira_id
    ):
        raise HTTPException(status_code=404, detail="Carreira não encontrada")


def _id_do_caminho(request, nome):
    # um id que não é número fica para a validação da rota (422)
    try:
        return int(request.path_params[nome])
    except (KeyError, ValueError):
        return None


def _entrar_com(acao, cred, request, response):
    try:
        token, usuario = acao(cred.nome, cred.senha, _ip(request))
    except MuitasTentativas as e:
        raise HTTPException(
            status_code=429, detail="Muitas tentativas. Espere alguns minutos."
        ) from e
    except ContaInvalida as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _por_cookie(response, token)
    return usuario


@router.post("/registrar", response_model=Usuario, status_code=201)
def registrar(cred: Credenciais, request: Request, response: Response):
    """Cria a conta e já entra nela."""
    return _entrar_com(conta_service.registrar, cred, request, response)


@router.post("/entrar", response_model=Usuario)
def entrar(cred: Credenciais, request: Request, response: Response):
    return _entrar_com(conta_service.entrar, cred, request, response)


@router.post("/sair", status_code=204)
def sair(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        conta_service.sair(token)
    response.delete_cookie(COOKIE)


@router.get("/eu", response_model=Usuario | None)
def eu(usuario=Depends(sessao_atual)):
    """Quem está logado; null se ninguém (a tela de entrada decide)."""
    return usuario
