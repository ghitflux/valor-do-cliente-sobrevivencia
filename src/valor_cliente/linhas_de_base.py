"""As alternativas simples: o que se faria sem modelo nenhum.

(a) taxa histórica: cada cliente repete, no período seguinte, o ritmo de compra que teve até aqui;
(b) regra de bolso de RFM: nota de 1 a 5 em recência, frequência e valor, somadas (só ordena);
(c) média da base: todo cliente recebe o ritmo médio da base (não distingue ninguém).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compras_pela_taxa_historica(x, T, horizonte: float) -> np.ndarray:
    """Recompras por unidade de tempo até aqui, vezes o tamanho do período seguinte."""
    x, T = np.asarray(x, dtype=float), np.asarray(T, dtype=float)
    return np.where(T > 0, x / np.where(T > 0, T, 1.0), 0.0) * horizonte


def compras_pela_media_da_base(x, T, horizonte: float) -> np.ndarray:
    """O mesmo número para todos: recompras da base inteira por cliente-semana, vezes o horizonte."""
    x, T = np.asarray(x, dtype=float), np.asarray(T, dtype=float)
    return np.full(len(x), x.sum() / T.sum() * horizonte)


def faixas(valores, quantas: int = 5, maior_e_melhor: bool = True) -> np.ndarray:
    """Nota de 1 a `quantas` pelo posto do valor na base (5 = melhor quinto).

    Empates recebem o posto médio, então clientes com o mesmo valor ficam sempre na mesma faixa
    (na frequência, muita gente empata em zero recompras).
    """
    serie = pd.Series(np.asarray(valores, dtype=float))
    posto = serie.rank(method="average", pct=True, ascending=maior_e_melhor).to_numpy()
    return np.clip(np.ceil(posto * quantas), 1, quantas).astype(int)


def pontuacao_rfm(recencia, frequencia, valor) -> pd.DataFrame:
    """Regra de bolso de RFM: quintos de recência (menos tempo calado é melhor), frequência e valor.

    A pontuação é a soma das três notas (3 a 15). Não prevê quantidade nenhuma: só ordena clientes.
    """
    notas = pd.DataFrame({
        "R": faixas(recencia, maior_e_melhor=False),
        "F": faixas(frequencia),
        "M": faixas(valor),
    })
    notas["RFM"] = notas[["R", "F", "M"]].sum(axis=1)
    return notas
