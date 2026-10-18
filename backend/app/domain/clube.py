from app.domain import numeros, posicoes


class Clube:

    # postura tática escolhida pelo técnico (afeta os pesos da engine)
    TATICAS = ("ofensivo", "equilibrado", "defensivo")

    # {tática: (mod_ataque, mod_defesa)} — ataque > 1 cria mais; defesa > 1
    # concede menos. Ofensivo troca solidez por perigo (mais gols dos dois
    # lados); defensivo o inverso.
    _MODS = {
        "ofensivo":     (1.30, 0.82),
        "equilibrado":  (1.00, 1.00),
        "defensivo":    (0.85, 1.20),
    }

    # a formação também pesa (v1.2), na metade da escala da tática: mais
    # atacantes criam mais e deixam mais espaço atrás; mais zagueiros, o
    # contrário. 4-3-3 (o padrão de todo clube) é a neutra.
    _MODS_FORMACAO = {
        "3-4-3": (1.12, 0.90),
        "4-2-4": (1.12, 0.90),
        "3-5-2": (1.05, 0.96),
        "4-1-2-1-2": (1.04, 0.97),
        "4-3-3": (1.00, 1.00),
        "4-2-3-1": (1.00, 1.02),
        "4-4-2": (0.97, 1.04),
        "4-4-1-1": (0.95, 1.05),
        "4-5-1": (0.92, 1.07),
        "5-3-2": (0.92, 1.08),
        "5-4-1": (0.88, 1.12),
    }

    # {formação: (defensores, meias, atacantes)} pelo setor de cada vaga do
    # desenho (posicoes.DESENHO) — o goleiro é sempre 1. Um meia aberto (ME/
    # MD) é ponta, então o 4-4-2 conta 2 atacantes a mais que o nome
    FORMACOES = posicoes.SETORES_DA_FORMACAO

    def __init__(
        self,
        nome,
        pais,
        dinheiro,
        torcedores=0
    ):
        self.nome = nome
        self.pais = pais
        self.dinheiro = dinheiro
        self.torcedores = torcedores
        self.rivais = set()   # nomes dos clubes rivais (clássicos)
        self.identidade = None   # cores/escudo/camisa (só visual, v1.1)

        # finanças da temporada (v0.7) — ver app.domain.financas
        self.dinheiro_inicial = dinheiro
        self.receita_tv = 0
        self.receita_bilheteria = 0
        self.receita_premiacao = 0
        self.despesa_salarios = 0
        self.receita_vendas = 0
        self.despesa_compras = 0
        # caixa ao fim de cada rodada (para o gráfico). Guardado, não
        # reconstruído: transferências e renovações mexem no caixa e na folha
        # ENTRE as rodadas, então as partidas sozinhas não contam a história
        self.historico_caixa = []

        self.jogadores = []
        self.titulares = []
        self.reservas = []
        self.formacao = "4-3-3"
        self.tatica = "equilibrado"
        self.xi_preferido = set()   # Jogadores que o técnico prefere como titulares
        # onde o técnico pôs cada um (v1.3): {"formacao", "nomes"}, com
        # nomes[i] na vaga i do desenho. Só vale na formação em que foi feito
        self.posicionamento = None

        self.pontos = 0
        self.gols_marcados = 0
        self.gols_sofridos = 0

        self.vitorias = 0
        self.empates = 0
        self.derrotas = 0

        self.forma = []
        
        self.penalidade_expulsao = 0
        
    def lancar(self, categoria, valor):
        """Registra um lançamento financeiro: soma no total da `categoria` e
        mexe no caixa (receita_* entra, despesa_* sai). O caixa pode ficar
        negativo — o clube entra em dívida."""

        setattr(self, categoria, getattr(self, categoria) + valor)
        if categoria.startswith("despesa_"):
            self.dinheiro -= valor
        else:
            self.dinheiro += valor

    def atualizar_forma(self, resultado):

        self.forma.append(resultado)

        if len(self.forma) > 5:
            self.forma.pop(0)
    
    def bonus_forma(self):

        bonus = 0

        for resultado in self.forma:

            if resultado == "V":
                bonus += 0.5

            elif resultado == "D":
                bonus -= 0.5

        return bonus

    def mod_ataque(self):
        """Multiplicador da chance de gol do clube quando ataca (tática ×
        formação)."""
        return (
            self._MODS.get(self.tatica, (1.0, 1.0))[0]
            * self._MODS_FORMACAO.get(self.formacao, (1.0, 1.0))[0]
        )

    def mod_defesa(self):
        """> 1 quando o clube concede menos; < 1 quando concede mais."""
        return (
            self._MODS.get(self.tatica, (1.0, 1.0))[1]
            * self._MODS_FORMACAO.get(self.formacao, (1.0, 1.0))[1]
        )
    
    def mostrar(self):
        print(f"\nClube: {self.nome}")
        print(f"País: {self.pais}")
        print(f"Dinheiro: {self.dinheiro}")
        print("\nElenco:")
        for jogador in self.jogadores:
            print(f"- {jogador.nome} ({jogador.overall})")
            
    def mostrar_partida(self):
        print(f"\nClube: {self.nome}")
        print(f"Força: {self.calcular_forca():.0f}")
        
    def contratar_jogador(self, jogador):

        numeros.garantir_numero(self, jogador)
        self.jogadores.append(
            jogador
        )
    
    def contratar_reserva(self, jogador):

        numeros.garantir_numero(self, jogador)
        self.jogadores.append(jogador)
        self.reservas.append(jogador)
    
    def calcular_forca(self):

        ativos = [
            j for j in self.titulares
            if not j.expulso
        ]

        if not ativos:
            return 0

        total = 0

        for jogador in ativos:

            modificador = 1

            if jogador.condicao == "Cansado":
                modificador = 0.90

            elif jogador.condicao == "Exausto":
                modificador = 0.75

            # o overall NA VAGA (v1.3): improvisado rende menos
            total += (
                jogador.overall_em_campo()
                * modificador
            )

        return (
            total / len(ativos)
        ) - self.penalidade_expulsao
        
    def escalar_time(self):
        """Monta o XI nas vagas da formação (posicoes.VAGAS) e o banco.

        O XI do técnico é respeitado: quem ele escolheu entra na frente de
        qualquer um, menos se estiver exausto (aí o motor poupa), e os
        escolhidos são distribuídos nas vagas com a menor perda somada —
        escolher um volante no lugar de um zagueiro improvisa o volante na
        zaga. As vagas que sobram ficam com quem rende mais nelas (score
        com o overall na vaga). Faltando gente (venda, lesão, suspensão), improvisa quem
        sabe jogar ali, em vez de jogar com 10.
        """

        disponiveis = [
            j for j in self.jogadores
            if j.disponivel
        ]
        vagas = posicoes.vagas(self.formacao)
        ocupante = [None] * len(vagas)
        proibido = 1000   # goleiro × linha: só se não houver outro jeito

        def atribuir(candidatos, custo, linha_no_gol):
            # quem joga em que vaga com o menor custo SOMADO (algoritmo
            # húngaro): um ponta sobrando num 5-3-2 vai para o meio e um meia
            # recua, em vez de o ponta virar zagueiro
            livres = [i for i, o in enumerate(ocupante) if o is None]
            if not candidatos or not livres:
                return
            cruza = lambda j, v: (j.posicao == "Goleiro") != (v == "Goleiro")
            m = [
                [custo(j, vagas[i]) + (proibido if cruza(j, vagas[i]) else 0)
                 for i in livres]
                for j in candidatos
            ]
            if len(candidatos) <= len(livres):
                pares = zip(candidatos, (livres[k] for k in posicoes.menor_custo(m)))
            else:
                transposta = [list(coluna) for coluna in zip(*m)]
                pares = (
                    (candidatos[k], i)
                    for i, k in zip(livres, posicoes.menor_custo(transposta))
                )
            for j, i in pares:
                # goleiro nunca vai para a linha; jogador de linha no gol só
                # quando não sobrou goleiro
                if cruza(j, vagas[i]) and (
                    j.posicao == "Goleiro" or not linha_no_gol
                ):
                    continue
                ocupante[i] = j

        escolhidos = [
            j for j in disponiveis
            if j in self.xi_preferido and j.condicao != "Exausto"
        ]

        # quem o técnico pôs numa vaga fica nela (goleiro só no gol)
        pos = self.posicionamento
        if pos and pos.get("formacao") == self.formacao:
            por_nome = {j.nome: j for j in escolhidos}
            for i, nome in enumerate(pos.get("nomes", [])[: len(vagas)]):
                j = por_nome.get(nome)
                if j and (j.posicao == "Goleiro") == (vagas[i] == "Goleiro"):
                    ocupante[i] = j

        atribuir(
            [j for j in escolhidos if j not in ocupante],
            lambda j, v: j.overall - j.overall_em(v),
            linha_no_gol=False,
        )

        resto = [j for j in disponiveis if j not in ocupante]
        atribuir(
            resto,
            lambda j, v: -j.score_escalacao(
                preferido=j in self.xi_preferido, vaga=v
            ),
            linha_no_gol=True,
        )

        for jogador in self.jogadores:
            jogador.vaga = jogador.slot = None
        self.titulares = []
        for slot, (vaga, jogador) in enumerate(zip(vagas, ocupante)):
            if jogador is not None:
                # slot: a vaga no desenho da formação (onde fica no campo)
                jogador.vaga, jogador.slot = vaga, slot
                self.titulares.append(jogador)

        self.reservas = [
            j for j in disponiveis
            if j not in self.titulares
        ]
    
    def saldo_gols(self):
        return self.gols_marcados - self.gols_sofridos
    
    def mostrar_elenco(self):

        print("\n=== TITULARES ===")

        for jogador in self.jogadores:
            print(
                jogador.nome,
                jogador.posicao
            )

        print("\n=== RESERVAS ===")

        for jogador in self.reservas:
            print(
                jogador.nome,
                jogador.posicao
            )
    