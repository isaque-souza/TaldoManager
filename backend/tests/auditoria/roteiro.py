"""Ajuda da Auditoria 01: threads com roteiro fixo.

Nada aqui muda o código de produção: os ganchos entram por `monkeypatch`
só dentro de cada teste. As esperas têm prazo, então um roteiro que não
acontece falha com uma mensagem em vez de travar a suíte.
"""

import threading

ESPERA = 120   # segundos; um roteiro que passa disso travou


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


def esperar(evento, oque):
    assert evento.wait(ESPERA), f"o roteiro travou esperando: {oque}"


def nome_do_fio():
    return threading.current_thread().name


def juntar(*fios):
    for f in fios:
        f.join(ESPERA)
        assert not f.is_alive(), f"o fio {f.name} não terminou"
