"""Formatos de texto para as mensagens do jogo (v1.8).

O dinheiro nas mensagens segue o da tela: "R$ 1,2 mi", "R$ 850 mil".
"""


def reais(valor):
    """1.234.567 → "R$ 1,2 mi"; abaixo de 1 milhão, "R$ 850 mil"."""
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:.1f} mi".replace(".", ",")
    return f"R$ {round(valor / 1_000)} mil"
