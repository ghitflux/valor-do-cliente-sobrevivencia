"""Gamma-Gamma (Fader e Hardie, 2013): quanto um cliente gasta por compra, em média.

A história do modelo:
- o valor de cada compra de um cliente varia ao acaso em torno de uma média própria dele
  (cada compra é uma gama(p, nu), de média p / nu);
- essa média varia entre clientes (nu é uma gama(q, gama_), e p é igual para todos);
- o valor por compra não depende de quantas compras o cliente faz (hipótese a conferir nos dados).

Com poucas compras, a média observada de um cliente é ruidosa. O modelo a puxa para a média da
base, e puxa menos quanto mais compras o cliente tiver: é uma média ponderada entre os dois.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import optimize, special


@dataclass(frozen=True)
class ParametrosGammaGamma:
    p: float
    q: float
    gama: float
    log_verossimilhanca: float = float("nan")
    convergiu: bool = True

    def como_dicionario(self) -> dict:
        return asdict(self)


def log_verossimilhanca_por_cliente(p: float, q: float, gama: float, compras, valor_medio) -> np.ndarray:
    """Log da densidade da média observada de cada cliente, dadas as suas `compras` (n >= 1).

    f(m | n) = gama_fn(p n + q) / (gama_fn(p n) gama_fn(q)) * gama^q * m^(p n - 1) * n^(p n) / (gama + m n)^(p n + q)
    """
    n = np.asarray(compras, dtype=float)
    m = np.asarray(valor_medio, dtype=float)
    return (
        special.gammaln(p * n + q) - special.gammaln(p * n) - special.gammaln(q)
        + q * np.log(gama) + (p * n - 1.0) * np.log(m) + p * n * np.log(n)
        - (p * n + q) * np.log(gama + m * n)
    )


def log_verossimilhanca(parametros, compras, valor_medio, pesos=None) -> float:
    p, q, gama = parametros
    por_cliente = log_verossimilhanca_por_cliente(p, q, gama, compras, valor_medio)
    return float(np.sum(por_cliente if pesos is None else por_cliente * np.asarray(pesos, dtype=float)))


def ajustar(compras, valor_medio, pesos=None, inicio: ParametrosGammaGamma | None = None) -> ParametrosGammaGamma:
    """Máxima verossimilhança, com a busca no logaritmo dos três parâmetros."""
    n = np.asarray(compras, dtype=float)
    m = np.asarray(valor_medio, dtype=float)
    pesos = None if pesos is None else np.asarray(pesos, dtype=float)
    total = float(len(n) if pesos is None else pesos.sum())
    escala = float(np.average(m, weights=pesos))

    def perda(log_parametros: np.ndarray) -> float:
        valor = -log_verossimilhanca(np.exp(log_parametros), n, m, pesos) / total
        return valor if np.isfinite(valor) else 1e10

    if inicio is not None:
        partidas = [np.log([inicio.p, inicio.q, inicio.gama])]
    else:
        partidas = [np.log(v) for v in ([1.0, 3.0, 2.0 * escala], [5.0, 3.0, 0.4 * escala], [2.0, 5.0, 2.0 * escala])]
    limites = [(-9.0, 9.0), (-9.0, 9.0), (-9.0, 25.0)]
    melhor = None
    for partida in partidas:
        resultado = optimize.minimize(perda, partida, method="L-BFGS-B", bounds=limites)
        if melhor is None or resultado.fun < melhor.fun:
            melhor = resultado
    p, q, gama = np.exp(melhor.x)
    return ParametrosGammaGamma(float(p), float(q), float(gama), float(-melhor.fun * total), bool(melhor.success))


def valor_medio_da_base(par: ParametrosGammaGamma) -> float:
    """Valor médio por compra de um cliente sobre o qual não se sabe nada: p * gama / (q - 1)."""
    if par.q <= 1.0:
        return float("inf")
    return par.p * par.gama / (par.q - 1.0)


def valor_esperado_condicional(par: ParametrosGammaGamma, compras, valor_medio) -> np.ndarray:
    """E[valor médio por compra do cliente | n compras observadas com média m].

    = p (gama + m n) / (p n + q - 1), que é o mesmo que
      peso * (média da base) + (1 - peso) * m,  com peso = (q - 1) / (p n + q - 1).
    """
    n = np.asarray(compras, dtype=float)
    m = np.asarray(valor_medio, dtype=float)
    return par.p * (par.gama + m * n) / (par.p * n + par.q - 1.0)


def peso_da_media_da_base(par: ParametrosGammaGamma, compras) -> np.ndarray:
    """Quanto da estimativa de um cliente vem da média da base (o resto vem da média dele)."""
    n = np.asarray(compras, dtype=float)
    return (par.q - 1.0) / (par.p * n + par.q - 1.0)


def simular(par: ParametrosGammaGamma, compras, gerador: np.random.Generator) -> dict[str, np.ndarray]:
    """Gera a média observada de cada cliente pelo processo do modelo, e a média verdadeira dele."""
    n = np.asarray(compras, dtype=float)
    nu = gerador.gamma(par.q, 1.0 / par.gama, len(n))
    # a soma de n compras gama(p, nu) é gama(p n, nu); a média observada é a soma dividida por n
    media_observada = gerador.gamma(par.p * n, 1.0 / nu) / n
    return {"compras": n, "valor_medio": media_observada, "media_verdadeira": par.p / nu}
