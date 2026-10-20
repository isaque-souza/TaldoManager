"""Contas de técnico (v2.1): cadastro, login por sessão e dono dos saves.

A senha vira um hash scrypt (biblioteca padrão, sem dependência nova); a
sessão é um token aleatório que vai no cookie, e o banco guarda só o
sha256 dele — quem lê o banco não consegue se passar por ninguém.
"""

import hashlib
import hmac
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from app.db.conexao import conectar
from app.repositories import simulacao_repository as simulacao_repo
from app.repositories import usuario_repository as usuario_repo

DURACAO_SESSAO = timedelta(days=30)
LIMITE_JOGOS = 10          # jogos (carreiras ou saves avulsos) por conta
NOME_VALIDO = re.compile(r"^[\w.-]{3,20}$")
SENHA_MINIMA = 6

# freio contra quem tenta adivinhar senha ou criar contas em série,
# por IP: (tentativas, janela em segundos)
_LIMITES = {"entrar": (10, 15 * 60), "registrar": (5, 60 * 60)}
_tentativas = {}
_trava = threading.Lock()


class ContaInvalida(ValueError):
    """Cadastro ou login recusado (o texto vai para a tela)."""


class MuitasTentativas(Exception):
    """O IP passou do limite de tentativas da janela."""


class LimiteDeJogos(Exception):
    """A conta já tem o máximo de jogos."""


def _agora():
    return datetime.now(timezone.utc)


def _hash_senha(senha, sal=None):
    sal = sal or secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"{sal.hex()}${h.hex()}"


def _senha_confere(senha, guardado):
    sal, _ = guardado.split("$", 1)
    return hmac.compare_digest(_hash_senha(senha, bytes.fromhex(sal)), guardado)


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _contar_tentativa(acao, ip):
    """Registra a tentativa; `MuitasTentativas` se passou do limite."""
    maximo, janela = _LIMITES[acao]
    agora = time.monotonic()
    with _trava:
        recentes = [t for t in _tentativas.get((acao, ip), []) if agora - t < janela]
        if len(recentes) >= maximo:
            _tentativas[(acao, ip)] = recentes
            raise MuitasTentativas()
        recentes.append(agora)
        _tentativas[(acao, ip)] = recentes


def _esquecer_tentativas(acao, ip):
    with _trava:
        _tentativas.pop((acao, ip), None)


def _abrir_sessao(conn, usuario_id):
    token = secrets.token_urlsafe(32)
    agora = _agora()
    usuario_repo.apagar_sessoes_vencidas(conn, agora.isoformat())
    usuario_repo.criar_sessao(
        conn, _hash_token(token), usuario_id, (agora + DURACAO_SESSAO).isoformat()
    )
    return token


def registrar(nome, senha, ip):
    """Cria a conta e já entra. Devolve (token, {id, nome})."""
    nome = (nome or "").strip()
    if not NOME_VALIDO.match(nome):
        raise ContaInvalida(
            "O nome precisa ter de 3 a 20 letras, números, ponto, hífen ou _"
        )
    if len(senha or "") < SENHA_MINIMA:
        raise ContaInvalida(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres")
    _contar_tentativa("registrar", ip)

    conn = conectar()
    try:
        if usuario_repo.buscar_por_nome(conn, nome) is not None:
            raise ContaInvalida("Esse nome já está em uso")
        usuario_id = usuario_repo.criar(
            conn, nome, _hash_senha(senha), _agora().isoformat()
        )
        token = _abrir_sessao(conn, usuario_id)
        conn.commit()
        return token, {"id": usuario_id, "nome": nome}
    finally:
        conn.close()


def entrar(nome, senha, ip):
    """Confere a senha e abre uma sessão. Devolve (token, {id, nome})."""
    _contar_tentativa("entrar", ip)
    conn = conectar()
    try:
        u = usuario_repo.buscar_por_nome(conn, (nome or "").strip())
        if u is None or not _senha_confere(senha or "", u["senha_hash"]):
            raise ContaInvalida("Nome ou senha incorretos")
        token = _abrir_sessao(conn, u["id"])
        conn.commit()
    finally:
        conn.close()
    _esquecer_tentativas("entrar", ip)
    return token, {"id": u["id"], "nome": u["nome"]}


def sair(token):
    conn = conectar()
    try:
        usuario_repo.apagar_sessao(conn, _hash_token(token))
        conn.commit()
    finally:
        conn.close()


def usuario_da_sessao(token):
    """{id, nome} do dono da sessão; None se o token não vale (ou venceu)."""
    if not token:
        return None
    conn = conectar()
    try:
        s = usuario_repo.buscar_sessao(conn, _hash_token(token))
        if s is None or s["expira_em"] < _agora().isoformat():
            return None
        u = usuario_repo.buscar(conn, s["usuario_id"])
        return None if u is None else {"id": u["id"], "nome": u["nome"]}
    finally:
        conn.close()


def pode_ver_simulacao(usuario_id, simulacao_id):
    """True se o save é do técnico ou não existe (aí a rota dá o 404)."""
    conn = conectar()
    try:
        existe, dono = usuario_repo.dono_da_simulacao(conn, simulacao_id)
        return not existe or dono == usuario_id
    finally:
        conn.close()


def pode_ver_carreira(usuario_id, carreira_id):
    conn = conectar()
    try:
        donos = usuario_repo.donos_da_carreira(conn, carreira_id)
        return not donos or donos == {usuario_id}
    finally:
        conn.close()


def exigir_vaga_de_jogo(usuario_id):
    """`LimiteDeJogos` se a conta já tem LIMITE_JOGOS jogos."""
    if usuario_id is None:
        return
    conn = conectar()
    try:
        if usuario_repo.contar_jogos(conn, usuario_id) >= LIMITE_JOGOS:
            raise LimiteDeJogos()
    finally:
        conn.close()


def definir_dono(simulacao_id, usuario_id):
    """Marca o save recém-criado como do técnico (None = sem contas)."""
    if usuario_id is None:
        return
    conn = conectar()
    try:
        simulacao_repo.definir_dono(conn, simulacao_id, usuario_id)
        conn.commit()
    finally:
        conn.close()
