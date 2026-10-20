"""Ofertas da CPU (v1.7): quando elas chegam. As regras ficam em
`app.domain.ofertas`; aceitar, recusar e contrapropor ficam no
`mercado_service` (que já sabe fazer a venda).

Dois gatilhos, sempre dentro da transação de quem chama:
- `abrir_janela`: a temporada começou ou a rodada 19 foi jogada — ofertas
  pelos jogadores à venda e, às vezes, o assédio a um craque
- `ao_listar`: o técnico pôs alguém na lista com a janela aberta — as ofertas
  por ele chegam na hora

E os negócios entre os clubes da CPU (`app.domain.mercado_cpu`): quem chama
os faz no estado vivo antes de gravá-lo; `registrar_cpu` grava o histórico
e o aviso.

Este módulo não importa outros serviços: o `temporada_service` o chama, e o
`mercado_service` importa o `temporada_service`.
"""

from app.domain import caixa, ofertas
from app.repositories import jogador_repository as jogador_repo
from app.repositories import mensagem_repository as mensagem_repo
from app.repositories import oferta_repository as oferta_repo
from app.repositories import transferencia_repository as transferencia_repo


def _gravar(conn, simulacao_id, rodada, jogador_id, lista):
    for o in lista:
        oferta_repo.inserir(
            conn, simulacao_id, rodada, jogador_id, o.clube.nome, o.valor, o.teto, o.espontanea,
        )


def abrir_janela(conn, simulacao_id, rodada, campeonato, clube_usuario, rodada_msg):
    """A janela de `rodada` abriu. Quem já recebeu oferta nela fica de fora
    (chamar duas vezes não duplica nada)."""

    alvo = next(c for c in campeonato.clubes if c.nome == clube_usuario)
    ids = {r["nome"]: r["id"] for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)}
    ja = oferta_repo.jogadores_com_oferta(conn, simulacao_id, rodada)

    por_jogador = []
    for j in sorted(alvo.jogadores, key=lambda j: (-j.overall, j.nome)):
        if not j.a_venda or ids[j.nome] in ja:
            continue
        lista = ofertas.para_venda(
            j, alvo, campeonato.clubes, ofertas.semente(simulacao_id, rodada, j.nome),
        )
        _gravar(conn, simulacao_id, rodada, ids[j.nome], lista)
        ja.add(ids[j.nome])
        por_jogador.append((j, lista))
    mensagens = [caixa.ofertas_pela_lista(por_jogador)]

    achado = ofertas.assedio(alvo, campeonato.clubes, ofertas.semente(simulacao_id, rodada))
    if achado and ids[achado[0].nome] not in ja:
        jogador, oferta = achado
        _gravar(conn, simulacao_id, rodada, ids[jogador.nome], [oferta])
        mensagens.append(caixa.assedio(jogador, oferta))

    mensagem_repo.inserir(conn, simulacao_id, rodada_msg, mensagens)


def ao_listar(conn, simulacao_id, rodada, campeonato, alvo, jogador, jogador_id):
    """O jogador acabou de entrar na lista com a janela aberta: as ofertas
    chegam na hora — se ele ainda não recebeu nenhuma nesta janela (tirar e
    pôr de novo não sorteia outra vez). Devolve as ofertas novas."""

    if jogador_id in oferta_repo.jogadores_com_oferta(conn, simulacao_id, rodada):
        return []
    lista = ofertas.para_venda(
        jogador, alvo, campeonato.clubes, ofertas.semente(simulacao_id, rodada, jogador.nome),
    )
    _gravar(conn, simulacao_id, rodada, jogador_id, lista)
    mensagem_repo.inserir(conn, simulacao_id, rodada, [
        caixa.ofertas_pela_lista([(jogador, lista)]),
    ])
    return lista


def registrar_cpu(conn, simulacao_id, rodada, negocios, mapa_clubes, alvo, rodada_msg):
    """Grava os negócios da CPU desta janela (já feitos no estado vivo e
    gravados nos jogadores) no histórico de transferências e avisa o
    técnico."""
    if not negocios:
        return
    ids = {r["nome"]: r["id"] for r in jogador_repo.listar_por_simulacao(conn, simulacao_id)}
    for n in negocios:
        transferencia_repo.inserir(
            conn, simulacao_id, rodada, ids[n.jogador.nome],
            mapa_clubes[n.vendedor.nome], mapa_clubes[n.comprador.nome], n.valor,
        )
    mensagem_repo.inserir(conn, simulacao_id, rodada_msg, [caixa.mercado_da_cpu(
        [(n.jogador.nome, n.jogador.overall, n.vendedor.nome, n.comprador.nome, n.valor,
          n.comprador.liga) for n in negocios],
        alvo.liga, alvo.rivais,
    )])
