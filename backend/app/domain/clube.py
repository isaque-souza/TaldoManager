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

    # {formação: (defensores, meias, atacantes)} — o goleiro é sempre 1
    FORMACOES = {
        "4-4-2": (4, 4, 2),
        "4-3-3": (4, 3, 3),
        "4-5-1": (4, 5, 1),
        "4-2-4": (4, 2, 4),
        "3-5-2": (3, 5, 2),
        "3-4-3": (3, 4, 3),
        "5-3-2": (5, 3, 2),
        "5-4-1": (5, 4, 1),
    }

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

        # finanças da temporada (v0.7) — ver app.domain.financas
        self.dinheiro_inicial = dinheiro
        self.receita_tv = 0
        self.receita_bilheteria = 0
        self.receita_premiacao = 0
        self.despesa_salarios = 0
        self.receita_vendas = 0
        self.despesa_compras = 0

        self.jogadores = []
        self.titulares = []
        self.reservas = []
        self.formacao = "4-3-3"
        self.tatica = "equilibrado"
        self.xi_preferido = set()   # Jogadores que o técnico prefere como titulares

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
        """Multiplicador da chance de gol do clube quando ataca."""
        return self._MODS.get(self.tatica, (1.0, 1.0))[0]

    def mod_defesa(self):
        """> 1 quando o clube concede menos; < 1 quando concede mais."""
        return self._MODS.get(self.tatica, (1.0, 1.0))[1]
    
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

        self.jogadores.append(
            jogador
        )
    
    def contratar_reserva(self, jogador):

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

            total += (
                jogador.overall
                * modificador
            )

        return (
            total / len(ativos)
        ) - self.penalidade_expulsao
        
    def escalar_time(self):

        disponiveis = [
            j for j in self.jogadores
            if j.disponivel
        ]

        n_def, n_mei, n_ata = self.FORMACOES.get(self.formacao, (4, 3, 3))

        def melhores(posicao, quantos):
            elegiveis = [
                j for j in disponiveis
                if j.posicao == posicao
            ]
            elegiveis.sort(
                key=lambda j: j.score_escalacao(
                    preferido=j in self.xi_preferido
                ),
                reverse=True,
            )
            return elegiveis[:quantos]

        self.titulares = (
            melhores("Goleiro", 1)
            + melhores("Defesa", n_def)
            + melhores("Meio-Campo", n_mei)
            + melhores("Atacante", n_ata)
        )

        # faltou gente numa posição (venda, lesão, suspensão)? Improvisa os
        # melhores jogadores de linha que sobraram, em vez de jogar com 10.
        # Com o elenco completo isto não faz nada. (Roadmap: quando houver
        # overall por posição, improvisar quem SABE jogar ali.)
        if len(self.titulares) < 11:
            sobra = [
                j for j in disponiveis
                if j not in self.titulares and j.posicao != "Goleiro"
            ]
            sobra.sort(key=lambda j: j.score_escalacao(), reverse=True)
            self.titulares += sobra[: 11 - len(self.titulares)]

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
    