import random
import statistics

from app.domain.partida import Partida
from app.domain.clube import Clube
from app.domain.jogador import Jogador


def _clube_completo(nome, overall=75):
    """Clube com 18 jogadores (2 GK, 6 DEF, 6 MEI, 4 ATA), como no seed."""
    clube = Clube(nome, "Brasil", 1_000_000)

    plano = [
        ("Goleiro", 2),
        ("Defesa", 6),
        ("Meio-Campo", 6),
        ("Atacante", 4),
    ]

    n = 0
    for posicao, qtd in plano:
        for i in range(qtd):
            jogador = Jogador(f"{nome} {posicao} {i}", 25, posicao, overall)
            # 11 como titular, resto como reserva (exercita contratar_reserva)
            if n < 11:
                clube.contratar_jogador(jogador)
            else:
                clube.contratar_reserva(jogador)
            n += 1

    return clube


def test_criar_partida():
    clube1 = Clube("FC Taldo", "Brasil", 1000000)
    clube2 = Clube("Real Taldo", "Brasil", 1000000)

    partida = Partida(clube1, clube2)

    assert partida.clube1 == clube1
    assert partida.clube2 == clube2
    assert partida.resultado is None
    assert partida.gols_c1 == 0
    assert partida.gols_c2 == 0


def test_simular_partida_funciona():
    clube1 = Clube("FC Taldo", "Brasil", 1000000)
    clube2 = Clube("Real Taldo", "Brasil", 1000000)

    partida = Partida(clube1, clube2)
    partida.simular_partida()

    assert partida.resultado is not None
    assert partida.gols_c1 >= 0
    assert partida.gols_c2 >= 0
    assert isinstance(partida.eventos, list)


# ---------------------------------------------------------------------------
# Bug 4: clube.jogadores nao pode ser corrompido pelas substituicoes
# ---------------------------------------------------------------------------

def test_elenco_fixo_nao_muda_ao_longo_de_varias_partidas():
    random.seed(1)

    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    elenco_casa = set(id(j) for j in casa.jogadores)
    elenco_fora = set(id(j) for j in fora.jogadores)

    for _ in range(20):
        Partida(casa, fora).simular_partida()
        Partida(fora, casa).simular_partida()

    # sem duplicatas e sem perder ninguem
    assert len(casa.jogadores) == 18
    assert len(fora.jogadores) == 18
    assert set(id(j) for j in casa.jogadores) == elenco_casa
    assert set(id(j) for j in fora.jogadores) == elenco_fora


def test_substituicao_troca_apenas_na_escalacao():
    random.seed(0)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()
    partida.estatisticas = partida.criar_estatisticas()

    xi_antes = list(casa.titulares)
    partida.realizar_substituicao(casa, minuto=70)

    # elenco fixo intacto
    assert len(casa.jogadores) == 18
    assert len(set(id(j) for j in casa.jogadores)) == 18
    # titulares + reservas continuam particionando o elenco
    assert len(casa.titulares) == 11
    assert set(id(j) for j in casa.titulares + casa.reservas) == set(
        id(j) for j in casa.jogadores
    )
    # exatamente uma troca
    saiu = [j for j in xi_antes if j not in casa.titulares]
    entrou = [j for j in casa.titulares if j not in xi_antes]
    assert len(saiu) == 1 and len(entrou) == 1
    assert saiu[0].posicao == entrou[0].posicao
    assert saiu[0] in casa.reservas


def test_expulsao_nao_bane_o_jogador_das_proximas_partidas():
    # bug: `expulso` só era limpo para quem começava jogando; um titular que
    # levava vermelho ficava fora de `disponiveis` em escalar_time para
    # sempre (nunca voltava a ser titular -> nunca era "des-expulso").
    random.seed(9)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    Partida(casa, fora).simular_partida()

    zagueiro = next(j for j in casa.titulares if j.posicao == "Defesa")
    zagueiro.expulso = True
    partidas_antes = zagueiro.partidas

    apareceu = 0
    for _ in range(10):
        # isola o teste: lesão e suspensão são mecânicas à parte
        zagueiro.rodadas_lesao = 0
        zagueiro.jogos_suspensao = 0
        Partida(casa, fora).simular_partida()
        if zagueiro in casa.titulares or zagueiro in casa.reservas:
            apareceu += 1

    assert apareceu == 10                       # nunca some do elenco
    assert not zagueiro.expulso                 # flag foi limpa
    assert zagueiro.partidas > partidas_antes   # voltou a jogar


def test_goleiro_nunca_e_substituido_no_meio_da_partida():
    random.seed(3)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    for _ in range(30):
        Partida(casa, fora).simular_partida()

    # o titular pode variar entre rodadas (fadiga), mas dentro de uma partida
    # so um goleiro joga -> a soma de jogos dos goleiros bate com o total de
    # partidas (sem contagem dupla por substituicao de goleiro)
    for clube in (casa, fora):
        goleiros = [j for j in clube.jogadores if j.posicao == "Goleiro"]
        assert sum(g.partidas for g in goleiros) == 30


# ---------------------------------------------------------------------------
# Fadiga: reduzir_energia estava sem efeito -> ninguem cansava, sem rodizio
# ---------------------------------------------------------------------------

def test_fadiga_faz_energia_cair_durante_a_partida():
    random.seed(2)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    Partida(casa, fora).simular_partida()

    # pelo menos alguem em campo terminou a partida com menos de 100 de energia
    # (a medicao e antes da recuperacao pos-jogo do proximo Partida)
    energias = [j.energia for j in casa.titulares + fora.titulares]
    assert min(energias) < 100


def test_fadiga_forca_rodizio_de_elenco():
    random.seed(2)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    for _ in range(15):
        Partida(casa, fora).simular_partida()
        Partida(fora, casa).simular_partida()

    for clube in (casa, fora):
        jogaram = [j for j in clube.jogadores if j.partidas > 0]
        # sem fadiga funcionando, seriam sempre os mesmos 11
        assert len(jogaram) > 11


# ---------------------------------------------------------------------------
# Bug 2: reservas que nao entram nao podem pontuar
# ---------------------------------------------------------------------------

def test_criar_estatisticas_so_inclui_titulares():
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()

    stats = partida.criar_estatisticas()

    assert len(stats) == 22
    for reserva in casa.reservas + fora.reservas:
        assert reserva not in stats


def test_reservas_no_banco_nao_ganham_jogo_nem_nota():
    random.seed(7)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    Partida(casa, fora).simular_partida()

    for clube in (casa, fora):
        jogaram = [j for j in clube.jogadores if j.partidas > 0]
        # no máximo o XI + 5 substituições
        assert len(jogaram) <= 16
        # quem não jogou continua zerado
        for jogador in clube.jogadores:
            if jogador.partidas == 0:
                assert jogador.soma_nota == 0.0
                assert jogador.melhor_em_campo == 0


def test_soma_de_melhor_em_campo_bate_com_numero_de_partidas():
    random.seed(11)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    for _ in range(10):
        Partida(casa, fora).simular_partida()

    total_mvp = sum(
        j.melhor_em_campo
        for clube in (casa, fora)
        for j in clube.jogadores
    )
    assert total_mvp == 10


# ---------------------------------------------------------------------------
# Bug 3: clean sheet só para o goleiro que estava em campo
# ---------------------------------------------------------------------------

def test_clean_sheet_vai_so_para_o_goleiro_titular():
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()

    partida.gols_c1 = 2
    partida.gols_c2 = 0  # Casa não sofreu -> clean sheet do goleiro da Casa

    partida.atualizar_clean_sheet()

    gk_casa_titular = next(j for j in casa.titulares if j.posicao == "Goleiro")
    gk_casa_reserva = next(j for j in casa.reservas if j.posicao == "Goleiro")
    gk_fora_titular = next(j for j in fora.titulares if j.posicao == "Goleiro")

    assert gk_casa_titular.clean_sheets == 1
    assert gk_casa_reserva.clean_sheets == 0   # backup no banco: nada
    assert gk_fora_titular.clean_sheets == 0   # sofreu 2 gols


def test_clean_sheet_do_visitante_nao_infla_o_elenco():
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()

    partida.gols_c1 = 0  # visitante (Fora) não sofreu
    partida.gols_c2 = 1

    partida.atualizar_clean_sheet()

    goleiros_fora = [j for j in fora.jogadores if j.posicao == "Goleiro"]
    assert sum(g.clean_sheets for g in goleiros_fora) == 1


def test_clean_sheets_nunca_passam_das_partidas_jogadas():
    random.seed(5)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    for _ in range(38):
        Partida(casa, fora).simular_partida()

    for clube in (casa, fora):
        for jogador in clube.jogadores:
            assert jogador.clean_sheets <= jogador.partidas


# ---------------------------------------------------------------------------
# Mando de campo + força do time influenciando o placar
# ---------------------------------------------------------------------------

def test_mando_de_campo_da_vantagem_ao_mandante():
    casa = _clube_completo("Casa", overall=80)
    fora = _clube_completo("Fora", overall=80)

    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()

    # times identicos: o mandante tem força maior por causa do mando
    assert partida.forca_em_campo(casa) > partida.forca_em_campo(fora)
    assert partida.forca_em_campo(casa) - partida.forca_em_campo(fora) == (
        Partida.MANDO_DE_CAMPO
    )


def test_calcular_posse_favorece_o_time_mais_forte():
    forte = _clube_completo("Forte", overall=88)
    fraco = _clube_completo("Fraco", overall=70)

    partida = Partida(fraco, forte)  # forte joga fora, sem mando
    fraco.escalar_time()
    forte.escalar_time()
    partida.calcular_posse()

    assert partida.posse_c1 + partida.posse_c2 == 100
    assert partida.posse_c2 > 60  # o time forte domina a posse


def test_fator_ataque_reflete_a_diferenca_de_forca():
    forte = _clube_completo("Forte", overall=90)
    fraco = _clube_completo("Fraco", overall=68)

    partida = Partida(forte, fraco)
    forte.escalar_time()
    fraco.escalar_time()

    assert partida.fator_ataque(forte) > 1.0
    assert partida.fator_ataque(fraco) < 1.0
    # clamp
    assert partida.fator_ataque(forte) <= 1.7
    assert partida.fator_ataque(fraco) >= 0.55


def test_time_mais_forte_vence_a_maioria_dos_confrontos():
    random.seed(20)
    forte = _clube_completo("Forte", overall=85)
    fraco = _clube_completo("Fraco", overall=72)

    v_forte = v_fraco = empates = 0
    for i in range(60):
        # alterna o mando para isolar o efeito da força
        casa, visitante = (forte, fraco) if i % 2 == 0 else (fraco, forte)
        p = Partida(casa, visitante)
        p.simular_partida()
        g_forte = p.gols_c1 if casa is forte else p.gols_c2
        g_fraco = p.gols_c1 if casa is fraco else p.gols_c2
        if g_forte > g_fraco:
            v_forte += 1
        elif g_fraco > g_forte:
            v_fraco += 1
        else:
            empates += 1

    assert v_forte > v_fraco * 2


def test_mando_de_campo_melhora_o_aproveitamento_em_casa():
    # dois times idênticos: só o mando separa. O efeito é pequeno num jogo
    # só (e ruído como suspensão pode virar um seed), então agrega vários.
    pontos_casa = pontos_fora = 0
    for seed in range(4):
        random.seed(seed)
        a = _clube_completo("A", overall=80)
        b = _clube_completo("B", overall=80)
        for i in range(40):
            casa, visitante = (a, b) if i % 2 == 0 else (b, a)
            p = Partida(casa, visitante)
            p.simular_partida()
            if p.gols_c1 > p.gols_c2:
                pontos_casa += 3
            elif p.gols_c1 < p.gols_c2:
                pontos_fora += 3
            else:
                pontos_casa += 1
                pontos_fora += 1

    assert pontos_casa > pontos_fora


# ---------------------------------------------------------------------------
# Tática: entra em fator_ataque e muda o volume de gols dos dois lados
# ---------------------------------------------------------------------------

def test_fator_ataque_responde_a_tatica():
    casa = _clube_completo("Casa", overall=80)
    fora = _clube_completo("Fora", overall=80)
    partida = Partida(casa, fora)
    casa.escalar_time()
    fora.escalar_time()

    base = partida.fator_ataque(casa)

    casa.tatica = "ofensivo"
    assert partida.fator_ataque(casa) > base       # ataca com mais perigo

    casa.tatica = "defensivo"
    assert partida.fator_ataque(casa) < base

    # defender contra um time defensivo rende menos
    casa.tatica = "equilibrado"
    fora.tatica = "defensivo"
    assert partida.fator_ataque(casa) < base


def _placar_da_temporada(seed, tatica_casa):
    random.seed(seed)
    casa = _clube_completo("Casa", overall=80)
    fora = _clube_completo("Fora", overall=80)
    casa.tatica = tatica_casa

    gp = gc = 0
    for i in range(38):
        mandante, visitante = (casa, fora) if i % 2 == 0 else (fora, casa)
        p = Partida(mandante, visitante)
        p.simular_partida()
        gp += p.gols_c1 if mandante is casa else p.gols_c2
        gc += p.gols_c1 if visitante is casa else p.gols_c2
    return gp, gc


def test_xi_preferido_joga_muito_mas_o_rodizio_sobrevive():
    random.seed(7)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    # XI preferido = 11 jogadores fixos da Casa (o 1º de cada posição)
    def primeiros(posicao, n):
        return [j for j in casa.jogadores if j.posicao == posicao][:n]

    xi = (
        primeiros("Goleiro", 1)
        + primeiros("Defesa", 4)
        + primeiros("Meio-Campo", 3)
        + primeiros("Atacante", 3)
    )
    casa.xi_preferido = set(xi)

    for _ in range(38):
        Partida(casa, fora).simular_partida()
        Partida(fora, casa).simular_partida()

    de_linha = [j for j in xi if j.posicao != "Goleiro"]
    # os preferidos são o núcleo do time (jogam a grande maioria dos 76)...
    assert all(j.partidas >= 45 for j in de_linha)
    # ...mas ninguém de linha joga tudo — fadiga, suspensão e lesão rodam o time
    assert any(j.partidas < 76 for j in de_linha)
    # e algum reserva foi acionado
    reservas = [j for j in casa.jogadores if j not in xi]
    assert any(j.partidas > 0 for j in reservas)


def test_ofensivo_faz_mais_gols_pro_e_contra_que_defensivo():
    seeds = range(6)
    ofe = [_placar_da_temporada(s, "ofensivo") for s in seeds]
    defe = [_placar_da_temporada(s, "defensivo") for s in seeds]

    gp_ofe = sum(g[0] for g in ofe)
    gp_def = sum(g[0] for g in defe)
    gc_ofe = sum(g[1] for g in ofe)
    gc_def = sum(g[1] for g in defe)

    # ofensivo: mais gols marcados E mais sofridos (troca solidez por perigo)
    assert gp_ofe > gp_def
    assert gc_ofe > gc_def


# ---------------------------------------------------------------------------
# peso_gol + fórmula de nota: artilharia concentrada e notas menos comprimidas
# ---------------------------------------------------------------------------

def _clube_com_craque(nome):
    """Elenco médio (overall 78) com um atacante muito acima (overall 90)."""
    clube = _clube_completo(nome, overall=78)
    atacante = next(j for j in clube.jogadores if j.posicao == "Atacante")
    atacante.overall = 90
    atacante.nome = f"{nome} Craque"
    return clube, atacante


def test_o_craque_concentra_os_gols_do_time():
    # agrega vários seeds: a artilharia individual é ruidosa jogo a jogo
    gols_craque = gols_time = 0
    for seed in range(4):
        random.seed(seed)
        casa, craque = _clube_com_craque("Casa")
        fora = _clube_completo("Fora", overall=78)
        for _ in range(38):
            Partida(casa, fora).simular_partida()
        gols_craque += craque.gols
        gols_time += casa.gols_marcados

    assert gols_craque >= 55                      # ~14+/temporada
    assert gols_craque / gols_time > 0.25         # é o dono do ataque


def test_bom_atacante_tem_media_de_nota_alta_numa_temporada():
    random.seed(31)
    casa, craque = _clube_com_craque("Casa")
    fora = _clube_completo("Fora", overall=74)

    for _ in range(38):
        Partida(casa, fora).simular_partida()

    # a fórmula não deve mais comprimir todo mundo perto de 6.0-6.5
    assert craque.nota_media() > 7.3


def test_a_maioria_dos_jogadores_fica_perto_de_6():
    random.seed(32)
    casa = _clube_completo("Casa", overall=78)
    fora = _clube_completo("Fora", overall=78)

    for _ in range(38):
        Partida(casa, fora).simular_partida()
        Partida(fora, casa).simular_partida()

    notas = [
        j.nota_media()
        for clube in (casa, fora)
        for j in clube.jogadores
        if j.partidas >= 10
    ]
    # 6.0 continua sendo "jogou, sem se destacar"
    assert 5.8 < statistics.median(notas) < 7.0


# ---------------------------------------------------------------------------
# Fase 2b: snapshot da partida (timeline + escalação com nota)
# ---------------------------------------------------------------------------

def test_calcular_notas_grava_a_nota_de_cada_jogador():
    random.seed(40)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    partida.simular_partida()

    # antes a nota ficava só em jogador.soma_nota; agora tem que estar no dict
    notas = [s["nota"] for s in partida.estatisticas.values()]
    assert all(0 <= n <= 10 for n in notas)
    assert any(n != 6.0 for n in notas)


def test_resumo_escalacao_cobre_quem_jogou_e_bate_o_placar():
    random.seed(41)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    partida.simular_partida()

    atuacoes = partida.resumo_escalacao()

    # uma linha por jogador em campo (>= 22, mais os substitutos)
    assert len(atuacoes) == len(partida.estatisticas)
    assert len(atuacoes) >= 22

    # exatamente 11 titulares por lado
    for clube in (casa, fora):
        titulares = [
            a for a in atuacoes if a["clube"] == clube.nome and a["titular"]
        ]
        assert len(titulares) == 11

    # a soma de gols das atuações reproduz o placar
    gols_casa = sum(a["gols"] for a in atuacoes if a["clube"] == "Casa")
    gols_fora = sum(a["gols"] for a in atuacoes if a["clube"] == "Fora")
    assert (gols_casa, gols_fora) == (partida.gols_c1, partida.gols_c2)

    # substituto tem entrou_min preenchido e não é titular
    for a in atuacoes:
        if a["entrou_min"] is not None:
            assert a["titular"] is False


def test_resumo_eventos_em_ordem_e_com_clube():
    random.seed(42)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    partida = Partida(casa, fora)
    partida.simular_partida()

    eventos = partida.resumo_eventos()
    minutos = [e["minuto"] for e in eventos]
    assert minutos == sorted(minutos)

    gols = [e for e in eventos if e["tipo"] in ("gol", "penalti")]
    assert len(gols) == partida.gols_c1 + partida.gols_c2
    for e in eventos:
        assert e["clube"] in ("Casa", "Fora")
        if e["tipo"] == "substituicao":
            assert e["detalhe"] and e["detalhe"].startswith("sai ")


# ---------------------------------------------------------------------------
# Acréscimos e pênaltis defendidos (v0.6)
# ---------------------------------------------------------------------------

def test_acrescimos_estendem_a_partida():
    random.seed(1)
    casa = _clube_completo("Casa")
    fora = _clube_completo("Fora")

    minuto_maximo = 0
    for _ in range(20):
        p = Partida(casa, fora)
        p.simular_partida()
        assert 1 <= p.acrescimos <= 5
        if p.eventos:
            minuto_maximo = max(minuto_maximo, max(e["minuto"] for e in p.eventos))

    assert minuto_maximo > 90    # algo aconteceu nos acréscimos


def test_penalti_tem_tres_desfechos_e_as_contas_batem():
    import contextlib
    import io

    from scripts.data_loader import carregar_campeonato

    random.seed(3)
    camp = carregar_campeonato()
    with contextlib.redirect_stdout(io.StringIO()):
        while camp.rodada <= len(camp.calendario):
            camp.jogar_rodada()

    eventos = [e for p in camp.partidas_jogadas for e in p["eventos"]]
    convertidos = sum(1 for e in eventos if e["tipo"] == "penalti")
    perdidos = sum(1 for e in eventos if e["tipo"] == "penalti_perdido")
    defendidos = sum(1 for e in eventos if e["tipo"] == "penalti_defendido")

    assert defendidos > 0, "uma temporada sem nenhum pênalti defendido?"

    jogadores = [j for c in camp.clubes for j in c.jogadores]
    assert sum(j.penaltis for j in jogadores) == convertidos
    assert sum(j.penaltis_perdidos for j in jogadores) == perdidos + defendidos


def test_chutes_no_gol_e_escanteios_sao_contados():
    random.seed(2)
    casa = _clube_completo("Casa", overall=82)
    fora = _clube_completo("Fora", overall=78)

    total_escanteios = 0
    for _ in range(10):
        p = Partida(casa, fora)
        p.simular_partida()

        # chutes no gol nunca passam do total de finalizações
        assert p.finalizacoes_gol_c1 <= p.finalizacoes_c1
        assert p.finalizacoes_gol_c2 <= p.finalizacoes_c2
        # gols de bola rolando saem de um chute no gol (pênalti não conta aqui)
        penaltis = sum(1 for e in p.eventos if e["tipo"] == "penalti")
        assert p.gols_c1 + p.gols_c2 <= (
            p.finalizacoes_gol_c1 + p.finalizacoes_gol_c2 + penaltis
        )

        assert p.escanteios_c1 >= 0 and p.escanteios_c2 >= 0
        total_escanteios += p.escanteios_c1 + p.escanteios_c2

    assert total_escanteios > 0            # houve escanteios nos 10 jogos


def test_quem_sai_nao_volta_a_campo():
    # a substituição automática não escolhe quem já jogou e saiu (inclusive
    # quem o técnico tirou: no 46' tira um meia; ele não pode voltar)
    for seed in range(60):
        random.seed(seed)
        c1, c2 = _clube_completo("A"), _clube_completo("B")
        partida = Partida(c1, c2)
        meia = next(j for j in c1.jogadores if j.posicao == "Meio-Campo")
        reserva = next(j for j in c1.jogadores if j.posicao == "Meio-Campo" and j is not meia)
        partida.decisoes = [{"minuto": 46, "clube": "A", "sai": meia.nome, "entra": reserva.nome}]
        c1.xi_preferido = {meia}   # garante que ele começa jogando
        partida.simular_partida()

        jogaram = set(partida.titulares_iniciais)
        for troca in partida.substituicoes_log:
            assert troca["entra"] not in jogaram, (seed, troca["entra"].nome)
            jogaram.add(troca["entra"])
