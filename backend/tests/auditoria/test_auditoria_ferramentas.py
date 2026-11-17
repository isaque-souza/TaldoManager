"""Auditoria 03 — as ferramentas dos testes de reprodução (achado 6).

Um `xfail` de reprodução só pode aceitar a falha do comportamento afirmado
(`DefeitoReproduzido`). Espera vencida, barreira quebrada ou qualquer outra
exceção não provam o defeito e precisam deixar a suíte vermelha.
"""

import re
import subprocess
import sys
import threading
import textwrap
from pathlib import Path

import pytest

from tests.auditoria import test_auditoria_r1_rng as r1
from tests.auditoria import test_auditoria_r2_concorrencia as r2
from tests.auditoria.roteiro import (
    DefeitoReproduzido, Fio, RoteiroTravado, conferir_roteiro, esperar, exigir, juntar,
)

BACKEND = Path(__file__).resolve().parents[2]


def test_espera_vencida_e_roteiro_travado_e_nao_defeito():
    with pytest.raises(RoteiroTravado):
        esperar(threading.Event(), "nada", prazo=0.01)
    assert not issubclass(RoteiroTravado, AssertionError)


def test_fio_que_nao_termina_e_roteiro_travado():
    solta = threading.Event()
    f = Fio("preso", lambda: solta.wait(5))
    f.start()
    try:
        with pytest.raises(RoteiroTravado):
            juntar(f, prazo=0.01)
    finally:
        solta.set()
        f.join(5)


def test_barreira_quebrada_num_fio_vira_roteiro_travado():
    barreira = threading.Barrier(2, timeout=0.01)
    f = Fio("A", barreira.wait)
    f.start()
    f.join(5)
    assert isinstance(f.erro, threading.BrokenBarrierError)
    with pytest.raises(RoteiroTravado):
        conferir_roteiro(f)


def test_outro_erro_num_fio_fica_para_o_teste_julgar():
    f = Fio("B", lambda: (_ for _ in ()).throw(ValueError("recusado")))
    f.start()
    f.join(5)
    conferir_roteiro(f)   # não levanta: pode ser a recusa de um R2 corrigido
    assert isinstance(f.erro, ValueError)


def test_exigir_levanta_defeito_reproduzido():
    exigir(True, "ok")
    with pytest.raises(DefeitoReproduzido, match="detalhe"):
        exigir(False, "detalhe")


@pytest.mark.parametrize("modulo", [r1, r2], ids=["R1", "R2"])
def test_todo_xfail_de_reproducao_tem_strict_e_raises(modulo):
    marcados = []
    for nome in dir(modulo):
        if not nome.startswith("test_"):
            continue
        for m in getattr(getattr(modulo, nome), "pytestmark", []):
            if m.name == "xfail":
                marcados.append(nome)
                assert m.kwargs.get("strict") is True, nome
                assert m.kwargs.get("raises") is DefeitoReproduzido, nome
    assert len(marcados) == (4 if modulo is r1 else 3), marcados


def test_pytest_so_aceita_a_falha_esperada(tmp_path):
    """Roda o pytest de verdade num arquivo à parte: com
    `raises=DefeitoReproduzido`, o defeito conta como xfail; roteiro travado,
    assert comum e erro qualquer contam como falha."""
    arquivo = tmp_path / "test_semantica.py"
    arquivo.write_text(textwrap.dedent('''
        import pytest
        from tests.auditoria.roteiro import DefeitoReproduzido, RoteiroTravado, exigir

        marca = pytest.mark.xfail(strict=True, raises=DefeitoReproduzido, reason="x")

        @marca
        def test_defeito():
            exigir(False, "o defeito")

        @marca
        def test_roteiro_travado():
            raise RoteiroTravado("espera vencida")

        @marca
        def test_assert_comum():
            assert False

        @marca
        def test_erro_qualquer():
            raise KeyError("x")
    '''), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rfx",
         "--rootdir", str(tmp_path), str(arquivo)],
        capture_output=True, text=True, timeout=120, cwd=tmp_path,
        env={"PYTHONPATH": str(BACKEND), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    saida = r.stdout + r.stderr
    assert "3 failed, 1 xfailed" in saida, saida
    # cada teste no seu lugar (2ª revisão: a contagem sozinha não prova qual)
    def nomes(rotulo):
        return set(re.findall(rf"^{rotulo} \S*::(\w+)", saida, re.MULTILINE))
    assert nomes("XFAIL") == {"test_defeito"}, saida
    assert nomes("FAILED") == {"test_roteiro_travado", "test_assert_comum", "test_erro_qualquer"}, saida
