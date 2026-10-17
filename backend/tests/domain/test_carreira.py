import pytest

from app.domain.carreira import preparar_nova_temporada, seed_da_temporada
from scripts.data_loader import carregar_campeonato


def test_seed_da_temporada_soma_o_numero_da_temporada():
    assert seed_da_temporada(10, 1) == 10
    assert seed_da_temporada(10, 2) == 11
    assert seed_da_temporada(10, 5) == 14


def test_seed_da_temporada_aleatoria_continua_aleatoria():
    assert seed_da_temporada(None, 3) is None


def _finais(campeonato):
    """O "estado final" no formato das tabelas, sem mudança nenhuma."""
    clubes = [{"nome": c.nome, "dinheiro": c.dinheiro} for c in campeonato.clubes]
    jogadores = [
        {
            "nome": j.nome,
            "clube": c.nome,
            "salario": j.salario,
            "contrato_anos": j.contrato_anos,
            "multa_rescisoria": j.multa_rescisoria,
        }
        for c in campeonato.clubes for j in c.jogadores
    ]
    return clubes, jogadores


def test_jogador_transferido_comeca_no_clube_novo():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    a, b = base.clubes[0].nome, base.clubes[1].nome
    vendido = next(j for j in jogadores if j["clube"] == a)
    vendido["clube"] = b

    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    elencos = {c.nome: {j.nome for j in c.jogadores} for c in novo.clubes}

    assert vendido["nome"] not in elencos[a]
    assert vendido["nome"] in elencos[b]
    # ninguém some nem duplica
    total = sum(len(e) for e in elencos.values())
    assert total == len(jogadores)


def test_contrato_e_caixa_sao_herdados():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    clubes[0]["dinheiro"] = -1_234_000      # terminou endividado
    jogadores[0].update(salario=9_999_000, contrato_anos=5,
                        multa_rescisoria=77_000_000)

    novo = preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
    clube = next(c for c in novo.clubes if c.nome == clubes[0]["nome"])
    jogador = next(j for c in novo.clubes for j in c.jogadores
                   if j.nome == jogadores[0]["nome"])

    assert clube.dinheiro == clube.dinheiro_inicial == -1_234_000
    assert (jogador.salario, jogador.contrato_anos,
            jogador.multa_rescisoria) == (9_999_000, 5, 77_000_000)


def test_jogador_fora_da_seed_e_erro_claro():
    base = carregar_campeonato()
    clubes, jogadores = _finais(base)
    jogadores.append({**jogadores[0], "nome": "Jovem da Base"})

    with pytest.raises(ValueError, match="fora da seed"):
        preparar_nova_temporada(carregar_campeonato(), clubes, jogadores)
