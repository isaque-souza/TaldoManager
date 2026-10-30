"""Olheiros da base (v2.0, passo 5): o técnico manda um olheiro para uma
região por 1, 3 ou 6 meses e paga a missão na hora. A cada 30 dias o
olheiro manda um relatório com os jovens que achou (os "indicados"); o
técnico traz para a base quem quiser (precisa de vaga) e o resto some 30
dias depois, quando chega o relatório seguinte.

Cada região tem um perfil: quantos jovens, de que idade, quão prontos
(overall) e quanto espaço para crescer (potencial), a chance de uma joia e
as posições típicas. A régua é a mesma da peneira (`base.gerar_da_peneira`):
o nível da base e a média do elenco. Os nomes e o país vêm da região; a
nacionalidade fica só no jovem (os elencos não têm).

Quantos olheiros podem estar fora ao mesmo tempo depende do nível da base.
Os sorteios são próprios (`base.rng_da_peneira`): não mexem nas partidas.
"""

from datetime import timedelta

from app.domain import base

DURACOES = (1, 3, 6)                    # meses
DIAS_POR_RELATORIO = 30
VALIDADE_INDICADO = timedelta(days=30)  # some com o relatório seguinte
JOIA_EXTRA = (6, 10)                    # pontos a mais de potencial numa joia

# nível da base → olheiros fora ao mesmo tempo
LIMITE = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

# custo_mes, por relatório (mín, máx), idades, overall e margem (somados à
# régua do nível da base), chance de joia, peso extra das posições típicas
REGIOES = {
    "brasil": {
        "nome": "Brasil",
        "de": "do Brasil",
        "perfil": "Muitos jovens, de pontas e meias habilidosos",
        "paises": ["Brasil"],
        "custo_mes": 150_000,
        "por_relatorio": (1, 3),
        "idades": (15, 17),
        "overall": 0,
        "margem": 1,
        "joia": 0.10,
        "funcoes": {"Ponta": 2, "Meia-atacante": 2, "Lateral": 1.5},
        "nomes": ["João", "Pedro", "Gabriel", "Arthur", "Enzo", "Davi", "Kauã",
                  "Ryan", "Vitor", "Igor", "Wesley", "Gustavo", "Luan", "Endrick"],
        "sobrenomes": ["Silva", "Souza", "Santos", "Oliveira", "Ferreira", "Costa",
                       "Rocha", "Lima", "Gomes", "Barbosa", "Ribeiro", "Nascimento",
                       "Cardoso", "Teixeira"],
    },
    "america_do_sul": {
        "nome": "América do Sul",
        "de": "da América do Sul",
        "perfil": "Mais prontos: atacantes e volantes de briga",
        "paises": ["Argentina", "Uruguai", "Colômbia", "Chile", "Paraguai", "Equador"],
        "custo_mes": 200_000,
        "por_relatorio": (1, 2),
        "idades": (16, 18),
        "overall": 2,
        "margem": 0,
        "joia": 0.08,
        "funcoes": {"Centroavante": 2, "Volante": 2, "Meia central": 1.5},
        "nomes": ["Juan", "Santiago", "Matías", "Facundo", "Nicolás", "Agustín",
                  "Thiago", "Joaquín", "Valentín", "Franco", "Sebastián", "Alexis"],
        "sobrenomes": ["González", "Rodríguez", "Fernández", "López", "Martínez",
                       "Gómez", "Díaz", "Álvarez", "Romero", "Suárez", "Acosta",
                       "Benítez"],
    },
    "europa": {
        "nome": "Europa",
        "de": "da Europa",
        "perfil": "Os mais prontos e mais caros, com menos espaço para crescer",
        "paises": ["Portugal", "Espanha", "França", "Itália", "Inglaterra",
                   "Alemanha", "Holanda", "Bélgica"],
        "custo_mes": 350_000,
        "por_relatorio": (1, 2),
        "idades": (16, 18),
        "overall": 4,
        "margem": -3,
        "joia": 0.05,
        "funcoes": {"Zagueiro": 1.5, "Goleiro": 2, "Meia central": 1.5},
        "nomes": ["Luca", "Lorenzo", "Hugo", "Mathis", "Noah", "Finn", "Leon",
                  "Diogo", "Rúben", "Pablo", "Álvaro", "Jude", "Kobbie", "Xavi"],
        "sobrenomes": ["Rossi", "Ricci", "Moreau", "Lefebvre", "Müller", "Schmidt",
                       "de Jong", "Janssens", "Carvalho", "Sousa", "Navarro",
                       "Ruiz", "Clarke", "Hughes"],
    },
    "africa": {
        "nome": "África",
        "de": "da África",
        "perfil": "Crus, mas com mais joias escondidas",
        "paises": ["Nigéria", "Senegal", "Gana", "Costa do Marfim", "Camarões",
                   "Mali", "Marrocos"],
        "custo_mes": 150_000,
        "por_relatorio": (1, 3),
        "idades": (15, 17),
        "overall": -3,
        "margem": 4,
        "joia": 0.18,
        "funcoes": {"Zagueiro": 1.5, "Volante": 1.5, "Centroavante": 1.5, "Ponta": 1.5},
        "nomes": ["Samuel", "Ibrahim", "Moussa", "Kwame", "Yaw", "Sadio", "Ismaïla",
                  "Victor", "Emeka", "Youssef", "Achraf", "Bamba", "Cheikh"],
        "sobrenomes": ["Diallo", "Traoré", "Koné", "Mensah", "Osei", "Okafor",
                       "Adeyemi", "Ndiaye", "Sarr", "Touré", "Mbeki", "Haddad",
                       "Cissé"],
    },
    "asia": {
        "nome": "Ásia",
        "de": "da Ásia",
        "perfil": "A mais barata e a que mais manda nomes, de meias e laterais",
        "paises": ["Japão", "Coreia do Sul", "China", "Arábia Saudita", "Irã", "Austrália"],
        "custo_mes": 80_000,
        "por_relatorio": (2, 3),
        "idades": (15, 17),
        "overall": -3,
        "margem": -1,
        "joia": 0.06,
        "funcoes": {"Meia central": 1.5, "Lateral": 1.5, "Ponta": 1.5},
        "nomes": ["Haruto", "Ren", "Takumi", "Kaoru", "Min-jun", "Seo-jun", "Ji-ho",
                  "Wei", "Hao", "Salem", "Fahad", "Reza", "Mehdi", "Jackson"],
        "sobrenomes": ["Tanaka", "Suzuki", "Mitoma", "Kubo", "Kim", "Park", "Lee",
                       "Wang", "Zhang", "Al-Dawsari", "Al-Shehri", "Taremi",
                       "Rezaei", "Irvine"],
    },
}


class MissaoInvalida(ValueError):
    """Região ou duração que não existem."""


def validar(regiao, meses):
    if regiao not in REGIOES:
        raise MissaoInvalida("Essa região não existe")
    if meses not in DURACOES:
        raise MissaoInvalida("A missão dura 1, 3 ou 6 meses")


def limite(nivel_base):
    return LIMITE[nivel_base]


def custo(regiao, meses):
    """A missão inteira, paga no envio."""
    return REGIOES[regiao]["custo_mes"] * meses


def motivo_envio_bloqueado(regiao, meses, em_missao, nivel_base, caixa):
    """Por que não dá para mandar o olheiro agora. `em_missao`: as regiões
    das missões em andamento."""
    if len(em_missao) >= limite(nivel_base):
        n = limite(nivel_base)
        return (f"A base de nível {nivel_base} tem {n} olheiro{'s' if n > 1 else ''}, "
                "e todos estão em missão")
    if regiao in em_missao:
        return f"Já há um olheiro em missão: {REGIOES[regiao]['nome']}"
    if custo(regiao, meses) > caixa:
        return "Sem caixa para pagar a missão"
    return None


def primeiro_relatorio(enviado_em):
    return enviado_em + timedelta(days=DIAS_POR_RELATORIO)


def resumo_regioes():
    """As regiões para a tela: perfil e números."""
    return [
        {
            "id": rid,
            "nome": r["nome"],
            "perfil": r["perfil"],
            "paises": r["paises"],
            "custo_mes": r["custo_mes"],
            "por_relatorio": list(r["por_relatorio"]),
            "idades": list(r["idades"]),
        }
        for rid, r in REGIOES.items()
    ]


def _funcao(regiao, rng):
    """Uma posição na proporção do elenco ideal, com as típicas da região
    pesando mais."""
    extra = REGIOES[regiao]["funcoes"]
    funcoes = list(base.COMPOSICAO_IDEAL)
    pesos = [base.COMPOSICAO_IDEAL[f] * extra.get(f, 1) for f in funcoes]
    return rng.choices(funcoes, weights=pesos)[0]


def gerar_indicado(regiao, media_elenco, nivel_base, proibidos, rng):
    """Um jovem que o olheiro achou na região (`proibidos` é atualizado)."""
    r = REGIOES[regiao]
    desconto, (margem_min, margem_max) = base.NIVEIS[nivel_base][:2]
    overall = max(base.OVERALL_MIN, round(media_elenco) - desconto + r["overall"]
                  + rng.randint(-base.VARIACAO_OVERALL, base.VARIACAO_OVERALL))
    margem = rng.randint(max(1, margem_min + r["margem"]), max(2, margem_max + r["margem"]))
    if rng.random() < r["joia"]:
        margem += rng.randint(*JOIA_EXTRA)
    return base.Jovem(
        nome=base.gerar_nome(proibidos, rng, r["nomes"], r["sobrenomes"]),
        idade=rng.randint(*r["idades"]),
        funcao=_funcao(regiao, rng),
        overall=float(overall),
        potencial=min(99, overall + margem),
        pais=rng.choice(r["paises"]),
    )


def gerar_relatorio(regiao, media_elenco, nivel_base, proibidos, rng):
    """Os indicados de um relatório mensal."""
    quantos = rng.randint(*REGIOES[regiao]["por_relatorio"])
    return [gerar_indicado(regiao, media_elenco, nivel_base, proibidos, rng)
            for _ in range(quantos)]
