"""Métricas de validação e bootstrap. Tudo é medido no período que o modelo não viu."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy import stats


def receita_capturada(pontuacao, receita, fracao: float) -> float:
    """Parte da receita total que está nos `fracao` clientes de maior pontuação.

    Empate na fronteira (comum na regra de RFM, que só tem 13 notas possíveis): as vagas que
    sobram são preenchidas pela receita média do grupo empatado, que é o valor esperado de
    desempatar por sorteio. Pontuação constante devolve exatamente `fracao`.
    """
    pontuacao = np.asarray(pontuacao, dtype=float)
    receita = np.asarray(receita, dtype=float)
    total = receita.sum()
    vagas = int(round(fracao * len(pontuacao)))
    if vagas <= 0 or total <= 0:
        return 0.0
    limiar = np.partition(pontuacao, len(pontuacao) - vagas)[len(pontuacao) - vagas]
    acima = pontuacao > limiar
    empatados = pontuacao == limiar
    restantes = vagas - int(acima.sum())
    return float((receita[acima].sum() + restantes * receita[empatados].mean()) / total)


def curva_de_captura(pontuacao, receita, fracoes) -> np.ndarray:
    """Receita capturada para várias frações da base (a curva de ganho acumulado)."""
    return np.array([receita_capturada(pontuacao, receita, f) for f in fracoes])


def erros_de_previsao(previsto, real) -> dict[str, float]:
    """Erro por cliente (absoluto médio e quadrático) e viés do total (previsto / real - 1)."""
    previsto, real = np.asarray(previsto, dtype=float), np.asarray(real, dtype=float)
    erro = previsto - real
    return {
        "erro_absoluto_medio": float(np.mean(np.abs(erro))),
        "raiz_do_erro_quadratico": float(np.sqrt(np.mean(erro**2))),
        "vies_do_total": float(previsto.sum() / real.sum() - 1.0),
    }


def indices_de_bootstrap(n: int, repeticoes: int, semente: int) -> np.ndarray:
    """Matriz (repeticoes x n) de índices sorteados com reposição: a unidade sorteada é o cliente."""
    return np.random.default_rng(semente).integers(0, n, size=(repeticoes, n))


def intervalo(valores, confianca: float = 0.95) -> tuple[float, float]:
    """Intervalo percentil de uma lista de estimativas de bootstrap."""
    valores = np.asarray(valores, dtype=float)
    valores = valores[np.isfinite(valores)]
    cauda = (1.0 - confianca) / 2.0
    return float(np.quantile(valores, cauda)), float(np.quantile(valores, 1.0 - cauda))


def intervalo_de_wilson(sucessos: int, total: int, confianca: float = 0.95) -> tuple[float, float]:
    """Intervalo de Wilson para uma proporção (funciona bem com amostra pequena e proporção perto de 0 ou 1)."""
    if total == 0:
        return float("nan"), float("nan")
    z = stats.norm.ppf(0.5 + confianca / 2.0)
    p = sucessos / total
    centro = (p + z**2 / (2 * total)) / (1 + z**2 / total)
    margem = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / (1 + z**2 / total)
    return float(centro - margem), float(centro + margem)


def bootstrap(estatistica: Callable[[np.ndarray], float], indices: np.ndarray) -> np.ndarray:
    """Aplica a estatística (função dos índices sorteados) a cada reamostra."""
    return np.array([estatistica(linha) for linha in indices])


def calibracao_por_faixa(faixa: pd.Series, real, previsoes: dict[str, np.ndarray]) -> pd.DataFrame:
    """Média real e média prevista por cada método, dentro de cada faixa de clientes."""
    tabela = pd.DataFrame({"faixa": pd.Series(faixa).reset_index(drop=True), "real": np.asarray(real, dtype=float)})
    for nome, previsto in previsoes.items():
        tabela[nome] = np.asarray(previsto, dtype=float)
    agrupado = tabela.groupby("faixa", observed=True)
    saida = agrupado.mean()
    saida.insert(0, "clientes", agrupado.size())
    return saida
