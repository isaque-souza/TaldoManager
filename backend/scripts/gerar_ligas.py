"""Gera as seeds das ligas de jogadores fictícios (v2.5), no formato da
Premier (clubes.json e jogadores.json):

- data/seeds/taldo_b/: Liga Taldo B, clubes inventados;
- data/seeds/championship/: Championship 2023/24, os clubes reais do 1º
  ao 20º;
- data/seeds/laliga/: La Liga 2023/24, os clubes reais;
- data/seeds/segunda/: Segunda División 2023/24, 20 dos 22 clubes reais;
- data/seeds/brasileirao_b/: Série B de 2017, os clubes reais (a Série A
  de 2017 tem os jogadores reais: scripts/importar_brasileirao.py).

A força: nas Séries B vem da ordem dos clubes (o elenco do 1º gira em torno
de FORCA_TOPO e o do 20º em torno de FORCA_FUNDO — abaixo da Série A, para
que quem sobe sofra e quem cai seja favorito); na La Liga, cada clube tem
a sua. Os nomes não repetem os de nenhuma outra seed.

Determinístico: rodar de novo gera os mesmos arquivos. As ligas novas vão
sempre no FIM de `LIGAS`: o jogo acha o jogador pelo nome, e uma liga
gerada antes mudaria os nomes das seguintes (e quebraria os saves).

Uso (a partir da pasta backend/):
    python -m scripts.gerar_ligas
"""

import json
import random
import zlib
from pathlib import Path

from app.domain import livres, posicoes
from app.domain.jogador import Jogador
from scripts.importar_brasileirao import RIVAIS_NA_SERIE_B
from scripts.importar_premier import RIVAIS_NA_CHAMPIONSHIP, dar_funcoes, potencial, xi

SEEDS = Path(__file__).resolve().parent.parent / "data" / "seeds"

FORCA_TOPO, FORCA_FUNDO = 72, 65
TETO = 5                      # ninguém passa a força do clube + isto
OVERALL_MIN = 50
CORTE = {"GK": 3, "DF": 7, "MF": 8, "FW": 5}       # 23, como na Premier
TITULARES_DO_SETOR = {"GK": 1, "DF": 4, "MF": 3, "FW": 3}
CHANCE_MULTA = 0.55           # como na Taldo; na Inglaterra não há multa

NOMES_BR = [
    "Alan", "Alex", "Anderson", "André", "Bernardo", "Bruno", "Caio", "Carlos",
    "César", "Cristian", "Daniel", "Danilo", "Diego", "Douglas", "Eduardo",
    "Elias", "Emerson", "Everton", "Fabiano", "Fábio", "Felipe", "Fernando",
    "Gilberto", "Guilherme", "Heitor", "Hugo", "Iago", "Ítalo", "Jean",
    "Jefferson", "Jonas", "Jorge", "José", "Júlio", "Kaique", "Leandro",
    "Léo", "Luciano", "Luís", "Marcelo", "Márcio", "Marcos", "Mateus",
    "Maurício", "Murilo", "Nathan", "Nelson", "Otávio", "Paulo", "Rafael",
    "Renan", "Renato", "Ricardo", "Robson", "Rodrigo", "Rogério", "Samuel",
    "Sérgio", "Thales", "Tiago", "Ulisses", "Vagner", "Valdir", "Wallace",
    "Washington", "Wellington", "Willian", "Yago", "Yuri", "Zeca",
]
SOBRENOMES_BR = [
    "Alves", "Amaral", "Andrade", "Antunes", "Aragão", "Arruda", "Azevedo",
    "Bastos", "Batista", "Bezerra", "Brandão", "Brito", "Cabral", "Caldeira",
    "Campos", "Cardoso", "Carneiro", "Castro", "Cavalcanti", "Coelho",
    "Correia", "Cunha", "Dantas", "Duarte", "Esteves", "Fagundes", "Farias",
    "Figueiredo", "Fonseca", "Freitas", "Galvão", "Garcia", "Godoy",
    "Guimarães", "Leal", "Leite", "Lopes", "Macedo", "Machado", "Magalhães",
    "Matos", "Medeiros", "Meireles", "Mendes", "Menezes", "Miranda",
    "Monteiro", "Moraes", "Moreira", "Moura", "Nogueira", "Novaes", "Pacheco",
    "Paiva", "Peixoto", "Pinheiro", "Pires", "Prado", "Queiroz", "Ramos",
    "Rezende", "Sampaio", "Siqueira", "Soares", "Tavares", "Toledo",
    "Valente", "Vasconcelos", "Viana", "Vieira",
]
NOMES_EN = [
    "Aaron", "Adam", "Alfie", "Ben", "Billy", "Bradley", "Callum", "Charlie",
    "Connor", "Dan", "Danny", "Dean", "Dominic", "Elliot", "Ethan", "Finley",
    "Frankie", "Freddie", "George", "Harrison", "Harry", "Harvey", "Isaac",
    "Jack", "Jacob", "Jake", "James", "Jamie", "Jason", "Joe", "Jordan",
    "Josh", "Kai", "Kieran", "Kyle", "Lewis", "Liam", "Luke", "Mark", "Mason",
    "Matt", "Max", "Michael", "Nathan", "Ollie", "Owen", "Reece", "Rhys",
    "Ricky", "Ryan", "Sam", "Scott", "Sean", "Stuart", "Taylor", "Theo",
    "Tom", "Tyler", "Will", "Zak",
]
SOBRENOMES_EN = [
    "Adams", "Ainsworth", "Barker", "Barnes", "Bennett", "Bishop", "Bowen",
    "Bradshaw", "Brooks", "Burgess", "Butler", "Carter", "Chapman", "Clayton",
    "Coleman", "Collins", "Cooper", "Crawford", "Dawson", "Dixon", "Doyle",
    "Edwards", "Ellis", "Evans", "Fletcher", "Ford", "Foster", "Gibson",
    "Gordon", "Graham", "Grant", "Gray", "Hall", "Hamilton", "Harper",
    "Harris", "Hayes", "Holmes", "Howard", "Hudson", "Hunt", "Jenkins",
    "Johnson", "Kelly", "Kennedy", "Knight", "Lawrence", "Lloyd", "Marshall",
    "Mason", "Matthews", "Mills", "Mitchell", "Morgan", "Morris", "Murphy",
    "Murray", "Newton", "Owens", "Palmer", "Parker", "Payne", "Pearce",
    "Phillips", "Powell", "Price", "Reid", "Reynolds", "Richards", "Riley",
    "Robinson", "Rogers", "Russell", "Shaw", "Simpson", "Spencer", "Stevens",
    "Stone", "Sutton", "Taylor", "Turner", "Walker", "Wallace", "Ward",
    "Watson", "Webb", "Wells", "West", "Wilkinson", "Wood",
]
NOMES_ES = [
    "Adrián", "Aitor", "Alberto", "Alejandro", "Álex", "Alfonso", "Álvaro",
    "Andrés", "Ángel", "Antonio", "Borja", "Carlos", "César", "Cristian",
    "Dani", "David", "Diego", "Eduardo", "Enrique", "Eric", "Fernando", "Fran",
    "Gerard", "Gonzalo", "Guillermo", "Héctor", "Hugo", "Iker", "Ignacio",
    "Iñaki", "Íñigo", "Isma", "Iván", "Javi", "Jesús", "Joan", "Joel", "Jon",
    "Jorge", "José", "Juan", "Julen", "Kike", "Lucas", "Luis", "Manu", "Marc",
    "Marcos", "Mario", "Martín", "Miguel", "Mikel", "Nacho", "Óscar", "Pablo",
    "Pau", "Pedro", "Rafa", "Raúl", "Roberto", "Rubén", "Samu", "Santi",
    "Sergio", "Unai", "Víctor", "Xabi", "Yeray",
]
SOBRENOMES_ES = [
    "Aguirre", "Alonso", "Arrieta", "Barrios", "Blanco", "Bravo", "Caballero",
    "Calvo", "Campos", "Cano", "Carrasco", "Castillo", "Cortés", "Crespo",
    "Delgado", "Domínguez", "Echeverría", "Escudero", "Esteban", "Etxeberria",
    "Fuentes", "Gallego", "Garrido", "Gil", "Giménez", "Guerrero", "Herrera",
    "Hidalgo", "Ibáñez", "Iglesias", "Jiménez", "Lara", "León", "Lorenzo",
    "Lozano", "Marín", "Márquez", "Medina", "Méndez", "Molina", "Montero",
    "Mora", "Morales", "Moreno", "Muñoz", "Nieto", "Núñez", "Ortega", "Ortiz",
    "Pascual", "Pastor", "Peña", "Prieto", "Ramírez", "Reyes", "Rivas",
    "Román", "Rubio", "Sáez", "Salazar", "Sánchez", "Santana", "Santos",
    "Serrano", "Soler", "Suárez", "Torres", "Urrutia", "Vargas", "Vázquez",
    "Vega", "Velasco", "Vidal", "Zabala",
]
NACIONALIDADES_ES = ["ESP"] * 16 + ["ARG", "URU", "FRA", "POR", "MAR", "BRA", "COL", "SEN"]

NACIONALIDADES_EN = ["ENG"] * 14 + ["SCO", "WAL", "IRL", "NIR"] * 2 + ["FRA", "NED", "JAM", "NGA"]

# nome -> (sigla, cor primária, secundária, camisa, escudo, caixa mi, torcida mi)
CHAMPIONSHIP = {
    "Leicester City": ("LEI", "#003090", "#FDBE11", "lisa", "classico", 6, 0.9),
    "Ipswich Town": ("IPS", "#0044A9", "#FFFFFF", "lisa", "classico", 3, 0.4),
    "Leeds United": ("LEE", "#FFFFFF", "#1D428A", "lisa", "classico", 6, 1.2),
    "Southampton": ("SOU", "#D71920", "#FFFFFF", "listras", "classico", 5, 0.6),
    "West Brom": ("WBA", "#122F67", "#FFFFFF", "listras", "classico", 3, 0.5),
    "Norwich City": ("NOR", "#FFF200", "#00A650", "lisa", "redondo", 3, 0.4),
    "Hull City": ("HUL", "#F5A12D", "#000000", "listras", "moderno", 2, 0.25),
    "Middlesbrough": ("MID", "#E11B22", "#FFFFFF", "lisa", "classico", 3, 0.35),
    "Coventry City": ("COV", "#87CEEB", "#FFFFFF", "lisa", "redondo", 2, 0.3),
    "Preston": ("PNE", "#FFFFFF", "#002D62", "lisa", "classico", 1.5, 0.2),
    "Bristol City": ("BRC", "#E21B23", "#FFFFFF", "lisa", "redondo", 2, 0.25),
    "Cardiff City": ("CAR", "#0070B5", "#FFFFFF", "lisa", "redondo", 2, 0.3),
    "Millwall": ("MIL", "#001D5E", "#FFFFFF", "lisa", "moderno", 1.5, 0.2),
    "Swansea City": ("SWA", "#FFFFFF", "#000000", "lisa", "moderno", 2, 0.3),
    "Watford": ("WAT", "#FBEE23", "#ED2127", "lisa", "moderno", 3, 0.3),
    "Sunderland": ("SUN", "#EB172B", "#FFFFFF", "listras", "classico", 3, 0.8),
    "Stoke City": ("STK", "#E03A3E", "#FFFFFF", "listras", "classico", 3, 0.35),
    "QPR": ("QPR", "#1D5BA4", "#FFFFFF", "aros", "moderno", 2, 0.25),
    "Blackburn Rovers": ("BLB", "#009EE0", "#FFFFFF", "metade", "classico", 2, 0.3),
    "Sheffield Wednesday": ("SHW", "#1F5FAD", "#FFFFFF", "listras", "classico", 2, 0.5),
}
# clássicos dentro da Championship e com clubes da Premier (o par vai nas
# duas seeds; ver RIVAIS_NA_PREMIER)
CLASSICOS_CHAMPIONSHIP = [
    ("Norwich City", "Ipswich Town"),
    ("Cardiff City", "Swansea City"),
    ("Bristol City", "Cardiff City"),
    ("Middlesbrough", "Sunderland"),
    ("Preston", "Blackburn Rovers"),
    ("Leeds United", "Hull City"),
    ("Coventry City", "Leicester City"),
    ("Stoke City", "West Brom"),
    ("Millwall", "QPR"),
    ("Southampton", "Watford"),
]
RIVAIS_NA_PREMIER = RIVAIS_NA_CHAMPIONSHIP   # a lista mora no importador da Premier

# Liga Taldo B, da mais forte para a mais fraca:
# nome -> (sigla, cor primária, secundária, camisa, escudo, caixa mi, torcida mi)
TALDO_B = {
    "Taldo Wanderers": ("TWA", "#5B2C83", "#FFFFFF", "lisa", "classico", 5, 1.4),
    "Taldo Albion": ("TAL", "#0B5394", "#FFFFFF", "listras", "classico", 4, 1.1),
    "Taldo Rovers": ("TRO", "#1E7B3A", "#FFFFFF", "aros", "redondo", 4, 1.0),
    "Olímpico Taldo": ("OLT", "#FFFFFF", "#C9A227", "faixa", "moderno", 4, 0.9),
    "Taldo Town": ("TTO", "#E06666", "#FFFFFF", "lisa", "redondo", 3, 0.8),
    "Racing Taldo": ("RCT", "#6FA8DC", "#FFFFFF", "listras", "classico", 3, 0.8),
    "Taldo County": ("TCO", "#38761D", "#F1C232", "lisa", "classico", 3, 0.6),
    "Taldo Ferroviário": ("TFE", "#CC0000", "#000000", "metade", "classico", 3, 0.7),
    "Operário Taldo": ("OPT", "#000000", "#FFFFFF", "listras", "moderno", 2, 0.6),
    "Taldo Unidos": ("TUN", "#073763", "#E69138", "lisa", "redondo", 2, 0.5),
    "Taldo Atlântico": ("TAT", "#0097A7", "#FFFFFF", "faixa", "moderno", 2, 0.5),
    "Taldo Norte": ("TNO", "#274E13", "#FFFFFF", "lisa", "classico", 2, 0.45),
    "Taldo Sul": ("TSU", "#990000", "#FFD966", "lisa", "classico", 2, 0.45),
    "Taldo Litoral": ("TLI", "#3D85C6", "#FFE599", "listras", "redondo", 2, 0.4),
    "Taldo Serrano": ("TSE", "#783F04", "#FFFFFF", "lisa", "classico", 1.5, 0.3),
    "Taldo Vale": ("TVA", "#6AA84F", "#000000", "metade", "moderno", 1.5, 0.3),
    "Taldo Porto": ("TPO", "#1C4587", "#FFFFFF", "aros", "classico", 1.5, 0.3),
    "Taldo Central": ("TCE", "#B45F06", "#000000", "lisa", "redondo", 1.5, 0.25),
    "Taldo Phoenix": ("TPH", "#E69138", "#990000", "faixa", "moderno", 1, 0.2),
    "Taldo Comets": ("TCM", "#674EA7", "#F1C232", "lisa", "moderno", 1, 0.15),
}
CLASSICOS_TALDO_B = [
    ("Taldo Norte", "Taldo Sul"),
    ("Taldo Ferroviário", "Operário Taldo"),
    ("Taldo Wanderers", "Taldo Rovers"),
    ("Taldo Litoral", "Taldo Porto"),
    ("Taldo Serrano", "Taldo Vale"),
    ("Taldo Albion", "Taldo Town"),
    ("Olímpico Taldo", "Racing Taldo"),
    ("Taldo County", "Taldo Central"),
    ("Taldo Unidos", "Taldo Atlântico"),
    ("Taldo Phoenix", "Taldo Comets"),
]

# La Liga 2023/24, na ordem da tabela:
# nome -> (sigla, cor primária, secundária, camisa, escudo, caixa mi,
#          torcida mi, força). A força é do clube, não da ordem: o Girona
# foi 3º, mas o elenco não é o do Atlético. Com o XI ~2 acima da força e
# a variação maior (sigma/teto da liga), o topo tem craques de ~90
LALIGA = {
    "Real Madrid": ("RMA", "#FFFFFF", "#FEBE10", "lisa", "classico", 35, 12, 83),
    "Barcelona": ("BAR", "#A50044", "#004D98", "listras", "classico", 30, 12, 82),
    "Girona": ("GIR", "#E30613", "#FFFFFF", "listras", "moderno", 6, 0.3, 78),
    "Atlético Madrid": ("ATM", "#CB3524", "#FFFFFF", "listras", "classico", 22, 4, 80),
    "Athletic Club": ("ATH", "#EE2523", "#FFFFFF", "listras", "classico", 10, 2, 78),
    "Real Sociedad": ("RSO", "#0067B1", "#FFFFFF", "listras", "classico", 10, 1, 77),
    "Real Betis": ("BET", "#00954C", "#FFFFFF", "listras", "classico", 8, 1.5, 77),
    "Villarreal": ("VIL", "#FFE667", "#005187", "lisa", "redondo", 10, 0.5, 77),
    "Valencia": ("VAL", "#FFFFFF", "#000000", "lisa", "classico", 7, 2, 75),
    "Alavés": ("ALA", "#0061A8", "#FFFFFF", "listras", "moderno", 4, 0.3, 73),
    "Osasuna": ("OSA", "#D91A21", "#0A346F", "lisa", "classico", 4, 0.4, 74),
    "Getafe": ("GET", "#005999", "#FFFFFF", "lisa", "moderno", 4, 0.25, 74),
    "Celta de Vigo": ("CEL", "#8AC3EE", "#FFFFFF", "lisa", "redondo", 5, 0.6, 74),
    "Sevilla": ("SEV", "#FFFFFF", "#D71A28", "lisa", "classico", 12, 2, 76),
    "Mallorca": ("MLL", "#E20613", "#000000", "lisa", "classico", 4, 0.4, 73),
    "Las Palmas": ("LPA", "#FFE400", "#0055A4", "lisa", "redondo", 3, 0.4, 72),
    "Rayo Vallecano": ("RAY", "#FFFFFF", "#E53027", "faixa", "moderno", 3, 0.3, 73),
    "Cádiz": ("CAD", "#FFE500", "#0045A7", "lisa", "redondo", 3, 0.4, 71),
    "Almería": ("ALM", "#EE1119", "#FFFFFF", "listras", "moderno", 4, 0.25, 71),
    "Granada": ("GRA", "#C8102E", "#FFFFFF", "aros", "classico", 3, 0.5, 71),
}
# Segunda División 2023/24, do 1º ao 18º e mais dois dos rebaixados
SEGUNDA = {
    "Leganés": ("LEG", "#FFFFFF", "#0050A0", "listras", "moderno", 2, 0.15),
    "Real Valladolid": ("VLL", "#5C2D91", "#FFFFFF", "listras", "classico", 3, 0.3),
    "Eibar": ("EIB", "#A50044", "#004D98", "listras", "classico", 2, 0.1),
    "Espanyol": ("ESP", "#007FC8", "#FFFFFF", "listras", "classico", 4, 0.6),
    "Sporting Gijón": ("SPO", "#E2001A", "#FFFFFF", "listras", "classico", 2, 0.4),
    "Real Oviedo": ("OVI", "#0053A0", "#FFFFFF", "lisa", "classico", 2, 0.3),
    "Racing Santander": ("RAC", "#FFFFFF", "#00A650", "lisa", "classico", 2, 0.3),
    "Levante": ("LEV", "#004F9F", "#A50044", "listras", "classico", 3, 0.3),
    "Burgos": ("BUR", "#FFFFFF", "#000000", "lisa", "redondo", 1, 0.1),
    "Racing Ferrol": ("FER", "#00843D", "#FFFFFF", "lisa", "redondo", 1, 0.05),
    "Elche": ("ELC", "#FFFFFF", "#00A650", "faixa", "classico", 2, 0.2),
    "Tenerife": ("TEN", "#FFFFFF", "#0047AB", "lisa", "redondo", 2, 0.2),
    "Albacete": ("ALB", "#FFFFFF", "#C8102E", "lisa", "classico", 1, 0.1),
    "Cartagena": ("CTG", "#000000", "#FFFFFF", "listras", "moderno", 1, 0.1),
    "Real Zaragoza": ("ZAR", "#FFFFFF", "#0047AB", "lisa", "classico", 2, 0.5),
    "Eldense": ("ELD", "#00843D", "#C8102E", "listras", "redondo", 1, 0.05),
    "Huesca": ("HUE", "#0047AB", "#A50044", "listras", "classico", 1, 0.1),
    "Mirandés": ("MIR", "#C8102E", "#000000", "lisa", "redondo", 1, 0.05),
    "Alcorcón": ("ALC", "#FFE500", "#0047AB", "lisa", "moderno", 1, 0.05),
    "Amorebieta": ("AMO", "#000000", "#FFFFFF", "listras", "moderno", 1, 0.03),
}
# os clássicos da Espanha, das duas divisões (cada seed fica com os seus)
CLASSICOS_ESPANHA = [
    ("Real Madrid", "Barcelona"),
    ("Real Madrid", "Atlético Madrid"),
    ("Athletic Club", "Real Sociedad"),
    ("Sevilla", "Real Betis"),
    ("Valencia", "Villarreal"),
    ("Getafe", "Rayo Vallecano"),
    ("Almería", "Granada"),
    ("Cádiz", "Real Betis"),
    ("Barcelona", "Espanyol"),
    ("Valencia", "Levante"),
    ("Las Palmas", "Tenerife"),
    ("Alavés", "Eibar"),
    ("Osasuna", "Real Zaragoza"),
    ("Celta de Vigo", "Racing Ferrol"),
    ("Sporting Gijón", "Real Oviedo"),
    ("Real Zaragoza", "Huesca"),
    ("Leganés", "Alcorcón"),
    ("Real Valladolid", "Burgos"),
    ("Racing Santander", "Sporting Gijón"),
    ("Elche", "Cartagena"),
    ("Eldense", "Elche"),
    ("Mirandés", "Burgos"),
    ("Albacete", "Cartagena"),
    ("Amorebieta", "Eibar"),
]

# Série B de 2017, na ordem da tabela; o Internacional (2º, subiu) tem a
# força de clube grande
BRASILEIRAO_B = {
    "América Mineiro": ("AME", "#006F3C", "#000000", "lisa", "classico", 2, 0.5),
    "Internacional": ("INT", "#E30613", "#FFFFFF", "lisa", "classico", 8, 4, 75),
    "Ceará": ("CEA", "#000000", "#FFFFFF", "listras", "classico", 2, 0.8),
    "Paraná": ("PAR", "#0033A0", "#C8102E", "lisa", "redondo", 1.5, 0.3),
    "Londrina": ("LON", "#87CEEB", "#FFFFFF", "lisa", "moderno", 1, 0.15),
    "Oeste": ("OES", "#C8102E", "#FFFFFF", "lisa", "redondo", 1, 0.05),
    "Vila Nova": ("VNO", "#C8102E", "#FFFFFF", "lisa", "classico", 1, 0.2),
    "Brasil de Pelotas": ("BRP", "#C8102E", "#000000", "listras", "classico", 1, 0.15),
    "Juventude": ("JUV", "#00843D", "#FFFFFF", "listras", "classico", 1, 0.2),
    "Boa Esporte": ("BOA", "#000000", "#FFFFFF", "lisa", "moderno", 1, 0.05),
    "Paysandu": ("PAY", "#87CEEB", "#FFFFFF", "listras", "classico", 1.5, 0.7),
    "Figueirense": ("FIG", "#000000", "#FFFFFF", "listras", "classico", 1.5, 0.3),
    "Criciúma": ("CRI", "#FFD100", "#000000", "listras", "classico", 1, 0.2),
    "Goiás": ("GOI", "#00843D", "#FFFFFF", "lisa", "classico", 2, 0.5),
    "CRB": ("CRB", "#C8102E", "#FFFFFF", "listras", "classico", 1, 0.2),
    "Guarani": ("GUA", "#00843D", "#FFFFFF", "lisa", "classico", 1, 0.3),
    "Luverdense": ("LUV", "#00843D", "#FFD100", "lisa", "moderno", 0.5, 0.05),
    "Santa Cruz": ("STA", "#C8102E", "#000000", "aros", "classico", 1, 0.8),
    "ABC": ("ABC", "#000000", "#FFFFFF", "lisa", "classico", 0.5, 0.2),
    "Náutico": ("NAU", "#C8102E", "#FFFFFF", "listras", "classico", 1, 0.4),
}
CLASSICOS_BRASILEIRAO_B = [
    ("Náutico", "Santa Cruz"),
    ("Goiás", "Vila Nova"),
    ("Figueirense", "Criciúma"),
    ("Juventude", "Brasil de Pelotas"),
    ("Londrina", "Paraná"),
    ("Paysandu", "CRB"),
    ("ABC", "Náutico"),
    ("Oeste", "Guarani"),
    ("Boa Esporte", "América Mineiro"),
    ("Luverdense", "Goiás"),
    ("Ceará", "ABC"),
]

# id do primeiro jogador de cada seed (Taldo ~1–500, Premier 10 001+).
# Sem força no clube, a da ordem (FORCA_TOPO a FORCA_FUNDO); sem
# sigma/teto, os das Séries B. Liga nova vai no FIM (ver o topo do arquivo)
LIGAS = {
    "taldo_b": dict(pasta="taldo_b", clubes=TALDO_B, classicos=CLASSICOS_TALDO_B,
                    pais="Taldo", primeiro_id=20_001, nomes=(NOMES_BR, SOBRENOMES_BR),
                    multa=True, nacionalidades=None),
    "championship": dict(pasta="championship", clubes=CHAMPIONSHIP,
                         classicos=CLASSICOS_CHAMPIONSHIP + RIVAIS_NA_PREMIER,
                         pais="Inglaterra", primeiro_id=30_001,
                         nomes=(NOMES_EN, SOBRENOMES_EN), multa=False,
                         nacionalidades=NACIONALIDADES_EN),
    "laliga": dict(pasta="laliga", clubes=LALIGA, classicos=CLASSICOS_ESPANHA,
                   pais="Espanha", primeiro_id=40_001, nomes=(NOMES_ES, SOBRENOMES_ES),
                   multa=True, nacionalidades=NACIONALIDADES_ES, sigma=3.0, teto=7),
    "segunda": dict(pasta="segunda", clubes=SEGUNDA, classicos=CLASSICOS_ESPANHA,
                    pais="Espanha", primeiro_id=50_001, nomes=(NOMES_ES, SOBRENOMES_ES),
                    multa=True, nacionalidades=NACIONALIDADES_ES),
    # (o Brasileirão A usa os ids 60 001+)
    "brasileirao_b": dict(pasta="brasileirao_b", clubes=BRASILEIRAO_B,
                          classicos=CLASSICOS_BRASILEIRAO_B + RIVAIS_NA_SERIE_B,
                          pais="Brasil", primeiro_id=70_001,
                          nomes=(NOMES_BR, SOBRENOMES_BR), multa=True,
                          nacionalidades=None),
}


def _rng(chave):
    return random.Random(zlib.crc32(chave.encode("utf-8")))


def nomes_ocupados():
    """Os nomes das seeds de jogadores reais (e da Taldo): as geradas aqui
    não os repetem."""
    nomes = set()
    for pasta in (SEEDS, SEEDS / "premier", SEEDS / "brasileirao"):
        for arquivo in ("jogadores.json", "livres.json"):
            caminho = pasta / arquivo
            if caminho.exists():
                nomes |= {j["nome"] for j in json.loads(caminho.read_text(encoding="utf-8"))}
    return nomes


def _idade(rng):
    faixa = rng.random()
    if faixa < 0.20:
        return rng.randint(17, 20)
    if faixa < 0.80:
        return rng.randint(21, 29)
    return rng.randint(30, 35)


def _ajuste_idade(idade):
    if idade <= 19:
        return -5
    if idade <= 21:
        return -2
    if idade <= 30:
        return 0
    return -1 if idade <= 32 else -3


def _elenco(clube, forca, ocupados, nomes, rng, sigma=2.5, teto=TETO):
    elenco = []
    for setor, quantos in CORTE.items():
        for i in range(quantos):
            idade = _idade(rng)
            titular = i < TITULARES_DO_SETOR[setor]
            valor = forca + (2 if titular else -2) + _ajuste_idade(idade) + rng.gauss(0, sigma)
            nome = None
            while nome is None or nome in ocupados:
                nome = f"{rng.choice(nomes[0])} {rng.choice(nomes[1])}"
            ocupados.add(nome)
            elenco.append({
                "nome": nome, "idade": idade, "setor": setor,
                "overall": max(OVERALL_MIN, min(forca + teto, round(valor))),
            })
    for j in elenco:
        j["potencial"] = potencial(j)
    dar_funcoes(elenco)
    return elenco


def _ficha(j, liga, rng):
    funcao = j["funcao"]
    ficha = {
        "nome": j["nome"],
        "idade": j["idade"],
        "posicao": posicoes.SETOR[funcao],
        "overall": j["overall"],
        "potencial": j["potencial"],
        "funcao": funcao,
        "secundarias": livres.secundarias(funcao, _rng(j["nome"] + "/sec")),
        "contrato_anos": rng.randint(1, 2) if j["idade"] >= 32 else rng.randint(1, 5),
        "multa_rescisoria": None,
    }
    if liga["multa"] and rng.random() < CHANCE_MULTA:
        valor = Jogador(ficha["nome"], ficha["idade"], ficha["posicao"], ficha["overall"],
                        potencial=ficha["potencial"]).valor_mercado()
        ficha["multa_rescisoria"] = max(500_000, round(valor * rng.uniform(1.8, 4.0) / 100_000) * 100_000)
    if liga["nacionalidades"]:
        ficha["nacionalidade"] = rng.choice(liga["nacionalidades"])
    return ficha


def gerar(id_liga, ocupados):
    liga = LIGAS[id_liga]
    rng = random.Random(f"serie-b:{id_liga}")
    nomes_clubes = list(liga["clubes"])
    passo = (FORCA_TOPO - FORCA_FUNDO) / (len(nomes_clubes) - 1)
    clubes, jogadores = [], []
    proximo = liga["primeiro_id"]
    for i, nome in enumerate(nomes_clubes):
        dados = liga["clubes"][nome]
        forca = dados[7] if len(dados) > 7 else round(FORCA_TOPO - i * passo)
        elenco = _elenco(nome, forca, ocupados, liga["nomes"], rng,
                         liga.get("sigma", 2.5), liga.get("teto", TETO))
        titulares = xi(elenco)
        numero = iter(range(1, 99))
        for j in titulares + [j for j in elenco if j not in titulares]:
            j["id"] = proximo
            proximo += 1
            jogadores.append({"id": j["id"], **_ficha(j, liga, rng), "numero": next(numero)})
        sigla, cor1, cor2, camisa, escudo, caixa, torcida = dados[:7]
        clubes.append({
            "id": i + 1,
            "nome": nome,
            "pais": liga["pais"],
            "dinheiro": round(caixa * 1_000_000),
            "torcedores": round(torcida * 1_000_000),
            "titulares": [j["id"] for j in titulares],
            "reservas": [j["id"] for j in elenco if j not in titulares],
            "rivais": sorted(b if a == nome else a for a, b in liga["classicos"] if nome in (a, b)),
            "identidade": {"cor_primaria": cor1, "cor_secundaria": cor2,
                           "camisa": camisa, "escudo": escudo, "sigla": sigla},
        })
    return clubes, jogadores


def main():
    ocupados = nomes_ocupados()
    for id_liga, liga in LIGAS.items():
        clubes, jogadores = gerar(id_liga, ocupados)
        destino = SEEDS / liga["pasta"]
        destino.mkdir(parents=True, exist_ok=True)
        for arquivo, dados in (("clubes.json", clubes), ("jogadores.json", jogadores)):
            (destino / arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=4),
                                           encoding="utf-8")
        por_id = {j["id"]: j for j in jogadores}
        print(f"\n{id_liga}: {len(clubes)} clubes, {len(jogadores)} jogadores")
        for c in clubes:
            xi_ = [por_id[i]["overall"] for i in c["titulares"]]
            print(f"  {c['nome']:22} XI {sum(xi_) / 11:5.1f}  rivais {c['rivais']}")


if __name__ == "__main__":
    main()
