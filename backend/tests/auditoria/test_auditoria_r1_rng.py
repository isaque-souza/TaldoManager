"""Auditoria 01 — R1: o gerador aleatório é o `random` global do processo.

As rotas são `def` síncronas: o FastAPI roda cada uma numa thread do pool,
então duas requisições correm juntas no mesmo processo e no mesmo `random`.
`avancar` põe a corrente do save no `random` (`restaurar_estado`) e joga;
as leituras (`proxima_rodada`, `pre_jogo`, mercado, transmissão) fazem
`getstate` → põem a corrente do save delas → `setstate` de volta.

Os testes intercalam as duas threads num roteiro fixo (com `Event`, sem
depender da sorte do escalonador):

1. A restaura o save dele (o `random` fica com a corrente de A) e para.
2. B entra numa leitura de OUTRO save: guarda a corrente de A (`getstate`),
   põe a do save dele e para ali dentro.
3. A segue: sorteia a semente da partida do técnico e joga o primeiro jogo
   da rodada com o `random` que está no processo — o de B — e para.
4. B termina: o `finally` devolve ao `random` a foto do passo 2.
5. A termina a rodada.

Esse é um entrelaçamento que o escalonador de threads pode produzir sozinho
(o GIL troca de thread a cada ~5 ms; uma rodada leva centenas de ms).

Os testes que mostram o defeito estão em `xfail(strict=True)`: eles afirmam
o comportamento correto, falham hoje e, quando o R1 for corrigido, passam —
o `strict` faz a suíte acusar, para tirar a marca. Para ver a diferença
encontrada: `pytest tests/auditoria --runxfail`.
"""

import threading

import pytest

from app.domain.partida import Partida
from app.services import simulacao_service, temporada_service, transmissao_service
from tests.auditoria.roteiro import Fio, esperar, juntar, nome_do_fio

R1 = (
    "R1 reproduzido: uma leitura de outro save, no meio da rodada, troca o "
    "random global e a rodada sai diferente da mesma seed jogada sozinha"
)


def _clubes():
    clubes = simulacao_service.listar_clubes()
    return clubes[0]["nome"], clubes[1]["nome"]


def _placares(res):
    return [
        (r["mandante"], r["visitante"], r["gols_mandante"], r["gols_visitante"])
        for r in res["resultados"]
    ]


def _minha(res):
    meu = res["clube_usuario"]
    return next(r for r in res["resultados"] if meu in (r["mandante"], r["visitante"]))


def _intercalar(acao_a, acao_b):
    """Roda `acao_a` (fio "A") e `acao_b` (fio "B") no roteiro do docstring
    do módulo. Devolve os dois fios."""

    a_restaurou, b_dentro, a_jogou, b_saiu = (threading.Event() for _ in range(4))
    restaurar_original = temporada_service.restaurar_estado
    simular_original = Partida.simular_partida

    def restaurar(campeonato, blob):
        restaurar_original(campeonato, blob)
        if nome_do_fio() == "A" and not a_restaurou.is_set():
            a_restaurou.set()                       # passo 1
            esperar(b_dentro, "B entrar na leitura")
        elif nome_do_fio() == "B" and not b_dentro.is_set():
            b_dentro.set()                          # passo 2
            esperar(a_jogou, "A jogar o primeiro jogo")

    def simular(self):
        r = simular_original(self)
        if nome_do_fio() == "A" and not a_jogou.is_set():
            a_jogou.set()                           # passo 3
            esperar(b_saiu, "B sair da leitura")
        return r

    def b():
        try:
            return acao_b()
        finally:
            b_saiu.set()                            # passo 4

    # MonkeyPatch próprio: os ganchos saem no fim do roteiro, e o banco
    # temporário do conftest (no `monkeypatch` do teste) fica
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(temporada_service, "restaurar_estado", restaurar)
        mp.setattr(Partida, "simular_partida", simular)

        fio_a, fio_b = Fio("A", acao_a), Fio("B", b)
        fio_a.start()
        esperar(a_restaurou, "A restaurar o save")
        fio_b.start()
        juntar(fio_a, fio_b)
    for f in (fio_a, fio_b):
        if f.erro:
            raise f.erro
    # o roteiro aconteceu inteiro (senão o teste não prova nada)
    assert a_restaurou.is_set() and b_dentro.is_set() and a_jogou.is_set()
    return fio_a, fio_b


# ---------------------------------------------------------------------------
# controles: sem sobreposição, tudo bate (o método não inventa diferença)
# ---------------------------------------------------------------------------

def test_controle_mesma_seed_da_a_mesma_rodada():
    meu, outro = _clubes()
    x1 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    x2 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)

    ref = temporada_service.avancar(x1)
    # uma leitura de outro save ANTES (sem sobrepor) não muda nada
    temporada_service.pre_jogo(y)
    assert _placares(temporada_service.avancar(x2)) == _placares(ref)


def test_controle_leitura_em_outra_thread_sem_sobrepor_nao_muda_nada():
    meu, outro = _clubes()
    x1 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    x2 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)
    ref = temporada_service.avancar(x1)

    b = Fio("B", lambda: temporada_service.pre_jogo(y))
    b.start()
    juntar(b)
    a = Fio("A", lambda: temporada_service.avancar(x2))
    a.start()
    juntar(a)
    assert a.erro is None and b.erro is None
    assert _placares(a.resultado) == _placares(ref)


# ---------------------------------------------------------------------------
# R1: leitura de outro save no meio da rodada
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=R1)
def test_r1_pre_jogo_de_outro_save_no_meio_da_rodada_muda_o_resultado():
    meu, outro = _clubes()
    x1 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    x2 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)
    ref = temporada_service.avancar(x1)

    a, _ = _intercalar(
        lambda: temporada_service.avancar(x2),
        lambda: temporada_service.pre_jogo(y),
    )

    diferentes = [
        (r, i) for r, i in zip(_placares(ref), _placares(a.resultado)) if r != i
    ]
    assert not diferentes, (
        f"{len(diferentes)} de {len(_placares(ref))} jogos mudaram "
        f"(referência → intercalado): {diferentes}"
    )


@pytest.mark.xfail(strict=True, reason=R1)
def test_r1_a_corrente_errada_fica_gravada_e_muda_as_rodadas_seguintes():
    """`avancar` grava `random.getstate()` no blob no fim da rodada: depois
    de uma interferência, as rodadas seguintes — jogadas sem ninguém por
    perto — também saem diferentes da mesma seed."""
    meu, outro = _clubes()
    x1 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    x2 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)
    temporada_service.avancar(x1)
    _intercalar(
        lambda: temporada_service.avancar(x2),
        lambda: temporada_service.pre_jogo(y),
    )
    # aqui os ganchos já saíram: daqui em diante, cada save joga sozinho
    seguintes = []
    for _ in range(3):   # rodadas 2 a 4, cada save sozinho
        r1, r2 = temporada_service.avancar(x1), temporada_service.avancar(x2)
        seguintes.append(sum(a != b for a, b in zip(_placares(r1), _placares(r2))))
    assert seguintes == [0, 0, 0], f"jogos diferentes nas rodadas 2, 3 e 4: {seguintes}"


@pytest.mark.xfail(strict=True, reason=R1)
def test_r1_proxima_rodada_de_outro_save_no_meio_da_rodada_muda_o_resultado():
    """A tela da rodada (`GET /rodadas/proxima`) é a leitura mais comum."""
    meu, outro = _clubes()
    x1 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    x2 = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)
    ref = temporada_service.avancar(x1)

    a, _ = _intercalar(
        lambda: temporada_service.avancar(x2),
        lambda: temporada_service.proxima_rodada(y),
    )
    assert _placares(a.resultado) == _placares(ref)


@pytest.mark.xfail(strict=True, reason=R1)
def test_r1_o_jogo_gravado_deixa_de_ser_o_que_a_transmissao_mostrou():
    """O invariante de `test_transmissao.py`: sem decisões, a transmissão é
    exatamente a partida que vale. Com outra leitura no meio da rodada, o
    técnico assiste a um jogo e o banco grava outro."""
    meu, outro = _clubes()
    x = temporada_service.iniciar(seed=5, clube_usuario=meu)
    y = temporada_service.iniciar(seed=99, clube_usuario=outro)
    t = transmissao_service.iniciar(x)

    a, _ = _intercalar(
        lambda: temporada_service.avancar(x),
        lambda: temporada_service.pre_jogo(y),
    )
    minha = _minha(a.resultado)
    gravado = [minha["gols_mandante"], minha["gols_visitante"]]
    det = simulacao_service.detalhe_partida(x, minha["partida_id"])
    eventos_gravados = [(e["minuto"], e["tipo"], e["jogador"]) for e in det["eventos"]]
    eventos_transmitidos = [(e["minuto"], e["tipo"], e["jogador"]) for e in t["eventos"]]

    assert (gravado, eventos_gravados) == (t["minutos"][-1]["placar"], eventos_transmitidos), (
        f"transmissão {t['minutos'][-1]['placar']} × gravado {gravado}; "
        f"eventos transmitidos {len(eventos_transmitidos)}, gravados {len(eventos_gravados)}"
    )


def test_controle_transmissao_sem_interferencia_e_o_jogo_gravado():
    meu, _ = _clubes()
    x = temporada_service.iniciar(seed=5, clube_usuario=meu)
    t = transmissao_service.iniciar(x)
    minha = _minha(temporada_service.avancar(x))
    assert t["minutos"][-1]["placar"] == [minha["gols_mandante"], minha["gols_visitante"]]
