"""BG/NBD (Fader, Hardie e Lee, 2005): quantas compras um cliente ainda vai fazer.

A história que o modelo conta, por cliente:
- enquanto está "vivo", compra ao acaso a uma taxa própria `lambda` (processo de Poisson);
- depois de cada recompra, abandona de vez com probabilidade própria `p` (moeda geométrica);
- `lambda` varia entre clientes como uma gama(r, alfa); `p`, como uma beta(a, b).

O abandono nunca é observado (ninguém cancela contrato): só se vê o silêncio. O modelo usa três
números por cliente, medidos no período de calibração:
- `x`: recompras (compras depois da primeira);
- `t_x`: quando foi a última recompra, contado a partir da primeira compra (0 se x = 0);
- `T`: há quanto tempo o cliente existe (da primeira compra até o fim da calibração).

Tudo aqui é NumPy/SciPy; nada de biblioteca pronta de CLV.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import optimize, special


@dataclass(frozen=True)
class ParametrosBGNBD:
    r: float
    alfa: float
    a: float
    b: float
    log_verossimilhanca: float = float("nan")
    convergiu: bool = True

    def como_dicionario(self) -> dict:
        return asdict(self)


def _vetores(x, t_x, T) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, t_x, T = (np.asarray(v, dtype=float) for v in (x, t_x, T))
    return x, t_x, T


def log_verossimilhanca_por_cliente(r: float, alfa: float, a: float, b: float, x, t_x, T) -> np.ndarray:
    """Logaritmo da verossimilhança de cada cliente (equação 6 do artigo).

    L = A1 * A2 * (A3 + [x > 0] * A4), com
      A1 = gama(r + x) * alfa^r / gama(r)
      A2 = gama(a + b) * gama(b + x) / (gama(b) * gama(a + b + x))
      A3 = (alfa + T)^-(r + x)                        -> o cliente ainda está vivo em T
      A4 = a / (b + x - 1) * (alfa + t_x)^-(r + x)    -> abandonou logo depois da última compra
    Tudo em logaritmo para não estourar com clientes de muitas compras.
    """
    x, t_x, T = _vetores(x, t_x, T)
    ln_a1 = special.gammaln(r + x) - special.gammaln(r) + r * np.log(alfa)
    ln_a2 = special.gammaln(a + b) + special.gammaln(b + x) - special.gammaln(b) - special.gammaln(a + b + x)
    ln_a3 = -(r + x) * np.log(alfa + T)
    recomprou = x > 0
    x_seguro = np.where(recomprou, x, 1.0)  # evita log de número negativo onde o termo nem entra
    ln_a4 = np.log(a) - np.log(b + x_seguro - 1.0) - (r + x) * np.log(alfa + t_x)
    return ln_a1 + ln_a2 + np.where(recomprou, np.logaddexp(ln_a3, ln_a4), ln_a3)


def log_verossimilhanca(parametros, x, t_x, T, pesos=None) -> float:
    """Soma (ponderada) da log-verossimilhança. `parametros` = (r, alfa, a, b)."""
    r, alfa, a, b = parametros
    por_cliente = log_verossimilhanca_por_cliente(r, alfa, a, b, x, t_x, T)
    return float(np.sum(por_cliente if pesos is None else por_cliente * np.asarray(pesos, dtype=float)))


def ajustar(x, t_x, T, pesos=None, inicio: ParametrosBGNBD | None = None) -> ParametrosBGNBD:
    """Máxima verossimilhança. Os quatro parâmetros são positivos, então a busca é no logaritmo deles.

    Sem `inicio`, parte de alguns pontos diferentes e fica com o melhor (a superfície tem regiões
    planas). Com `inicio` (usado no bootstrap), parte só dele.
    """
    x, t_x, T = _vetores(x, t_x, T)
    pesos = None if pesos is None else np.asarray(pesos, dtype=float)
    total = float(len(x) if pesos is None else pesos.sum())

    def perda(log_parametros: np.ndarray) -> float:
        valor = -log_verossimilhanca(np.exp(log_parametros), x, t_x, T, pesos) / total
        return valor if np.isfinite(valor) else 1e10

    if inicio is not None:
        partidas = [np.log([inicio.r, inicio.alfa, inicio.a, inicio.b])]
    else:
        partidas = [np.log(p) for p in ([1.0, 1.0, 1.0, 1.0], [0.5, 10.0, 0.5, 2.0], [0.2, 4.0, 1.0, 5.0], [2.0, 20.0, 2.0, 2.0])]
    limites = [(-9.0, 9.0)] * 4
    melhor = None
    for partida in partidas:
        resultado = optimize.minimize(perda, partida, method="L-BFGS-B", bounds=limites)
        if melhor is None or resultado.fun < melhor.fun:
            melhor = resultado
    r, alfa, a, b = np.exp(melhor.x)
    return ParametrosBGNBD(float(r), float(alfa), float(a), float(b), float(-melhor.fun * total), bool(melhor.success))


def probabilidade_vivo(p: ParametrosBGNBD, x, t_x, T) -> np.ndarray:
    """P(cliente ainda ativo em T | x, t_x, T).

    Quem nunca recomprou (x = 0) recebe 1 por construção: no BG/NBD o abandono só pode acontecer
    depois de uma recompra. É uma limitação conhecida do modelo, discutida no README.
    """
    x, t_x, T = _vetores(x, t_x, T)
    recomprou = x > 0
    x_seguro = np.where(recomprou, x, 1.0)
    ln_razao = np.log(p.a) - np.log(p.b + x_seguro - 1.0) + (p.r + x) * (np.log(p.alfa + T) - np.log(p.alfa + t_x))
    return np.where(recomprou, 1.0 / (1.0 + np.exp(ln_razao)), 1.0)


def _a_longe_de_um(a: float) -> float:
    """As fórmulas de esperança dividem por (a - 1); em a = 1 o limite existe, mas a conta não."""
    return a if abs(a - 1.0) > 1e-6 else 1.0 + 1e-6


def compras_esperadas_condicional(p: ParametrosBGNBD, t, x, t_x, T) -> np.ndarray:
    """E[compras nas próximas t unidades de tempo | x, t_x, T] (equação 10 do artigo).

    O artigo escreve
        (a+b+x-1)/(a-1) * [1 - ((alfa+T)/(alfa+T+t))^(r+x) * 2F1(r+x, b+x; a+b+x-1; z)] * P(vivo),
    com z = t / (alfa + T + t). Para clientes de muitas compras, essa 2F1 tem parâmetros grandes e
    perde precisão. A identidade de Euler, 2F1(A, B; C; z) = (1-z)^(C-A-B) * 2F1(C-A, C-B; C; z),
    leva à forma equivalente e estável usada aqui:
        (a+b+x-1)/(a-1) * [1 - (1-z)^(a-1) * 2F1(a+b-1-r, a-1; a+b+x-1; z)] * P(vivo).
    Os testes conferem que as duas formas dão o mesmo número e que ambas batem com a integral numérica.
    """
    x, t_x, T = _vetores(x, t_x, T)
    t = np.asarray(t, dtype=float)
    a = _a_longe_de_um(p.a)
    z = t / (p.alfa + T + t)
    c = a + p.b + x - 1.0
    hiper = special.hyp2f1(a + p.b - 1.0 - p.r, a - 1.0, c, z)
    se_vivo = c / (a - 1.0) * (1.0 - (1.0 - z) ** (a - 1.0) * hiper)
    return se_vivo * probabilidade_vivo(p, x, t_x, T)


def compras_esperadas_condicional_artigo(p: ParametrosBGNBD, t, x, t_x, T) -> np.ndarray:
    """A mesma esperança, escrita exatamente como no artigo. Fica para conferência nos testes."""
    x, t_x, T = _vetores(x, t_x, T)
    t = np.asarray(t, dtype=float)
    a = _a_longe_de_um(p.a)
    z = t / (p.alfa + T + t)
    c = a + p.b + x - 1.0
    hiper = special.hyp2f1(p.r + x, p.b + x, c, z)
    se_vivo = c / (a - 1.0) * (1.0 - ((p.alfa + T) / (p.alfa + T + t)) ** (p.r + x) * hiper)
    return se_vivo * probabilidade_vivo(p, x, t_x, T)


def compras_esperadas_cliente_novo(p: ParametrosBGNBD, t) -> np.ndarray:
    """E[recompras em t unidades de tempo] de um cliente que acabou de fazer a primeira compra.

    É o caso x = 0, t_x = 0, T = 0 da esperança condicional (equação 9 do artigo).
    """
    t = np.asarray(t, dtype=float)
    zeros = np.zeros_like(t)
    return compras_esperadas_condicional(p, t, zeros, zeros, zeros)


def probabilidade_de_comprar(p: ParametrosBGNBD, t, x, t_x, T) -> np.ndarray:
    """P(pelo menos uma compra nas próximas t unidades de tempo | x, t_x, T).

    Se o cliente está vivo em T, a taxa dele tem distribuição a posteriori gama(r + x, alfa + T), e a
    chance de passar t sem comprar é ((alfa+T)/(alfa+T+t))^(r+x). Logo
        P(comprar) = P(vivo) * (1 - ((alfa+T)/(alfa+T+t))^(r+x)).
    Diferente de P(vivo), cai com o silêncio também para quem nunca recomprou.
    """
    x, t_x, T = _vetores(x, t_x, T)
    t = np.asarray(t, dtype=float)
    sem_compra_se_vivo = np.exp((p.r + x) * (np.log(p.alfa + T) - np.log(p.alfa + T + t)))
    return probabilidade_vivo(p, x, t_x, T) * (1.0 - sem_compra_se_vivo)


def simular(p: ParametrosBGNBD, T, horizonte: float, gerador: np.random.Generator) -> dict[str, np.ndarray]:
    """Gera clientes pelo próprio processo do modelo. Serve para testar o ajuste e as fórmulas.

    `T` é o vetor com a idade de cada cliente no fim da calibração; `horizonte` é o tamanho do
    período seguinte. Devolve x, t_x, T, as compras no período seguinte e se o cliente estava vivo em T.
    """
    T = np.asarray(T, dtype=float)
    n = len(T)
    taxa = gerador.gamma(p.r, 1.0 / p.alfa, n)
    abandono = gerador.beta(p.a, p.b, n)
    relogio = np.zeros(n)
    x, t_x, futuras = np.zeros(n), np.zeros(n), np.zeros(n)
    ativo = np.ones(n, dtype=bool)  # ainda gerando compras dentro da janela
    vivo_em_T = np.ones(n, dtype=bool)
    fim = T + horizonte
    while ativo.any():
        indices = np.flatnonzero(ativo)
        relogio[indices] += gerador.exponential(1.0 / taxa[indices])
        dentro = relogio[indices] <= fim[indices]
        ativo[indices[~dentro]] = False
        indices = indices[dentro]
        na_calibracao = relogio[indices] <= T[indices]
        x[indices[na_calibracao]] += 1
        t_x[indices[na_calibracao]] = relogio[indices[na_calibracao]]
        futuras[indices[~na_calibracao]] += 1
        abandonou = gerador.random(len(indices)) < abandono[indices]
        ativo[indices[abandonou]] = False
        vivo_em_T[indices[abandonou & na_calibracao]] = False
    return {"x": x, "t_x": t_x, "T": T, "compras_futuras": futuras, "vivo": vivo_em_T, "taxa": taxa, "abandono": abandono}
