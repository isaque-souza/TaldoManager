from . import financas
from .partida import Partida


class Campeonato:
    def __init__(self, nome, clubes):
        self.nome = nome
        self.clubes = clubes
        self.rodada = 1
        self.historico = []
        self.partidas_jogadas = []
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
            
    def jogar_rodada(self):

        self.mostrar_cabecalho()

        rodada_atual = self.obter_rodada()

        if rodada_atual is None:
            return

        for clube1, clube2 in rodada_atual:

            partida = Partida(clube1, clube2)
            partida.simular_partida()

            self.registrar_partida(
                clube1,
                clube2,
                partida
            )

            self.atualizar_recordes(partida)

        financas.processar_rodada(rodada_atual, len(self.calendario))

        self.rodada += 1

        if self.rodada > len(self.calendario):
            financas.pagar_premiacao(self.classificacao())

        for clube in self.clubes:
            clube.historico_caixa.append(clube.dinheiro)
            
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
            "eventos": partida.resumo_eventos(),
            "atuacoes": partida.resumo_escalacao(),
        })
            
    def classificacao(self):

        return sorted(
            self.clubes,
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

        times = self.clubes[:]

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