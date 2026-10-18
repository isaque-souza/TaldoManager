import random

from app.domain import torcida


class Partida:

    # vantagem do mandante, em pontos de "overall" somados à força do time,
    # para quem não tem torcida registrada; com torcida, quanto maior ela,
    # maior o mando (torcida.mando_de_campo, v1.4)
    MANDO_DE_CAMPO = torcida.MANDO_BASE

    def __init__(self, clube1, clube2):
        self.clube1 = clube1
        self.clube2 = clube2
        self.resultado = None
        self.gols_c1 = 0
        self.gols_c2 = 0
        self.eventos = []
        self.posse_c1 = 50
        self.posse_c2 = 50
        self.finalizacoes_c1 = 0
        self.finalizacoes_c2 = 0
        self.finalizacoes_gol_c1 = 0
        self.finalizacoes_gol_c2 = 0
        self.escanteios_c1 = 0
        self.escanteios_c2 = 0
        self.substituicoes_c1 = 0
        self.substituicoes_c2 = 0
        self.max_substituicoes = 5
        # {"minuto", "sai", "entra"} de cada troca, para o snapshot da escalação
        self.substituicoes_log = []
        # XI inicial de cada lado (capturado em criar_estatisticas)
        self.titulares_iniciais = set()
        # minutos de acréscimo (definidos em executar_simulacao)
        self.acrescimos = 0
        # simulação interativa (v1.2): decisões do técnico durante o jogo,
        # cada uma aplicada no começo do seu minuto —
        # {"minuto", "clube", "tatica"}, {"minuto", "clube", "formacao"} ou
        # {"minuto", "clube", "sai", "entra"}
        self.decisoes = []
        # um lance por minuto (quem atacou e como acabou), para a transmissão
        self.linha_do_tempo = []
        self._lance = None
        # minuto em que fotografar quem está em campo (pausa da transmissão)
        self.capturar_em = None
        self.estado_capturado = None

    #Orquestração
        
    def preparar_partida(self):

        self.gols_c1 = 0
        self.gols_c2 = 0

        self.finalizacoes_c1 = 0
        self.finalizacoes_c2 = 0

        self.finalizacoes_gol_c1 = 0
        self.finalizacoes_gol_c2 = 0

        self.escanteios_c1 = 0
        self.escanteios_c2 = 0

        self.eventos = []
        self.substituicoes_log = []

        self.clube1.penalidade_expulsao = 0
        self.clube2.penalidade_expulsao = 0

        self.calcular_posse()

        for jogador in (
            self.clube1.titulares +
            self.clube2.titulares
        ):
            jogador.resetar_estatisticas_partida()
    
    def executar_simulacao(
        self,
    ):

        self.acrescimos = random.randint(1, 5)

        if self.capturar_em == 0:
            self.estado_capturado = self.foto_do_momento(0)

        for minuto in range(1, 91 + self.acrescimos):

            self.aplicar_decisoes(minuto)

            self.simular_minuto(
                minuto,
            )

            self.linha_do_tempo.append(self._registro_do_minuto(minuto))

            if minuto == self.capturar_em:
                self.estado_capturado = self.foto_do_momento(minuto)

    def simular_minuto(
        self,
        minuto
    ):

        self._lance = None

        self.simular_ataque(
            minuto,
        )

        self.simular_falta_avulsa(
            minuto
        )

        self.simular_penalti_minuto(
            minuto,
        )
        self.simular_substituicao(
            minuto
        )
        if minuto in [15, 30, 45, 60, 75, 90]:
            self.atualizar_fadiga()
    
    def finalizar_partida(self):

        self.recalcular_placar()

        self.definir_resultado()

        self.mostrar_resultado()

        self.mostrar_eventos()

        self.atualizar_classificacao()

        self.atualizar_estatisticas_clubes()

        self.atualizar_clean_sheet()
    
    def simular_partida(self):

        # o cartão vermelho tira o jogador só do resto DESTA partida; a
        # suspensão (jogos_suspensao) é o que o mantém fora das próximas
        for jogador in self.clube1.jogadores + self.clube2.jogadores:
            jogador.expulso = False

        # tática e formação mudadas no meio do jogo (interativa) valem só
        # para esta partida
        posturas = {c: (c.tatica, c.formacao) for c in (self.clube1, self.clube2)}

        self.clube1.escalar_time()
        self.clube2.escalar_time()

        # suspenso/lesionado já ficaram de fora em escalar_time; a partida
        # ter acontecido faz a pena e a recuperação andarem uma rodada
        self._avancar_pendencias()
        
        print("\n=== ESCALAÇÃO ===")
        print(self.clube1.nome)

        for j in self.clube1.titulares:
            print(
                j.nome,
                j.overall,
                j.energia,
                j.score_escalacao()
            )

        print("\nReservas")

        for j in self.clube1.reservas:
            print(
                j.nome,
                j.overall,
                j.energia,
                j.score_escalacao()
            )
        
        
        self.preparar_partida()

        self.estatisticas = (
            self.criar_estatisticas()
    )

        self.executar_simulacao(
        )

        self.processar_eventos()

        self.verificar_hat_tricks(
            
        )

        self.finalizar_partida()

        melhor, nota = (
            self.calcular_notas(
            )
        )

        if melhor is not None:
            self.mostrar_melhor_em_campo(
                melhor,
                nota
            )
        
        print("\n=== FADIGA ANTES DA RECUPERAÇÃO ===")

        for jogador in self.clube1.titulares[:3]:
            print(
                jogador.nome,
                jogador.energia,
                jogador.condicao
            )

        for jogador in self.clube2.titulares[:3]:
            print(
                jogador.nome,
                jogador.energia,
                jogador.condicao
            )

        self.recuperar_energia(
            self.clube1
        )

        self.recuperar_energia(
            self.clube2
        )

        self.sortear_lesoes()

        for clube, (tatica, formacao) in posturas.items():
            clube.tatica, clube.formacao = tatica, formacao

    #Engine
    
    def simular_ataque(
        self,
        minuto,
    ):

        # houve ataque?
        if random.random() > 0.28:
            return

        # quem atacou?
        clube_atacando = random.choices(
            [self.clube1, self.clube2],
            weights=[
                self.posse_c1,
                self.posse_c2
            ]
        )[0]

        # quem defendeu?
        clube_defendendo = (
            self.clube2
            if clube_atacando == self.clube1
            else self.clube1
        )

        self._defensor = None
        # o lance do minuto (só anota; não sorteia nada)
        self._lance = {
            "lado": 1 if clube_atacando == self.clube1 else 2,
            "fim": "cortado",
        }

        self.simular_acao_defensiva(
            clube_defendendo,
            minuto
        )

        # quem finalizou?
        artilheiro = self.escolher_artilheiro(
            clube_atacando
        )

        if artilheiro is None:
            return

        self.gerar_drible(
            artilheiro
        )

        self.gerar_passe_chave(
            artilheiro
        )

        # houve finalização?
        if not self.gerar_finalizacao(
            clube_atacando,
            artilheiro
        ):
            self._talvez_escanteio(clube_atacando, 0.20)   # ataque cortado
            return

        # foi no gol?
        if not self.finalizacao_no_gol(
            clube_atacando,
            artilheiro
        ):

            self._lance["fim"] = "fora"

            self.adicionar_evento(
                minuto,
                "chute_fora",
                artilheiro
            )

            self._talvez_escanteio(clube_atacando, 0.30)   # desviou pra linha
            return

        # goleiro defendeu?
        if self.goleiro_defendeu(
            clube_defendendo
        ):
            self._lance["fim"] = "defesa"
            self._talvez_escanteio(clube_atacando, 0.45)   # espalmou
            return

        # gol
        self._lance["fim"] = "gol"
        self.marcar_gol(
            clube_atacando,
            minuto,
            artilheiro
        )
    
    def _talvez_escanteio(self, clube_atacando, chance):
        if random.random() < chance:
            if clube_atacando == self.clube1:
                self.escanteios_c1 += 1
            else:
                self.escanteios_c2 += 1

    def gerar_finalizacao(
        self,
        clube_atacando,
        artilheiro
    ):

        # duelo (v1.3): velocidade e drible do atacante contra velocidade e
        # marcação de quem tentou parar o lance
        chance_finalizacao = 0.25 * (1 + self.duelo(artilheiro, self._defensor))

        if random.random() > chance_finalizacao:
            return False

        if clube_atacando == self.clube1:
            self.finalizacoes_c1 += 1
        else:
            self.finalizacoes_c2 += 1

        if artilheiro:
            artilheiro.chutes_partida += 1

        return True
    
    def finalizacao_no_gol(
        self,
        clube_atacando,
        artilheiro
    ):

        chance_no_gol = 0.50 * self.fator_ataque(clube_atacando)
        # quem finaliza melhor do que o próprio nível acerta mais o alvo (v1.3);
        # o nível em si já pesa no fator_ataque
        if artilheiro:
            chance_no_gol *= 1 + max(-0.12, min(0.12, (
                artilheiro.atributo("finalizacao") - artilheiro.overall_em_campo()
                - self.REF_FINALIZACAO
            ) * 0.01))

        if random.random() > chance_no_gol:
            return False

        if clube_atacando == self.clube1:
            self.finalizacoes_gol_c1 += 1
        else:
            self.finalizacoes_gol_c2 += 1

        if artilheiro:
            artilheiro.chutes_gol_partida += 1

        return True
    
    def goleiro_defendeu(
        self,
        clube
    ):

        goleiro = self._goleiro(clube)

        if goleiro is None:
            return False

        # reflexos e posicionamento (v1.3; antes, o overall)
        chance_defesa = (
            0.14 +
            (self.nivel_goleiro(goleiro) - 71) * 0.012
        )

        if random.random() < chance_defesa:

            goleiro.defesas_partida += 1
            return True

        return False
    
    def marcar_gol(
        self,
        clube,
        minuto,
        artilheiro
    ):
        
        if artilheiro is None:
            return

        # atualiza estatísticas do jogador
        artilheiro.gols += 1
        self.estatisticas[artilheiro]["gols"] += 1

        # atualiza placar
        if clube == self.clube1:
            self.gols_c1 += 1
        else:
            self.gols_c2 += 1

        # registra evento
        self.adicionar_evento(
            minuto,
            "gol",
            artilheiro
        )

        # assistência
        self.distribuir_assistencia(
            clube,
            artilheiro
        )
    
    def simular_penalti_minuto(
        self,
        minuto
    ):

        # aproximadamente
        # 0.3 penaltis por partida
        if random.random() > 0.003:
            return

        clube = random.choice([
            self.clube1,
            self.clube2
        ])

        cobrador = self.escolher_cobrador(
            clube
        )
        
        if cobrador is None:
            return

        resultado = random.random()

        # finalização do cobrador contra reflexos do goleiro (v1.3)
        goleiro = self._goleiro(self.adversario(clube))
        diferenca = cobrador.atributo("finalizacao") - (
            self.nivel_goleiro(goleiro) if goleiro else self.REF_FINALIZACAO
        ) - self.VANTAGEM_COBRADOR
        converte = max(0.62, min(0.88, 0.76 + diferenca * 0.003))

        # o pênalti é o lance que fica marcado no minuto
        self._lance = {
            "lado": 1 if clube == self.clube1 else 2,
            "fim": "penalti" if resultado < converte else "penalti_perdido",
        }

        if resultado < converte:                # convertido
            cobrador.gols += 1
            cobrador.penaltis += 1
            self.estatisticas[cobrador]["gols"] += 1
            self.adicionar_evento(minuto, "penalti", cobrador)
            return

        cobrador.penaltis_perdidos += 1

        # dos que não entram, ~58% o goleiro pega (como antes: 0.76–0.90)
        if resultado < converte + (1 - converte) * 0.58 and goleiro is not None:
            goleiro.defesas_partida += 1
            self.adicionar_evento(minuto, "penalti_defendido", goleiro)
        else:                                          # jogou fora
            self.adicionar_evento(minuto, "penalti_perdido", cobrador)

    def _goleiro(self, clube):
        return next(
            (j for j in clube.titulares if j.posicao == "Goleiro"), None
        )
    
    #Estatisticas Reais
    
    def gerar_drible(
        self,
        jogador
    ):

        # o drible do jogador muda a chance (v1.3)
        fator = max(0.5, min(1.5, 1 + (jogador.atributo("drible") - 80) * 0.02))

        if jogador.posicao == "Atacante":

            if random.random() < 0.40 * fator:
                jogador.dribles_partida += 1

        elif jogador.posicao == "Meio-Campo":

            if random.random() < 0.25 * fator:
                jogador.dribles_partida += 1
    
    def gerar_passe_chave(
        self,
        jogador
    ):

        # o passe do jogador muda a chance (v1.3)
        fator = max(0.5, min(1.5, 1 + (jogador.atributo("passe") - 79) * 0.02))

        if jogador.posicao == "Meio-Campo":

            if random.random() < 0.50 * fator:
                jogador.passes_chave_partida += 1

        elif jogador.posicao == "Atacante":

            if random.random() < 0.20 * fator:
                jogador.passes_chave_partida += 1
    
    #Ações Defensivas
    
    def simular_acao_defensiva(
        self,
        clube_defendendo,
        minuto
    ):

        defensores = [
            j for j in clube_defendendo.titulares
            if (
                j.posicao in [
                    "Defesa",
                    "Meio-Campo"
                ]
                and not j.expulso
            )
        ]

        if not defensores:
            return

        defensor = random.choice(
            defensores
        )
        self._defensor = defensor   # duela com o atacante (v1.3)

        self.gerar_desarme(
            defensor
        )

        self.gerar_interceptacao(
            defensor
        )

        self.gerar_corte(
            defensor
        )

        self.gerar_falta(
            defensor,
            clube_defendendo,
            minuto
        )
    
    def gerar_desarme(
        self,
        jogador
    ):

        if jogador.posicao == "Defesa":

            jogador.desarmes_partida += random.randint(
                0,
                2
            )

        elif jogador.posicao == "Meio-Campo":

            jogador.desarmes_partida += random.randint(
                0,
                1
            )
    
    def gerar_interceptacao(
        self,
        jogador
    ):

        if jogador.posicao == "Defesa":

            jogador.interceptacoes_partida += random.randint(
                0,
                2
            )

        elif jogador.posicao == "Meio-Campo":

            jogador.interceptacoes_partida += random.randint(
                0,
                1
            )
    
    def gerar_corte(
        self,
        jogador
    ):

        if jogador.posicao == "Defesa":

            jogador.cortes_partida += random.randint(
                0,
                3
            )
    
    # falta: chance por ação defensiva; a "avulsa" cobre as faltas de meio
    # de campo que não vêm de um ataque (briga pela bola, etc.)
    CHANCE_FALTA = 0.50
    CHANCE_FALTA_AVULSA = 0.055
    # cartão POR FALTA: a maioria das faltas não dá nada
    CHANCE_AMARELO = 0.17
    CHANCE_VERMELHO_DIRETO = 0.004

    def gerar_falta(self, jogador, clube, minuto):
        if random.random() >= self.CHANCE_FALTA:
            return
        self._registrar_falta(jogador, clube, minuto)

    def simular_falta_avulsa(self, minuto):
        if random.random() >= self.CHANCE_FALTA_AVULSA:
            return
        clube = random.choice([self.clube1, self.clube2])
        candidatos = [
            j for j in clube.titulares
            if j.posicao in ("Defesa", "Meio-Campo") and not j.expulso
        ]
        if not candidatos:
            return
        self._registrar_falta(random.choice(candidatos), clube, minuto)

    def _registrar_falta(self, jogador, clube, minuto):
        jogador.faltas += 1
        jogador.faltas_partida += 1

        r = random.random()
        if r < self.CHANCE_VERMELHO_DIRETO:          # falta violenta
            self._expulsar(jogador, clube, minuto)
            return
        if r >= self.CHANCE_VERMELHO_DIRETO + self.CHANCE_AMARELO:
            return                                    # falta comum, sem cartão

        jogador.amarelos += 1
        jogador.amarelos_partida += 1
        self.adicionar_evento(minuto, "cartao_amarelo", jogador)

        # 2º amarelo: quase sempre vermelho, mas o juiz às vezes releva
        if jogador.amarelos_partida >= 2 and random.random() < 0.6:
            self._expulsar(jogador, clube, minuto)
            return

        jogador.registrar_amarelo()

    def _expulsar(self, jogador, clube, minuto):
        jogador.vermelhos += 1
        jogador.expulso = True
        jogador.jogos_suspensao += 1
        clube.penalidade_expulsao += 5
        self.adicionar_evento(minuto, "expulsao", jogador)
    
    #Fadiga
    
    def atualizar_fadiga(self):

        jogadores = (
            self.clube1.titulares +
            self.clube2.titulares
        )

        for jogador in jogadores:
            jogador.reduzir_energia()

        # times que cansam perdem posse
        self.calcular_posse()
    
    def recuperar_energia(
        self,
        clube
    ):

        # quem jogou recupera parcialmente no intervalo entre rodadas
        for jogador in clube.titulares:

            jogador.energia += random.randint(
                20,
                32
            )

            jogador.energia = min(
                100,
                jogador.energia
            )

            jogador.atualizar_condicao()

        # quem ficou de fora recupera quase tudo
        for jogador in clube.reservas:

            jogador.energia += random.randint(
                55,
                80
            )

            jogador.energia = min(
                100,
                jogador.energia
            )

            jogador.atualizar_condicao()
    
    #Substituições
    
    def simular_substituicao(
        self,
        minuto
    ):

        # normalmente após os 60 minutos
        if minuto < 60:
            return

        if random.random() > 0.08:
            return

        clube = random.choice([
            self.clube1,
            self.clube2
        ])

        self.realizar_substituicao(
            clube,
            minuto
        )
    
    def escolher_substituto(
        self,
        clube,
        titular
    ):

        # quem já jogou e saiu volta para `reservas`, mas não pode voltar a
        # campo (está em `estatisticas`); só entra quem ainda não jogou.
        # Da mesma posição da vaga, se houver (v1.3); senão, do mesmo setor
        reservas = [
            j for j in clube.reservas
            if j.posicao == titular.posicao
            and j not in self.estatisticas
        ]
        da_vaga = [j for j in reservas if j.funcao == titular.vaga]
        reservas = da_vaga or reservas

        if not reservas:
            return None

        return random.choice(
            reservas
        )
    
    def realizar_substituicao(
        self,
        clube,
        minuto
    ):

        if clube == self.clube1:

            if self.substituicoes_c1 >= self.max_substituicoes:
                return

        else:

            if self.substituicoes_c2 >= self.max_substituicoes:
                return

        # jogadores de linha em campo neste momento (goleiro nao entra
        # no rodizio de substituicao)
        em_campo = [
            j for j in clube.titulares
            if not j.expulso
            and j.posicao != "Goleiro"
        ]

        if not em_campo:
            return

        em_campo.sort(
            key=lambda j: j.energia
        )

        saindo = em_campo[0]

        entrando = self.escolher_substituto(
            clube,
            saindo
        )

        if entrando is None:
            return

        self._trocar(clube, saindo, entrando, minuto)

    def substituicoes_feitas(self, clube):
        return (
            self.substituicoes_c1
            if clube == self.clube1
            else self.substituicoes_c2
        )

    def _trocar(self, clube, saindo, entrando, minuto):
        """A troca em si, da IA ou do técnico (simulação interativa)."""

        # entra zerado (podia ter estatistica de partida antiga)
        entrando.resetar_estatisticas_partida()

        # a troca acontece so na escalacao da partida (titulares/reservas),
        # nunca em clube.jogadores, que e o elenco fixo da temporada
        clube.titulares.remove(saindo)
        clube.titulares.append(entrando)
        # quem entra fica na vaga de quem saiu (v1.3)
        entrando.vaga, saindo.vaga = saindo.vaga, None
        entrando.slot, saindo.slot = saindo.slot, None

        clube.reservas.remove(entrando)
        clube.reservas.append(saindo)

        self.substituicoes_log.append({
            "minuto": minuto,
            "sai": saindo,
            "entra": entrando,
        })

        if entrando not in self.estatisticas:

            self.estatisticas[entrando] = {
                "gols": 0,
                "assistencias": 0,
                "passes": 0,
                "desarmes": 0,
                "nota": 6.0,
            }

        if clube == self.clube1:
            self.substituicoes_c1 += 1
        else:
            self.substituicoes_c2 += 1

        self.adicionar_evento(
            minuto,
            "substituicao",
            entrando
        )
    
    #Simulação interativa (v1.2)

    def _clube_por_nome(self, nome):
        return next(
            (c for c in (self.clube1, self.clube2) if c.nome == nome), None
        )

    def aplicar_decisoes(self, minuto):
        """Decisões do técnico marcadas para este minuto, antes do lance.
        Foram validadas ao entrar e a simulação é determinística, mas uma
        que não caiba mais é ignorada em vez de derrubar a rodada."""

        for decisao in self.decisoes:
            if decisao["minuto"] != minuto:
                continue
            clube = self._clube_por_nome(decisao["clube"])
            if clube is None:
                continue
            if "tatica" in decisao:
                clube.tatica = decisao["tatica"]
                continue
            if "formacao" in decisao:
                # muda a postura (mod_ataque/mod_defesa); os jogadores em
                # campo são os mesmos — quem joga muda por substituição
                clube.formacao = decisao["formacao"]
                continue
            if self.motivo_substituicao_invalida(
                clube, decisao["sai"], decisao["entra"]
            ):
                continue
            saindo = next(j for j in clube.titulares if j.nome == decisao["sai"])
            entrando = next(j for j in clube.reservas if j.nome == decisao["entra"])
            self._trocar(clube, saindo, entrando, minuto)

    def motivo_substituicao_invalida(self, clube, nome_sai, nome_entra):
        """Por que a troca não pode ser feita agora (None se pode)."""

        if self.substituicoes_feitas(clube) >= self.max_substituicoes:
            return f"As {self.max_substituicoes} substituições já foram feitas"
        saindo = next((j for j in clube.titulares if j.nome == nome_sai), None)
        if saindo is None:
            return f"{nome_sai} não está em campo"
        if saindo.expulso:
            return f"{nome_sai} foi expulso e não pode ser substituído"
        entrando = next((j for j in clube.reservas if j.nome == nome_entra), None)
        if entrando is None:
            return f"{nome_entra} não está no banco"
        if entrando in self.estatisticas:   # já jogou e saiu
            return f"{nome_entra} já saiu e não pode voltar"
        return motivo_goleiro(saindo.posicao, entrando.posicao)

    def _registro_do_minuto(self, minuto):
        return {
            "minuto": minuto,
            "lance": self._lance,
            "posse": [self.posse_c1, self.posse_c2],
            "finalizacoes": [self.finalizacoes_c1, self.finalizacoes_c2],
            "no_gol": [self.finalizacoes_gol_c1, self.finalizacoes_gol_c2],
            "escanteios": [self.escanteios_c1, self.escanteios_c2],
        }

    def _placar_ate(self, minuto):
        """Placar com os gols até `minuto` (o de pênalti não passa por
        gols_c1/gols_c2 durante o jogo, só pelos eventos)."""

        placar = [0, 0]
        for evento in self.eventos:
            if evento["tipo"] in ("gol", "penalti") and evento["minuto"] <= minuto:
                placar[0 if self._clube_do(evento["jogador"]) == self.clube1 else 1] += 1
        return placar

    def foto_do_momento(self, minuto):
        """Quem está em campo e no banco ao fim de `minuto`, com energia,
        cartões e a nota até ali: o que o técnico vê ao pausar."""

        placar = self._placar_ate(minuto)

        def em_campo(j, gols_pro, gols_contra):
            stats = self.estatisticas.get(j, {"gols": 0, "assistencias": 0})
            return {
                "nome": j.nome,
                "numero": j.numero,
                "posicao": j.posicao,
                "funcao": j.funcao,
                "vaga": j.vaga,
                "overall_vaga": j.overall_em_campo(),
                "overall": j.overall,
                "energia": round(j.energia),
                "amarelos": j.amarelos_partida,
                "expulso": j.expulso,
                "gols": stats["gols"],
                "nota": round(self._nota(j, stats, gols_pro, gols_contra), 1),
            }

        def no_banco(j):
            return {
                "nome": j.nome,
                "numero": j.numero,
                "posicao": j.posicao,
                "funcao": j.funcao,
                "overall_por_posicao": j.overall_por_posicao(),
                "overall": j.overall,
                "energia": round(j.energia),
                "disponivel": j not in self.estatisticas,
            }

        clubes = []
        for i, clube in enumerate((self.clube1, self.clube2)):
            pro, contra = placar[i], placar[1 - i]
            clubes.append({
                "clube": clube.nome,
                "tatica": clube.tatica,
                "formacao": clube.formacao,
                "substituicoes_restantes": (
                    self.max_substituicoes - self.substituicoes_feitas(clube)
                ),
                "em_campo": [em_campo(j, pro, contra) for j in clube.titulares],
                "banco": [no_banco(j) for j in clube.reservas],
            })

        return {"minuto": minuto, "placar": placar, "clubes": clubes}

    #Escolhas

    def escolher_artilheiro(
        self,
        clube
    ):

        candidatos = []
        pesos = []

        for jogador in clube.titulares:

            if jogador.expulso or jogador.posicao == "Goleiro":
                continue

            peso = jogador.peso_gol()

            if peso > 0:
                candidatos.append(jogador)
                # ao quadrado: concentra os gols nos melhores finalizadores
                pesos.append(peso ** 2)

        if not candidatos:
            return None

        return random.choices(candidatos, weights=pesos, k=1)[0]
    
    def escolher_cobrador(self, clube):

        cobradores = [
            j for j in clube.titulares
            if j.posicao != "Goleiro"
            and not j.expulso
        ]

        pesos = []

        # quem bate é quem finaliza bem (v1.3; antes, o overall)
        for jogador in cobradores:

            finalizacao = jogador.atributo("finalizacao")
            if jogador.posicao == "Atacante":
                peso = finalizacao * 4

            elif jogador.posicao == "Meio-Campo":
                peso = finalizacao * 2

            else:  # Defesa
                peso = max(1, finalizacao // 8)

            pesos.append(peso)

        if not cobradores:
            return None

        return random.choices(
            cobradores,
            weights=pesos,
            k=1
        )[0]
    
    def distribuir_assistencia(
        self,
        clube,
        artilheiro
    ):

        lista = []

        for jogador in clube.titulares:

            if jogador.expulso:
                continue

            if (
                jogador != artilheiro
                and not jogador.expulso
            ):

                peso = jogador.peso_assistencia()

                if peso > 0:
                    lista.extend([jogador] * peso)

        if lista and random.random() < 0.70:

            assistente = random.choice(lista)

            assistente.assistencias += 1
            self.estatisticas[assistente]["assistencias"] += 1
    
    #Cartões
    
    def _avancar_pendencias(self):
        """A partida ter acontecido faz suspensão e lesão andarem uma rodada
        para os dois clubes (os afetados já ficaram de fora em escalar_time)."""
        for clube in (self.clube1, self.clube2):
            for jogador in clube.jogadores:
                if jogador.jogos_suspensao > 0:
                    jogador.jogos_suspensao -= 1
                if jogador.rodadas_lesao > 0:
                    jogador.rodadas_lesao -= 1

    # ~1 lesão a cada ~11 partidas de um clube
    CHANCE_LESAO = 0.09

    def _gravidade_lesao(self):
        r = random.random()
        if r < 0.60:
            return random.randint(1, 2)      # pancada / entorse
        if r < 0.90:
            return random.randint(3, 5)      # estiramento
        return random.randint(6, 12)         # lesão séria

    def sortear_lesoes(self):
        """Depois do apito: cada clube pode perder um titular por lesão nas
        próximas rodadas. Adiciona um evento `lesao` na linha do tempo."""
        for clube in (self.clube1, self.clube2):
            if random.random() > self.CHANCE_LESAO:
                continue

            em_campo = [j for j in clube.titulares if not j.lesionado]
            if not em_campo:
                continue

            vitima = random.choice(em_campo)
            vitima.rodadas_lesao = self._gravidade_lesao()
            self.adicionar_evento(
                random.randint(10, 90), "lesao", vitima
            )

    #Eventos
    
    def adicionar_evento(
        self,
        minuto,
        tipo,
        jogador
    ):

        simbolos = {
            "gol": "⚽",
            "assistencia": "🅰️",
            "penalti": "⚽ (P)",
            "penalti_perdido": "❌ (P)",
            "chute_fora": "💨",
            "cartao_amarelo": "🟨",
            "expulsao": "🟥",
            "defesa_goleiro": "🧤",
            "penalti_defendido": "🧤 (P)",
            "substituicao": "🔄",
            "lesao": "🚑",
        }

        simbolo = simbolos.get(
            tipo,
            "•"
        )

        texto = (
            f"{minuto}' "
            f"{simbolo} "
            f"{jogador.nome}"
        )

        self.eventos.append({
            "minuto": minuto,
            "tipo": tipo,
            "jogador": jogador,
            "texto": texto
        })
            
    def processar_eventos(self):

        self.eventos.sort(
            key=lambda e: e["minuto"]
        )

        expulsos = set()
        eventos_validos = []

        for evento in self.eventos:

            jogador = evento.get("jogador", None)

            if jogador and jogador in expulsos:
                continue

            eventos_validos.append(evento)

            if evento.get("tipo") == "expulsao" and jogador:
                expulsos.add(jogador)

        self.eventos = eventos_validos
    
    def mostrar_eventos(self):

        print("\nEVENTOS")

        for evento in sorted(
            self.eventos,
            key=lambda e: e["minuto"]
        ):

            print(
                evento.get(
                    "texto",
                    "Evento"
                )
            )
    
    #Estatísticas
    
    def criar_estatisticas(self):

        self.estatisticas = {}

        # quem começou jogando (para o snapshot da escalação; um titular pode
        # sair e voltar quando o substituto entra por outro companheiro)
        self.titulares_iniciais = set(
            self.clube1.titulares + self.clube2.titulares
        )

        # so quem comeca jogando. Reservas entram no dict apenas se forem
        # acionados em realizar_substituicao (senao contariam jogo e nota
        # sem terem entrado em campo).
        for jogador in (
            self.clube1.titulares +
            self.clube2.titulares
        ):

            self.estatisticas[jogador] = {
                "gols":0,
                "assistencias":0,
                "passes":0,
                "desarmes":0,
                "nota":6.0
            }

        return self.estatisticas

    def verificar_hat_tricks(
        self,
    ):

        for jogador in self.estatisticas:

            if self.estatisticas[jogador]["gols"] >= 3:

                jogador.hat_tricks += 1

                print(
                    f"\n🎩 HAT-TRICK DE "
                    f"{jogador.nome}!"
                )
    
    def _nota(self, jogador, stats, gols_pro, gols_contra):
        """Nota de 0 a 10 da atuação, dado o placar do ponto de vista do
        clube do jogador. Pura: serve ao fim do jogo e na pausa."""

        nota = 6.0

        gols = stats["gols"]
        assistencias = stats["assistencias"]

        saldo = gols_pro - gols_contra
        clean_sheet = gols_contra == 0

        # ==========================
        # AÇÕES DA PARTIDA
        # ==========================

        if jogador.posicao == "Atacante":

            nota += gols * 1.6
            nota += assistencias * 1.0
            nota += jogador.chutes_gol_partida * 0.15
            nota += jogador.dribles_partida * 0.06

        elif jogador.posicao == "Meio-Campo":

            nota += gols * 1.3
            nota += assistencias * 1.2
            nota += jogador.passes_chave_partida * 0.09
            nota += jogador.interceptacoes_partida * 0.05
            nota += jogador.dribles_partida * 0.04

        elif jogador.posicao == "Defesa":

            nota += gols * 1.6
            nota += assistencias * 0.8
            nota += jogador.desarmes_partida * 0.07
            nota += jogador.interceptacoes_partida * 0.06
            nota += jogador.cortes_partida * 0.03

            if clean_sheet:
                nota += 0.9

        elif jogador.posicao == "Goleiro":

            nota += jogador.defesas_partida * 0.10

            if clean_sheet:
                nota += 0.8

            nota -= jogador.gols_sofridos_partida * 0.18

        # ==========================
        # RESULTADO
        # ==========================

        if saldo > 0:
            nota += 0.4

        elif saldo < 0:
            nota -= 0.25

        # ==========================
        # BÔNUS EXTRAS
        # ==========================

        if (
            jogador.posicao == "Atacante"
            and saldo >= 2
        ):
            nota += 0.3

        # atuação de destaque: dois ou mais gols
        if gols >= 2:
            nota += 0.4

        if (
            jogador.posicao in ("Atacante", "Meio-Campo")
            and gols > 0
            and assistencias > 0
        ):
            nota += 0.3

        if (
            jogador.posicao == "Goleiro"
            and saldo == 0
            and clean_sheet
        ):
            nota += 0.2

        # ==========================
        # LIMITA NOTA
        # ==========================

        nota = max(0, min(10, nota))

        return nota

    def calcular_notas(self):

        melhor_jogador = None
        maior_nota = 0

        for jogador in self.estatisticas:

            time1 = jogador in self.clube1.jogadores

            if time1:
                gols_pro, gols_contra = self.gols_c1, self.gols_c2
            else:
                gols_pro, gols_contra = self.gols_c2, self.gols_c1

            nota = self._nota(
                jogador, self.estatisticas[jogador], gols_pro, gols_contra
            )

            # guarda a nota da partida (o snapshot em `atuacao` usa isto)
            self.estatisticas[jogador]["nota"] = round(nota, 2)

            jogador.soma_nota += nota
            jogador.partidas += 1

            if nota > jogador.melhor_nota:
                jogador.melhor_nota = nota

            if nota < jogador.pior_nota:
                jogador.pior_nota = nota

            # ==========================
            # MELHOR EM CAMPO
            # ==========================

            if melhor_jogador is None:
                melhor_jogador = jogador
                maior_nota = nota

            elif (
                nota > maior_nota
                or (
                    nota == maior_nota
                    and (
                        self.estatisticas[jogador]["gols"],
                        self.estatisticas[jogador]["assistencias"]
                    ) > (
                        self.estatisticas[melhor_jogador]["gols"],
                        self.estatisticas[melhor_jogador]["assistencias"]
                    )
                )
            ):
                melhor_jogador = jogador
                maior_nota = nota

        if melhor_jogador is not None:
            melhor_jogador.melhor_em_campo += 1

        return melhor_jogador, maior_nota
    
    def mostrar_melhor_em_campo(self, jogador, nota):

        print("\n⭐ MELHOR EM CAMPO")

        print(
            f"{jogador.nome} "
            f"({jogador.posicao}) "
            f"- Nota {nota:.1f}\n")

    #Snapshot para persistência / navegação

    def _clube_do(self, jogador):
        """Clube do jogador pelo elenco fixo da temporada, não pela escalação
        (o autor de um gol pode já ter sido substituído)."""

        return (
            self.clube1
            if jogador in self.clube1.jogadores
            else self.clube2
        )

    def resumo_eventos(self):
        """Timeline da partida como lista de dicts, em ordem cronológica.
        Chamar depois de `processar_eventos`."""

        sai_de = {
            s["entra"]: s["sai"].nome
            for s in self.substituicoes_log
        }

        linhas = []

        for evento in sorted(
            self.eventos,
            key=lambda e: e["minuto"]
        ):

            jogador = evento.get("jogador")

            clube = (
                self._clube_do(jogador)
                if jogador is not None
                else None
            )

            detalhe = None

            if (
                evento["tipo"] == "substituicao"
                and jogador in sai_de
            ):
                detalhe = f"sai {sai_de[jogador]}"

            linhas.append({
                "minuto": evento["minuto"],
                "tipo": evento["tipo"],
                "jogador": jogador.nome if jogador is not None else None,
                "clube": clube.nome if clube is not None else None,
                "detalhe": detalhe,
            })

        return linhas

    def resumo_escalacao(self):
        """Uma linha por jogador que entrou em campo: se foi titular, quando
        entrou/saiu, contribuição e nota. Chamar depois de `calcular_notas`."""

        # percorre as trocas em ordem, a última vale. Quem sai não volta mais
        # (escolher_substituto), mas a leitura continua certa se voltasse.
        entrou_min = {}
        saiu_min = {}

        for troca in self.substituicoes_log:
            sai, entra, minuto = troca["sai"], troca["entra"], troca["minuto"]

            saiu_min[sai] = minuto

            saiu_min.pop(entra, None)  # voltou a campo
            if entra not in self.titulares_iniciais:
                entrou_min[entra] = minuto

        atuacoes = []

        for jogador, stats in self.estatisticas.items():

            titular = jogador in self.titulares_iniciais

            atuacoes.append({
                "jogador": jogador.nome,
                "clube": self._clube_do(jogador).nome,
                "posicao": jogador.posicao,
                "titular": titular,
                "entrou_min": None if titular else entrou_min.get(jogador),
                "saiu_min": saiu_min.get(jogador),
                "gols": stats["gols"],
                "assistencias": stats["assistencias"],
                "nota": stats["nota"],
            })

        return atuacoes
    
    #Resultado
    
    def recalcular_placar(self):

        gols_c1 = 0
        gols_c2 = 0

        for evento in self.eventos:

            if evento["tipo"] in ["gol", "penalti"]:

                jogador = evento["jogador"]

                # elenco fixo, nao a escalacao — o autor do gol pode ter
                # sido substituido antes do fim
                if jogador in self.clube1.jogadores:
                    gols_c1 += 1
                else:
                    gols_c2 += 1

        self.gols_c1 = gols_c1
        self.gols_c2 = gols_c2
    
    def definir_resultado(self):

        if self.gols_c1 > self.gols_c2:
            self.resultado = f"{self.clube1.nome} venceu!"

        elif self.gols_c2 > self.gols_c1:
            self.resultado = f"{self.clube2.nome} venceu!"

        else:
            self.resultado = "Empate!"
    
    def mostrar_resultado(self):

        print(
            f"{self.clube1.nome} "
            f"{self.gols_c1} x "
            f"{self.gols_c2} "
            f"{self.clube2.nome}"
        )

        print(f"{self.resultado}\n")
    
    #Campeonato
    
    def atualizar_classificacao(self):

        if self.gols_c1 > self.gols_c2:

            self.clube1.pontos += 3
            self.clube1.vitorias += 1
            self.clube2.derrotas += 1

            self.clube1.atualizar_forma("V")
            self.clube2.atualizar_forma("D")

        elif self.gols_c2 > self.gols_c1:

            self.clube2.pontos += 3
            self.clube2.vitorias += 1
            self.clube1.derrotas += 1

            self.clube2.atualizar_forma("V")
            self.clube1.atualizar_forma("D")

        else:

            self.clube1.pontos += 1
            self.clube2.pontos += 1

            self.clube1.empates += 1
            self.clube2.empates += 1

            self.clube1.atualizar_forma("E")
            self.clube2.atualizar_forma("E")
    
    def atualizar_estatisticas_clubes(self):

        self.clube1.gols_marcados += self.gols_c1
        self.clube1.gols_sofridos += self.gols_c2

        self.clube2.gols_marcados += self.gols_c2
        self.clube2.gols_sofridos += self.gols_c1   
    
    def atualizar_clean_sheet(self):

        # credita o clean sheet so ao goleiro que estava em campo no fim
        # (titulares), dos dois lados igualmente.
        if self.gols_c2 == 0:

            for jogador in self.clube1.titulares:
                if jogador.posicao == "Goleiro":
                    jogador.clean_sheets += 1

        if self.gols_c1 == 0:

            for jogador in self.clube2.titulares:
                if jogador.posicao == "Goleiro":
                    jogador.clean_sheets += 1
            
    #Utilidade
    
    def forca_em_campo(self, clube):
        """Força do time neste momento: média de overall do XI ajustada por
        fadiga e expulsões (Clube.calcular_forca), mais o mando de campo se
        for o mandante — maior quanto maior a torcida dele."""

        forca = clube.calcular_forca()

        if clube is self.clube1:
            forca += torcida.mando_de_campo(clube.torcedores)

        return forca

    # atributos (v1.3). O nível de cada time já pesa pela força (overall);
    # os atributos entram pelo ESTILO — quanto o jogador está acima ou
    # abaixo do próprio overall naquilo — para não contar a força duas vezes.
    # As referências são as médias dos titulares da seed: o lance típico
    # sai como antes.
    REF_FINALIZACAO = 2       # quem chuta finaliza, em média, 2 acima do overall
    VANTAGEM_COBRADOR = -2    # FIN média de quem bate − nível médio dos goleiros
    REF_DUELO = 3             # o atacante típico leva essa vantagem de estilo
    PESO_DUELO = 0.015        # por ponto de vantagem
    DUELO_MAX = 0.25

    def duelo(self, atacante, defensor):
        """Quanto o atacante leva de vantagem de estilo sobre quem tentou
        parar o lance (−DUELO_MAX a +DUELO_MAX): velocidade e drible acima
        do próprio nível contra velocidade e marcação acima do dele — um
        ponta rápido contra um zagueiro lento. Sem defensor, 0."""
        if atacante is None or defensor is None:
            return 0.0
        ataque = (atacante.atributo("velocidade") + atacante.atributo("drible")) / 2
        defesa = (defensor.atributo("velocidade") + defensor.atributo("marcacao")) / 2
        vantagem = (
            (ataque - atacante.overall_em_campo())
            - (defesa - defensor.overall_em_campo())
            - self.REF_DUELO
        ) * self.PESO_DUELO
        return max(-self.DUELO_MAX, min(self.DUELO_MAX, vantagem))

    @staticmethod
    def nivel_goleiro(goleiro):
        """Reflexos e posicionamento juntos (um goleiro improvisado, de linha,
        usa o overall no gol)."""
        if goleiro.posicao != "Goleiro":
            return goleiro.overall_em_campo()
        return (goleiro.atributo("reflexos") + goleiro.atributo("posicionamento")) / 2

    def adversario(self, clube):

        if clube is self.clube1:
            return self.clube2

        return self.clube1

    def fator_ataque(self, clube_atacando):
        """Multiplicador da chance de gol: > 1 quando o ataque é mais forte
        que a defesa adversária, < 1 quando é mais fraco. Centrado em 1.

        A tática entra aqui: o clube ofensivo cria mais (mod_ataque) e o
        adversário defensivo concede menos (mod_defesa)."""

        adversario = self.adversario(clube_atacando)

        ataque = self.forca_em_campo(clube_atacando)
        defesa = self.forca_em_campo(adversario)

        if defesa <= 0:
            return 1.55

        fator = (ataque / defesa) ** 3
        fator *= clube_atacando.mod_ataque()
        fator /= adversario.mod_defesa()

        return max(0.7, min(1.55, fator))

    def calcular_posse(self):

        f1 = self.forca_em_campo(self.clube1)
        f2 = self.forca_em_campo(self.clube2)

        if f1 <= 0 or f2 <= 0:
            self.posse_c1 = 50
            self.posse_c2 = 50
            return

        # elevar a força a uma potência transforma diferenças pequenas de
        # overall em diferenças visíveis de posse
        peso1 = f1 ** 4
        peso2 = f2 ** 4

        self.posse_c1 = round(peso1 / (peso1 + peso2) * 100)
        self.posse_c2 = 100 - self.posse_c1


def motivo_goleiro(setor_sai, setor_entra):
    """Goleiro só troca com goleiro (v1.3): nem vai para a linha, nem um
    jogador de linha vai para o gol. None se a troca pode."""
    if (setor_sai == "Goleiro") != (setor_entra == "Goleiro"):
        return "Goleiro só pode ser trocado por outro goleiro"
    return None
