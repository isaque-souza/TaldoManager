"""Jogadores sem clube (v1.6).

A seed começa com QUANTOS livres (scripts/gerar_livres.py); na carreira a
lista vive de temporada em temporada (`carreira_service`):

- quem não renova e não acha clube vai para ela (carreira._sair_livre);
- livres envelhecem e se aposentam como todo mundo (sem jogar, caem);
- a CPU contrata livres antes de subir os jovens da base (`cpu_contrata`);
- no fim da virada ela é completada até QUANTOS com livres novos e cortada
  em LIMITE (sobram os melhores).

Três perfis, como no mercado de verdade: veteranos ainda bons que ninguém
renovou, jogadores comuns no auge e jovens que não vingaram onde estavam. O
nível fica na faixa dos reservas da liga — livre bom demais esvaziaria o
mercado entre os clubes.
"""

from app.domain import base, mercado, posicoes
from app.domain.jogador import Jogador

QUANTOS = 50
LIMITE = 70

# perfil -> (fatia dos livres, idades, overall, margem de potencial)
PERFIS = {
    "veterano": (0.30, (30, 35), (70, 80), (0, 0)),
    "auge": (0.45, (23, 29), (64, 76), (0, 4)),
    "jovem": (0.25, (17, 21), (58, 68), (8, 20)),
}

# secundárias possíveis: as vizinhas em campo
VIZINHAS = {
    "Zagueiro": ["Lateral", "Volante"],
    "Lateral": ["Zagueiro", "Ponta", "Meia central"],
    "Volante": ["Zagueiro", "Meia central"],
    "Meia central": ["Volante", "Meia-atacante", "Ponta"],
    "Meia-atacante": ["Meia central", "Segundo atacante", "Ponta"],
    "Ponta": ["Meia-atacante", "Lateral", "Centroavante"],
    "Segundo atacante": ["Meia-atacante", "Centroavante"],
    "Centroavante": ["Segundo atacante", "Ponta"],
}


def secundarias(funcao, rng):
    if funcao == "Goleiro":
        return []
    sorte = rng.random()
    quantas = 2 if sorte < 0.08 else 1 if sorte < 0.38 else 0
    return sorted(rng.sample(VIZINHAS[funcao], quantas))


def gerar(funcao, perfil, proibidos, rng):
    """Um livre (dict, como no livres.json). `proibidos` é atualizado."""
    _, idades, overalls, margem = PERFIS[perfil]
    overall = rng.randint(*overalls)
    return {
        "nome": base.gerar_nome(proibidos, rng),
        "idade": rng.randint(*idades),
        "posicao": posicoes.SETOR[funcao],
        "overall": overall,
        "potencial": min(99, overall + rng.randint(*margem)),
        "funcao": funcao,
        "secundarias": secundarias(funcao, rng),
    }


def para_jogador(dados):
    """O dict de `gerar` (ou do livres.json) como `Jogador`, sem contrato."""
    return Jogador(
        dados["nome"], dados["idade"], dados["posicao"], dados["overall"],
        potencial=dados["potencial"],
        contrato_anos=0,
        funcao=dados["funcao"],
        secundarias=dados["secundarias"],
    )


def ficar_livre(jogador):
    """Sem clube não há contrato nem tempo de casa."""
    jogador.assinar_contrato(0, jogador.salario_referencia(), None)
    jogador.temporadas_no_clube = 0
    jogador.a_venda = False


def dispensar(jogador, clube, livres):
    """O `clube` rescinde com o jogador (v1.7): paga a rescisão (entra nos
    salários) e ele vai para os `livres`. Devolve o custo. Levanta
    `TransferenciaInvalida` se alguma regra impedir."""

    if jogador not in clube.jogadores:
        raise mercado.TransferenciaInvalida(f"{jogador.nome} não joga no {clube.nome}")
    motivo = mercado.motivo_dispensa_bloqueada(clube, jogador)
    if motivo:
        raise mercado.TransferenciaInvalida(motivo)

    custo = mercado.rescisao(jogador)
    mercado.tirar_do_elenco(clube, jogador)
    ficar_livre(jogador)
    livres.append(jogador)
    clube.lancar("despesa_salarios", custo)
    return custo


# ---------------------------------------------------------------------------
# virada da carreira
# ---------------------------------------------------------------------------

def _carente(livres, rng):
    """A posição que mais falta na lista, na proporção do elenco ideal."""
    total = sum(base.COMPOSICAO_IDEAL.values())
    deficit = {
        f: n / total - sum(1 for j in livres if j.funcao == f) / max(1, len(livres))
        for f, n in base.COMPOSICAO_IDEAL.items()
    }
    maior = max(deficit.values())
    return rng.choice([f for f, d in deficit.items() if d == maior])


def _perfil(rng):
    sorte = rng.random()
    for perfil, (fatia, *_) in PERFIS.items():
        if sorte < fatia:
            return perfil
        sorte -= fatia
    return "auge"


def completar(campeonato, nomes_usados, rng):
    """Completa a lista até QUANTOS com livres novos e corta em LIMITE
    (fica quem tem o overall mais alto) — por liga do campeonato (v1.6): a
    lista é uma só, mas cresce com o mundo. `nomes_usados`: nomes que não
    podem se repetir na carreira."""
    livres = campeonato.livres
    ligas = max(1, len(campeonato.ligas))
    proibidos = set(nomes_usados) | {j.nome for j in livres} | {
        j.nome for c in campeonato.clubes for j in c.jogadores
    }
    while len(livres) < QUANTOS * ligas:
        livres.append(para_jogador(
            gerar(_carente(livres, rng), _perfil(rng), proibidos, rng)
        ))
    if len(livres) > LIMITE * ligas:
        livres.sort(key=lambda j: -j.overall)
        del livres[LIMITE * ligas:]


def cpu_contrata(campeonato, clube_usuario, rng):
    """Clubes da CPU com elenco abaixo do tamanho-alvo contratam o melhor
    livre da posição carente — se ele render mais que um jovem da base
    (média do elenco − base.DESCONTO_OVERALL). O resto das vagas a base
    preenche. Sem luvas, como quem chega de graça na virada
    (carreira._sair_livre): a temporada nova começa com o caixa da anterior.
    Devolve os movimentos."""
    movimentos = []
    for clube in campeonato.clubes:
        if clube.nome == clube_usuario:
            continue
        while len(clube.jogadores) < base.TAMANHO_ALVO:
            media = sum(j.overall for j in clube.jogadores) / len(clube.jogadores)
            funcao = base.posicao_carente(clube, rng)
            candidatos = [
                j for j in campeonato.livres
                if j.funcao == funcao
                and j.overall >= round(media) - base.DESCONTO_OVERALL
            ]
            if not candidatos:
                break
            jogador = max(candidatos, key=lambda j: j.overall)
            campeonato.livres.remove(jogador)
            clube.contratar_jogador(jogador)
            jogador.assinar_contrato(
                mercado.CONTRATO_LIVRE_ANOS, jogador.salario_referencia(), None
            )
            movimentos.append({
                "tipo": "chegou_livre",
                "jogador": jogador.nome,
                "clube": clube.nome,
                "posicao": jogador.posicao,
                "idade": jogador.idade,
                "overall": jogador.overall,
                "detalhe": "estava sem clube",
            })
    return movimentos
