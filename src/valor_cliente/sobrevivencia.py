"""Kaplan-Meier: a curva de "quem ainda não voltou", com dado censurado.

Para o tempo até a recompra, o cliente que ainda não voltou quando os dados acabam não é um
"nunca voltou": só se sabe que o tempo dele é maior do que o observado (censura à direita).
Jogar esses clientes fora, ou tratá-los como perdidos, distorce a curva. O estimador de
Kaplan-Meier usa cada um até onde foi observado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def kaplan_meier(duracao, evento, confianca: float = 0.95) -> pd.DataFrame:
    """Curva de sobrevivência S(t) nos tempos em que houve evento.

    `duracao`: tempo até o evento ou até a censura. `evento`: True se o evento foi observado.
    Em cada tempo t com d eventos e n clientes ainda em risco, S cai pelo fator (1 - d / n).
    Erro padrão pela fórmula de Greenwood; intervalo na escala log(-log S), que nunca sai de 0 a 1.
    """
    duracao = np.asarray(duracao, dtype=float)
    evento = np.asarray(evento, dtype=bool)
    tempos, inverso = np.unique(duracao, return_inverse=True)
    eventos = np.bincount(inverso, weights=evento, minlength=len(tempos))
    saidas = np.bincount(inverso, minlength=len(tempos))  # eventos e censuras em cada tempo
    em_risco = len(duracao) - np.concatenate([[0], np.cumsum(saidas)[:-1]])
    com_evento = eventos > 0
    tempos, eventos, em_risco = tempos[com_evento], eventos[com_evento], em_risco[com_evento]

    sobrevivencia = np.cumprod(1.0 - eventos / em_risco)
    with np.errstate(divide="ignore", invalid="ignore"):
        soma_greenwood = np.cumsum(eventos / (em_risco * (em_risco - eventos)))
        erro_padrao = sobrevivencia * np.sqrt(soma_greenwood)
        z = stats.norm.ppf(0.5 + confianca / 2.0)
        expoente = z * np.sqrt(soma_greenwood) / np.abs(np.log(sobrevivencia))
        inferior = sobrevivencia ** np.exp(expoente)
        superior = sobrevivencia ** np.exp(-expoente)
    return pd.DataFrame({
        "tempo": tempos, "em_risco": em_risco.astype(int), "eventos": eventos.astype(int),
        "sobrevivencia": sobrevivencia, "erro_padrao": erro_padrao, "inferior": inferior, "superior": superior,
    })


def sobrevivencia_em(curva: pd.DataFrame, tempos, coluna: str = "sobrevivencia") -> np.ndarray:
    """Valor da curva (função em degraus) nos tempos pedidos; antes do primeiro evento vale 1."""
    tempos = np.atleast_1d(np.asarray(tempos, dtype=float))
    posicao = np.searchsorted(curva["tempo"].to_numpy(), tempos, side="right") - 1
    valores = np.concatenate([[1.0], curva[coluna].to_numpy()])
    return valores[posicao + 1]


def tempo_mediano(curva: pd.DataFrame) -> float:
    """Primeiro tempo em que S(t) chega a 0,5 ou menos; NaN se a curva não chega lá."""
    abaixo = curva[curva["sobrevivencia"] <= 0.5]
    return float(abaixo["tempo"].iloc[0]) if len(abaixo) else float("nan")


def chance_de_voltar(curva: pd.DataFrame, silencio, horizonte: float) -> np.ndarray:
    """P(evento nas próximas `horizonte` unidades | ainda sem evento depois de `silencio`).

    = 1 - S(silencio + horizonte) / S(silencio). É a pergunta de quem decide a reativação:
    dado que o cliente já está calado há tanto tempo, qual a chance de ele ainda voltar sozinho?
    """
    silencio = np.atleast_1d(np.asarray(silencio, dtype=float))
    return 1.0 - sobrevivencia_em(curva, silencio + horizonte) / sobrevivencia_em(curva, silencio)
