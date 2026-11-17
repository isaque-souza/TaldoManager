"""Ajuda da Auditoria 01: threads com roteiro fixo.

Nada aqui muda o código de produção: os ganchos entram por `monkeypatch`
só dentro de cada teste. As esperas têm prazo, então um roteiro que não
acontece falha com uma mensagem em vez de travar a suíte.

Duas falhas diferentes, de propósito (Auditoria 03, achado 6):

- `DefeitoReproduzido`: o comportamento correto NÃO aconteceu. É a única
  falha que os testes `xfail` aceitam (`raises=DefeitoReproduzido`).
- `RoteiroTravado`: o roteiro não aconteceu (espera vencida, barreira
  quebrada, fio que não terminou). O teste não provou nada; o `xfail` não
  aceita essa falha e a suíte fica vermelha.
"""

import threading

ESPERA = 120   # segundos; um roteiro que passa disso travou


class DefeitoReproduzido(AssertionError):
    """O teste afirmou o comportamento correto e ele não aconteceu."""


class RoteiroTravado(Exception):
    """O roteiro das threads não aconteceu; o teste não prova nada.

    De propósito NÃO é `AssertionError`: o `xfail(raises=DefeitoReproduzido)`
    não pode confundir as duas."""


def exigir(condicao, detalhe):
    """`assert` dos testes de reprodução: falha com `DefeitoReproduzido`."""
    if not condicao:
        raise DefeitoReproduzido(detalhe)


class Fio(threading.Thread):
    """Thread com nome (os ganchos olham o nome) que guarda o resultado
    ou a exceção da ação."""

    def __init__(self, nome, acao):
        super().__init__(name=nome, daemon=True)
        self.acao = acao
        self.resultado = None
        self.erro = None

    def run(self):
        try:
            self.resultado = self.acao()
        except BaseException as e:   # noqa: BLE001 — o teste decide o que fazer
            self.erro = e


def esperar(evento, oque, prazo=None):
    if not evento.wait(ESPERA if prazo is None else prazo):
        raise RoteiroTravado(f"o roteiro travou esperando: {oque}")


def nome_do_fio():
    return threading.current_thread().name


def juntar(*fios, prazo=None):
    for f in fios:
        f.join(ESPERA if prazo is None else prazo)
        if f.is_alive():
            raise RoteiroTravado(f"o fio {f.name} não terminou")


def conferir_roteiro(*fios):
    """Falha de roteiro dentro de um fio (espera vencida, barreira quebrada)
    vira `RoteiroTravado` no teste. Outros erros ficam para o teste julgar
    (ex.: a recusa do segundo pedido, quando o R2 for corrigido)."""
    for f in fios:
        if isinstance(f.erro, (RoteiroTravado, threading.BrokenBarrierError)):
            raise RoteiroTravado(f"o roteiro falhou no fio {f.name}: {f.erro!r}") from f.erro
