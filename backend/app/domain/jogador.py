

import random

from app.domain import atributos, posicoes
from app.domain.fama import fator_valor


# o titular típico da liga tem físico 1 acima do próprio overall (seed): o
# efeito do físico é centrado aí, então um jogador típico cansa como antes
REF_FISICO = 1


class Jogador:

    # amarelos acumulados no campeonato que disparam uma suspensão automática
    AMARELOS_PARA_SUSPENSAO = 5

    def __init__(self, nome, idade, posicao, overall,
                 potencial=None, contrato_anos=3, multa_rescisoria=None,
                 salario=None, funcao=None, secundarias=None,
                 fama=0, temporadas_no_clube=0):
        self.nome = nome
        self.idade = idade
        self.posicao = posicao   # setor (Goleiro, Defesa...): o motor usa
        # posição específica (v1.3): zagueiro, lateral, volante... Sem ela
        # (jovens de saves antigos), a padrão do setor, com as outras do
        # setor como secundárias: rende em qualquer vaga do setor dele
        self.funcao = posicoes.nome_atual(funcao or posicoes.PADRAO_DO_SETOR[posicao])
        if posicoes.SETOR[self.funcao] != posicao:
            raise ValueError(f"{nome}: {self.funcao} não é do setor {posicao}")
        if secundarias is None:
            secundarias = () if funcao else posicoes.do_setor(posicao, self.funcao)
        self.secundarias = tuple(posicoes.nome_atual(f) for f in secundarias)
        self.vaga = None   # posição em que está escalado (Clube.escalar_time)
        self.slot = None   # e a vaga no desenho da formação
        self.overall = overall
        self.numero = None   # camisa (v1.1): dado ao entrar no clube
        # mercado (v0.7): potencial nunca fica abaixo do overall atual
        self.potencial = max(overall, potencial or overall)
        self.contrato_anos = contrato_anos   # temporadas restantes
        # valor fixo de contrato; None = sem multa (o clube só vende se quiser)
        self.multa_rescisoria = multa_rescisoria
        # salário de CONTRATO, por temporada: fica fixo até a renovação, mesmo
        # que o jogador evolua. Sem contrato informado, começa no de mercado.
        self.salario = salario if salario is not None else self.salario_referencia()
        # fama (v1.4): do jogador, vai com ele; o tempo de casa zera quando
        # ele muda de clube (ver app.domain.fama)
        self.fama = fama
        self.temporadas_no_clube = temporadas_no_clube
        # na lista de transferências do clube (v1.7); sai dela ao mudar de clube
        self.a_venda = False
        # papel no elenco e humor (v1.7, só no clube do técnico): ver
        # app.domain.papeis. Os contadores são da temporada, só da liga
        self.papel = None
        self.humor = "contente"
        self.titularidades = 0
        self.jogos_disponivel = 0
        self.gols = 0
        self.assistencias = 0
        self.partidas = 0
        self.soma_nota = 0.0
        self.melhor_nota = 0.0
        self.pior_nota = 10.0
        self.melhor_em_campo = 0
        self.clean_sheets = 0
        self.hat_tricks = 0
        self.penaltis = 0
        self.penaltis_perdidos = 0
        self.faltas = 0
        self.amarelos = 0
        self.vermelhos = 0
        # Estatisticas ofensivas 
        self.chutes_partida = 0
        self.chutes_gol_partida = 0
        self.passes_chave_partida = 0
        self.dribles_partida = 0
        # Estatisticas defensivas 
        self.desarmes_partida = 0
        self.interceptacoes_partida = 0
        self.cortes_partida = 0
        self.bloqueios_partida = 0
        # Estatisticas Goleiro
        self.defesas_partida = 0
        self.cortes_partida = 0
        self.bloqueios_partida = 0
        # Disciplina
        self.faltas_partida = 0
        self.gols_sofridos_partida = 0
        # controle por partida
        self.amarelos_partida = 0
        self.expulso = False
        self.energia = 100
        self.condicao = "Normal"
        # suspensão (persiste entre partidas, ao contrário de `expulso`)
        self.jogos_suspensao = 0   # jogos que ainda vai cumprir de fora
        self.amarelos_ciclo = 0    # amarelos rumo à próxima suspensão
        self.rodadas_lesao = 0     # rodadas que ainda fica fora por lesão

    def overall_em(self, vaga):
        """Quanto o jogador rende jogando na `vaga` (ver app.domain.posicoes)."""
        return max(1, self.overall - posicoes.perda(
            self.funcao, vaga, self.secundarias
        ))

    @property
    def atributos(self):
        """{atributo: valor} (v1.3): os seis de linha, ou os de goleiro."""
        return atributos.de(self)

    def atributo(self, nome):
        return self.atributos[nome]

    def overall_por_posicao(self):
        """{posição: overall nela}, para a tela mostrar quanto rende em cada
        vaga (v1.3)."""
        return {f: self.overall_em(f) for f in posicoes.FUNCOES}

    def overall_em_campo(self):
        """O overall na vaga em que está escalado (o natural, fora do XI)."""
        return self.overall_em(self.vaga or self.funcao)

    @property
    def suspenso(self):
        return self.jogos_suspensao > 0

    @property
    def lesionado(self):
        return self.rodadas_lesao > 0

    @property
    def disponivel(self):
        return not (self.expulso or self.suspenso or self.lesionado)

    def registrar_amarelo(self):
        """Amarelo 'limpo' (não virou vermelho): conta para o acúmulo do
        campeonato. Devolve True quando fecha um ciclo e gera suspensão."""
        self.amarelos_ciclo += 1
        if self.amarelos_ciclo >= self.AMARELOS_PARA_SUSPENSAO:
            self.amarelos_ciclo = 0
            self.jogos_suspensao += 1
            return True
        return False
        
        
    def resetar_estatisticas_partida(self):

        self.chutes_partida = 0
        self.chutes_gol_partida = 0
        self.passes_chave_partida = 0
        self.dribles_partida = 0

        self.desarmes_partida = 0
        self.interceptacoes_partida = 0
        self.cortes_partida = 0
        self.bloqueios_partida = 0

        self.defesas_partida = 0
        self.gols_sofridos_partida = 0

        self.faltas_partida = 0

        self.amarelos_partida = 0
        self.expulso = False
        
    def mostrar(self):
        print(
            f"Nome: {self.nome}, "
            f"Idade: {self.idade}, "
            f"Posição: {self.posicao}, "
            f"Overall: {self.overall}"
        )
        
    def mostrar_nota(self):
        print(
            f"Nome: {self.nome}, "
            f"Posição: {self.posicao}, "
            f"Nota Média: {self.soma_nota}, "
            f"Melhor Nota: {self.melhor_nota}, "
            f"Pior Nota: {self.pior_nota}"
        )    
    
    def peso_gol(self):

        if self.posicao == "Goleiro":
            return 0

        if self.posicao == "Defesa":
            return 0

        if self.posicao == "Meio-Campo":
            base = 3

        elif self.posicao == "Atacante":
            base = 10

        else:
            return 0

        # o nível de finalização é o fator dominante: um atacante 88 finaliza
        # muito mais que um de 72, para existir uma disputa de artilharia. Com
        # os atributos (v1.3), meio overall, meio finalização: quem finaliza
        # melhor que o próprio nível ganha espaço sem virar o único artilheiro
        nivel = (self.overall + self.atributo("finalizacao")) / 2
        peso = base + (max(50, nivel) - 50) ** 1.7 / 22

        if self.condicao == "Cansado":
            peso *= 0.90

        elif self.condicao == "Exausto":
            peso *= 0.70

        return int(peso)
    
    def peso_assistencia(self):

        if self.posicao == "Goleiro":
            return 1

        base = {
            "Atacante": 7,
            "Meio-Campo": 13,
            "Defesa": 2
        }

        # o passe decide quem dá as assistências (v1.3; antes, o overall)
        peso = (
            base[self.posicao]
            + (self.atributo("passe") // 8)
        )

        if self.condicao == "Cansado":
            peso *= 0.90

        elif self.condicao == "Exausto":
            peso *= 0.70

        return int(peso)
    
    # --- mercado -----------------------------------------------------------
    # valor de mercado e salário de referência são CALCULADOS: derivam de
    # overall, idade e potencial, então nunca ficam desatualizados. Já o
    # salário que o jogador RECEBE (`self.salario`) é fato de contrato.

    @staticmethod
    def _base_overall(overall):
        # exponencial: cada ponto de overall vale ~22% a mais que o anterior,
        # então um 90 vale muito mais que dois 80
        return 5_000 * 1.22 ** (max(50, overall) - 50)

    def valor_mercado(self):
        """Valor de transferência (em dinheiro do jogo), múltiplo de 10 mil."""

        valor = self._base_overall(self.overall)

        if self.idade <= 21:
            valor *= 1.3
        elif self.idade <= 25:
            valor *= 1.15
        elif self.idade >= 33:
            valor *= 0.4
        elif self.idade >= 30:
            valor *= 0.7

        # margem de crescimento só pesa para quem ainda tem idade de evoluir
        if self.idade <= 24:
            valor *= 1 + 0.04 * (self.potencial - self.overall)

        # jogador famoso vende camisa e enche estádio: vale mais (v1.4)
        valor *= fator_valor(self.fama)

        return max(10_000, round(valor / 10_000) * 10_000)

    def salario_referencia(self):
        """Quanto o mercado paga por temporada a um jogador deste overall,
        múltiplo de mil. É a base das negociações de contrato; depende só do
        overall: paga-se pelo que o jogador rende hoje, não pelo que vai
        render."""
        return self.salario_de_mercado(self.overall)

    @classmethod
    def salario_de_mercado(cls, overall):
        """`salario_referencia` sem precisar de um Jogador (ex.: a partir de
        uma linha do banco)."""
        salario = 0.08 * cls._base_overall(overall)
        return max(1_000, round(salario / 1_000) * 1_000)

    def assinar_contrato(self, anos, salario, multa_rescisoria):
        self.contrato_anos = anos
        self.salario = salario
        self.multa_rescisoria = multa_rescisoria

    def nota_media(self):
        if self.partidas == 0:
            return 0.0
        
        return round(
            self.soma_nota / self.partidas, 2
        )
    
    def score_escalacao(self, preferido=False, vaga=None):

        score = self.overall_em(vaga) if vaga else self.overall

        # bônus por energia
        score += self.energia * 0.15

        # penalidade por condição
        if self.condicao == "Cansado":
            score -= 5

        elif self.condicao == "Exausto":
            score -= 15

        # o XI do técnico entra na frente de todos (Clube.escalar_time), menos
        # quem está "Exausto"; o bônus só desempata entre os que sobram. Fixar
        # os 11 e nunca rodar acumula fadiga e custa alguns pontos na tabela.
        if preferido:
            score += 12

        return score
    
    def mostrar_estatisticas(self):

        print("\n=== ESTATÍSTICAS ===")

        print(
            f"Nome: {self.nome}\n"
            f"Posição: {self.posicao}\n"
            f"Overall: {self.overall}\n"
            f"Jogos: {self.partidas}\n"
            f"Gols: {self.gols}\n"
            f"Assistências: {self.assistencias}\n"
            f"Melhores em campo: {self.melhor_em_campo}\n"
            f"Hat-tricks: {self.hat_tricks}\n"
            f"Pênaltis: {self.penaltis}\n"
            f"Pênaltis perdidos: {self.penaltis_perdidos}\n"
            f"Clean Sheets: {self.clean_sheets}\n"
            f"Nota Média: {self.nota_media()}\n"
            f"Melhor Nota: {round(self.melhor_nota,2)}\n"
            f"Pior Nota: {round(self.pior_nota,2)}\n"
        )
    
    def reduzir_energia(self):

        gasto = random.randint(3,6)

        if self.posicao == "Atacante":
            gasto += 3

        elif self.posicao == "Meio-Campo":
            gasto += 5

        elif self.posicao == "Defesa":
            gasto += 2

        # quem tem mais físico do que o próprio nível cansa menos (v1.3): ±1%
        # por ponto. Pelo estilo, não pelo valor: senão o time forte, que tem
        # tudo mais alto, ganharia de novo só por ser forte
        if self.posicao != "Goleiro":
            estilo = self.atributo("fisico") - self.overall - REF_FISICO
            gasto = round(gasto * max(0.8, min(1.2, 1 - estilo * 0.01)))

        self.energia = max(0, self.energia - gasto)

        self.atualizar_condicao()
    
    def atualizar_condicao(self):

        if self.energia <= 30:
            self.condicao = "Exausto"

        elif self.energia <= 60:
            self.condicao = "Cansado"

        else:
            self.condicao = "Normal"