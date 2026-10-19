import random

from . import copa as copa_
from . import estadio, fama, financas, torcida
from .partida import Partida


class Campeonato:
    def __init__(self, nome, clubes):
        self.nome = nome
        self.clubes = clubes
        # ligas (v1.6): cada uma tem a sua tabela e o seu turno e returno,
        # jogados na mesma rodada; a ordem é a dos clubes
        self.ligas = list(dict.fromkeys(c.liga for c in clubes))
        self.livres = []              # jogadores sem clube (v1.6)
        self.copa = None              # copa entre as ligas (v1.6), se houver
        self.rodada = 1
        self.historico = []
        self.partidas_jogadas = []
        self.partida_usuario = None   # a do técnico na última rodada
        self.calendario = self.gerar_calendario()
        self.recordes = {
            "maior_goleada": {
            "valor": 0,
            "partida": ""
            },
            "mais_gols_jogo": {
            "valor": 0,
            "partida": ""
            }
        }
            
    def jogar_rodada(self, clube_usuario=None, decisoes=None, capturar_em=None):
        """Joga a rodada. Com `clube_usuario`, a partida dele roda numa
        corrente de RNG própria (semente sorteada antes de tudo): decisões
        do técnico no meio do jogo (simulação interativa, v1.2) mudam só
        aquele jogo, nunca os outros da rodada. A Partida dele fica em
        `self.partida_usuario`."""

        self.mostrar_cabecalho()

        rodada_atual = self.obter_rodada()

        if rodada_atual is None:
            return

        semente = random.getrandbits(64) if clube_usuario else None
        self.partida_usuario = None

        publicos = {}
        for clube1, clube2 in rodada_atual:

            partida = Partida(clube1, clube2)
            # o público é decidido antes do apito (v1.5): empurra o mandante
            # e vira a bilheteria dele
            partida.publico = estadio.publico(clube1, clube2)
            publicos[clube1.nome] = partida.publico

            if clube_usuario in (clube1.nome, clube2.nome):
                partida.decisoes = decisoes or []
                partida.capturar_em = capturar_em
                fora = random.getstate()
                random.seed(semente)
                try:
                    partida.simular_partida()
                finally:
                    random.setstate(fora)
                self.partida_usuario = partida
            else:
                partida.simular_partida()

            self.registrar_partida(
                clube1,
                clube2,
                partida
            )

            torcida.processar_jogo(clube1, clube2, partida.gols_c1, partida.gols_c2)

            self.atualizar_recordes(partida)

        financas.processar_rodada(rodada_atual, len(self.calendario), publicos)

        for clube in self.clubes:
            estadio.avancar_obra(clube)

        self.jogar_copa()

        self.rodada += 1

        if self.rodada > len(self.calendario):
            for liga in self.ligas:
                tabela = self.classificacao(liga)
                financas.pagar_premiacao(tabela)
                # a fama antes da torcida: os ídolos novos já atraem gente
                fama.fim_de_temporada(tabela)
                torcida.fim_de_temporada(tabela)

        for clube in self.clubes:
            clube.historico_caixa.append(clube.dinheiro)
            
    def jogar_copa(self):
        """A fase da copa no meio da semana, se esta rodada tiver uma.
        Devolve os jogos jogados ([] se não teve)."""
        if self.copa is None:
            return []
        fase = self.copa.fase_da_rodada(self.rodada)
        if fase is None:
            return []
        return self.copa.jogar_fase(fase, {c.nome: c for c in self.clubes})

    def iniciar_copa(self, classificados):
        """Monta a copa com {liga: [nomes do 1º ao 8º]}. Só com duas
        ligas; com uma, fica sem copa."""
        self.copa = copa_.Copa(classificados) if len(self.ligas) == 2 else None
        return self.copa

    def mostrar_cabecalho(self):

        print(f"\n{'=' * 40}")
        print(f"Rodada {self.rodada}")
        print(f"{'=' * 40}")
            
    def obter_rodada(self):

        if self.rodada > len(self.calendario):
            print("Campeonato encerrado!")
            return None

        rodada = self.calendario[self.rodada - 1]

        if not rodada:
            print("Campeonato encerrado!")
            return None

        return rodada
        
    def registrar_partida(self, clube1, clube2, partida):

        self.historico.append(
            f"Rodada {self.rodada}: "
            f"{clube1.nome} "
            f"{partida.gols_c1} x "
            f"{partida.gols_c2} "
            f"{clube2.nome}"
        )

        # registro estruturado, para persistir / navegar depois
        self.partidas_jogadas.append({
            "rodada": self.rodada,
            "mandante": clube1.nome,
            "visitante": clube2.nome,
            "gols_mandante": partida.gols_c1,
            "gols_visitante": partida.gols_c2,
            "posse_mandante": partida.posse_c1,
            "finalizacoes_mandante": partida.finalizacoes_c1,
            "finalizacoes_visitante": partida.finalizacoes_c2,
            "finalizacoes_gol_mandante": partida.finalizacoes_gol_c1,
            "finalizacoes_gol_visitante": partida.finalizacoes_gol_c2,
            "escanteios_mandante": partida.escanteios_c1,
            "escanteios_visitante": partida.escanteios_c2,
            "acrescimos": partida.acrescimos,
            "publico": partida.publico,
            "eventos": partida.resumo_eventos(),
            "atuacoes": partida.resumo_escalacao(),
        })
            
    def clubes_da_liga(self, liga=None):
        """Os clubes de uma liga (v1.6); sem `liga`, todos."""
        return [c for c in self.clubes if liga is None or c.liga == liga]

    def classificacao(self, liga=None):
        """A tabela de uma liga (v1.6). Sem `liga`, todos os clubes juntos —
        com uma liga só, é a tabela dela."""

        return sorted(
            self.clubes_da_liga(liga),
            key=lambda c: (
                c.pontos,
                c.saldo_gols(),
                c.gols_marcados
            ),
            reverse=True
        )
            
    def mostrar_classificacao(self):

        print(f"Classificação do campeonato {self.nome}:")

        for idx, clube in enumerate(self.classificacao(), start=1):

            jogos = (
                clube.vitorias +
                clube.empates +
                clube.derrotas
            )

            print(
                f"{idx}. {clube.nome} | "
                f"P: {clube.pontos} | "
                f"J: {jogos} | "
                f"V: {clube.vitorias} | "
                f"E: {clube.empates} | "
                f"D: {clube.derrotas} | "
                f"GP: {clube.gols_marcados} | "
                f"GC: {clube.gols_sofridos} | "
                f"SG: {clube.saldo_gols()} | "
                f"Forma: {' '.join(clube.forma)}"
            )
                
    def listar_jogadores(self):

        jogadores = []

        for clube in self.clubes:
            jogadores.extend(clube.jogadores)

        return jogadores
        
    def mostrar_artilharia(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: j.gols,
            reverse=True
        )

        print("\n=== ARTILHARIA ===")

        for jogador in ranking:

            if jogador.gols > 0:

                print(
                    f"{jogador.nome} | "
                    f"G: {jogador.gols} | "
                    f"A: {jogador.assistencias} | "
                    f"N: {jogador.nota_media():.1f}"
                )
                    
    def assistencias(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: j.assistencias,
            reverse=True
            )

        print("\n=== ASSISTÊNCIAS ===")

        for jogador in ranking:

            if jogador.assistencias > 0:

                print(
                    f"{jogador.nome} | "
                    f"A: {jogador.assistencias}"
                )
    
    def clean_sheets(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: (
                j.clean_sheets,
                j.nota_media()
            ),
            reverse=True
        )

        print("\n=== CLEAN SHEETS ===")

        for jogador in ranking:

            if (
                jogador.posicao == "Goleiro"
                and jogador.clean_sheets > 0
            ):

                print(
                    f"{jogador.nome} | "
                    f"CS: {jogador.clean_sheets}"
                )
            
    def melhores_notas(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: (
                j.nota_media(),
                j.melhor_nota,
                j.melhor_em_campo,
                j.gols,
                j.assistencias
            ),
            reverse=True
        )

        print("\n=== MELHORES NOTAS ===")

        for jogador in ranking:

            if jogador.partidas > 0:

                print(
                    f"{jogador.nome} | "
                    f"Média: {jogador.nota_media()} | "
                    f"Melhor: {jogador.melhor_nota:.1f} | "
                    f"Pior: {jogador.pior_nota:.1f}"
                )
                
    def hat_tricks(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: j.hat_tricks,
            reverse=True
        )

        print("\n=== HAT-TRICKS ===")

        for jogador in ranking:

            if jogador.hat_tricks > 0:

                print(
                    f"{jogador.nome} | "
                    f"HT: {jogador.hat_tricks}"
                )
            
    def mvp_campeonato(self):

        ranking = sorted(
            self.listar_jogadores(),
            key=lambda j: (
                j.melhor_em_campo,
                j.nota_media(),
                j.gols + j.assistencias,
                j.hat_tricks
            ),
            reverse=True
        )

        vencedor = ranking[0]

        print("\n🏆 MVP DO CAMPEONATO")
        print("---------------------------")
        print(f"Jogador: {vencedor.nome}")
        print(f"Posição: {vencedor.posicao}")
        print(f"Overall: {vencedor.overall}")
        print(f"Melhores em campo: {vencedor.melhor_em_campo}")
        print(f"Nota média: {vencedor.nota_media()}")
        print(f"Gols: {vencedor.gols}")
        print(f"Assistências: {vencedor.assistencias}")
        
    def mostrar_historico(self):

        print(f"Histórico do campeonato {self.nome}:")

        for evento in self.historico:
            print(f"- {evento}")
            
    def atualizar_recordes(self, partida):

        diferenca = abs(
            partida.gols_c1 -
            partida.gols_c2
        )

        total = (
            partida.gols_c1 +
            partida.gols_c2
        )

        descricao = (
            f"{partida.clube1.nome} "
            f"{partida.gols_c1} x "
            f"{partida.gols_c2} "
            f"{partida.clube2.nome}"
        )

        if diferenca > self.recordes["maior_goleada"]["valor"]:

            self.recordes["maior_goleada"]["valor"] = diferenca
            self.recordes["maior_goleada"]["partida"] = descricao

        if total > self.recordes["mais_gols_jogo"]["valor"]:

            self.recordes["mais_gols_jogo"]["valor"] = total
            self.recordes["mais_gols_jogo"]["partida"] = descricao
            
    def mostrar_recordes(self):

        print("\n=== RECORDES ===")

        print(
            "Maior goleada:",
            self.recordes["maior_goleada"]["partida"],
            f"({self.recordes['maior_goleada']['valor']})"
        )

        print(
            "Mais gols em uma partida:",
            self.recordes["mais_gols_jogo"]["partida"],
            f"({self.recordes['mais_gols_jogo']['valor']})"
        )
    
    def gerar_calendario(self):
        """O turno e returno de cada liga (v1.6), lado a lado: a rodada N
        tem os jogos da rodada N de todas as ligas (elas têm o mesmo número
        de clubes)."""

        por_liga = [self._calendario_da_liga(self.clubes_da_liga(liga))
                    for liga in self.ligas]
        if not por_liga:
            return []
        return [
            [jogo for rodadas in por_liga for jogo in rodadas[i]]
            for i in range(max(len(r) for r in por_liga))
        ]

    def _calendario_da_liga(self, clubes):

        times = clubes[:]

        if len(times) % 2 != 0:
            times.append(None)

        rodadas = []

        # Turno
        for _ in range(len(times) - 1):

            rodada = []

            for i in range(len(times) // 2):

                time1 = times[i]
                time2 = times[-i - 1]

                if time1 is not None and time2 is not None:
                    rodada.append((time1, time2))

            rodadas.append(rodada)

            times = (
                [times[0]]
                + [times[-1]]
                + times[1:-1]
            )

        # Returno
        rodadas_volta = []

        for rodada in rodadas:

            nova_rodada = []

            for time1, time2 in rodada:
                nova_rodada.append((time2, time1))

            rodadas_volta.append(nova_rodada)

        return rodadas + rodadas_volta