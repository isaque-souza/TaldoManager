"""Jogo ao vivo (v1.1): acréscimos gravados e os gols da rodada por minuto."""

from app.services import simulacao_service, temporada_service


def _clube():
    return simulacao_service.listar_clubes()[0]["nome"]


def test_partida_grava_os_acrescimos_de_1_a_5():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    res = temporada_service.avancar(sid)
    for r in res["resultados"]:
        det = simulacao_service.detalhe_partida(sid, r["partida_id"])
        assert 1 <= det["partida"]["acrescimos"] <= 5
        # nenhum lance passa do fim do jogo
        assert all(e["minuto"] <= 90 + det["partida"]["acrescimos"] for e in det["eventos"])


def test_ao_vivo_traz_os_jogos_da_rodada_com_os_gols_batendo_o_placar():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    res = temporada_service.avancar(sid)

    av = simulacao_service.ao_vivo(sid, 1)
    assert av["rodada"] == 1
    assert {p["partida_id"] for p in av["partidas"]} == {r["partida_id"] for r in res["resultados"]}
    for p in av["partidas"]:
        do_mandante = sum(g["clube"] == p["mandante"] for g in p["gols"])
        do_visitante = sum(g["clube"] == p["visitante"] for g in p["gols"])
        assert (do_mandante, do_visitante) == (p["gols_mandante"], p["gols_visitante"])
        minutos = [g["minuto"] for g in p["gols"]]
        assert minutos == sorted(minutos)


def test_ao_vivo_de_rodada_nao_jogada_vem_vazio_e_simulacao_inexistente_none():
    sid = temporada_service.iniciar(seed=5, clube_usuario=_clube())
    assert simulacao_service.ao_vivo(sid, 3)["partidas"] == []
    assert simulacao_service.ao_vivo(999_999, 1) is None
