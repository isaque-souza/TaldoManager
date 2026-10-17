"""Meta da diretoria (v1.0): fixada no início da temporada e exposta na visão."""

from app.db.conexao import conectar
from app.domain import diretoria
from app.services import carreira_service, simulacao_service, temporada_service


def _clube_do_ranking(ranking):
    return next(
        c for c in simulacao_service.listar_clubes() if c["ranking_forca"] == ranking
    )


def _posicao(visao, clube):
    return next(c["posicao"] for c in visao["classificacao"] if c["clube"] == clube)


def test_rodada_a_rodada_nasce_com_a_meta_do_ranking():
    clube = _clube_do_ranking(1)
    sid = temporada_service.iniciar(seed=1, clube_usuario=clube["nome"])

    meta = simulacao_service.carregar_temporada(sid)["meta"]
    assert meta["ranking_forca"] == 1
    assert meta["posicao"] == 1
    assert meta["descricao"] == "Ser campeão"


def test_situacao_acompanha_a_tabela_rodada_a_rodada():
    clube = _clube_do_ranking(10)["nome"]
    sid = temporada_service.iniciar(seed=2, clube_usuario=clube)
    for _ in range(5):
        temporada_service.avancar(sid)

    visao = simulacao_service.carregar_temporada(sid)
    meta = visao["meta"]
    assert meta["posicao_atual"] == _posicao(visao, clube)
    assert meta["situacao"] == diretoria.situacao(meta["posicao_atual"], meta["posicao"])


def test_simular_tudo_com_clube_tem_meta_e_situacao_final():
    clube = _clube_do_ranking(5)["nome"]
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=clube)

    visao = simulacao_service.carregar_temporada(sid)
    assert visao["meta"]["posicao"] == 8
    assert visao["meta"]["posicao_atual"] == _posicao(visao, clube)


def test_sem_clube_dirigido_nao_tem_meta():
    sid = simulacao_service.salvar_temporada(seed=3)
    assert simulacao_service.carregar_temporada(sid)["meta"] is None


def test_meta_fica_fixa_mesmo_se_o_elenco_mudar():
    # gravada no save: mexer no elenco depois não recalcula
    clube = _clube_do_ranking(1)["nome"]
    sid = temporada_service.iniciar(seed=1, clube_usuario=clube)
    conn = conectar()
    with conn:
        conn.execute(
            "UPDATE jogador SET overall = 40 WHERE simulacao_id = ? AND clube_id ="
            " (SELECT id FROM clube WHERE simulacao_id = ? AND nome = ?)",
            (sid, sid, clube),
        )
    conn.close()

    assert simulacao_service.carregar_temporada(sid)["meta"]["posicao"] == 1


def test_save_antigo_sem_meta_continua_abrindo():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube_do_ranking(1)["nome"])
    conn = conectar()
    with conn:
        conn.execute(
            "UPDATE simulacao SET meta_posicao = NULL, ranking_forca = NULL WHERE id = ?",
            (sid,),
        )
    conn.close()

    assert simulacao_service.carregar_temporada(sid)["meta"] is None


def test_nova_temporada_da_carreira_ganha_meta_propria():
    sid = simulacao_service.salvar_temporada(seed=3, clube_usuario=_clube_do_ranking(12)["nome"])

    nova = carreira_service.proxima_temporada(sid)["simulacao_id"]
    meta = simulacao_service.carregar_temporada(nova)["meta"]

    # recalculada com os elencos depois da virada
    assert meta is not None
    assert meta["posicao"] == diretoria.meta_da_temporada(meta["ranking_forca"])
