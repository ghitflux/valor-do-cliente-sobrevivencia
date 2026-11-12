"""Conferência opcional contra a biblioteca `lifetimes` (não é dependência do projeto).

Fica pulada no uso normal. Para rodar:
    uv run --with lifetimes pytest tests/test_conferencia_lifetimes.py
"""

import numpy as np
import pytest

from valor_cliente import bgnbd
from valor_cliente import gamma_gamma as gg
from valor_cliente.bgnbd import ParametrosBGNBD
from valor_cliente.gamma_gamma import ParametrosGammaGamma

lifetimes = pytest.importorskip("lifetimes")


def test_bgnbd_bate_com_a_biblioteca():
    verdade = ParametrosBGNBD(r=0.6, alfa=8.0, a=1.2, b=3.0)
    gerador = np.random.default_rng(31)
    s = bgnbd.simular(verdade, gerador.uniform(20.0, 52.0, 5000), 0.0, gerador)
    meu = bgnbd.ajustar(s["x"], s["t_x"], s["T"])
    deles = lifetimes.BetaGeoFitter(penalizer_coef=0.0).fit(s["x"], s["t_x"], s["T"])
    r, alfa, a, b = (deles.params_[k] for k in ("r", "alpha", "a", "b"))
    # a verossimilhança no ótimo é a mesma (a e b sozinhos são mal identificados, então comparo o ajuste)
    assert bgnbd.log_verossimilhanca((r, alfa, a, b), s["x"], s["t_x"], s["T"]) == pytest.approx(meu.log_verossimilhanca, abs=0.05)
    assert meu.r == pytest.approx(r, rel=0.02) and meu.alfa == pytest.approx(alfa, rel=0.02)
    # com os mesmos parâmetros, as fórmulas dão os mesmos números
    mesmos = ParametrosBGNBD(r, alfa, a, b)
    np.testing.assert_allclose(
        bgnbd.compras_esperadas_condicional(mesmos, 39.0, s["x"], s["t_x"], s["T"]),
        deles.conditional_expected_number_of_purchases_up_to_time(39.0, s["x"], s["t_x"], s["T"]),
        rtol=1e-6,
    )
    np.testing.assert_allclose(
        bgnbd.probabilidade_vivo(mesmos, s["x"], s["t_x"], s["T"]),
        deles.conditional_probability_alive(s["x"], s["t_x"], s["T"]),
        rtol=1e-6,
    )


def test_gamma_gamma_bate_com_a_biblioteca():
    verdade = ParametrosGammaGamma(p=6.0, q=4.0, gama=15.0)
    gerador = np.random.default_rng(32)
    s = gg.simular(verdade, gerador.integers(1, 9, 5000), gerador)
    meu = gg.ajustar(s["compras"], s["valor_medio"])
    deles = lifetimes.GammaGammaFitter(penalizer_coef=0.0).fit(s["compras"], s["valor_medio"])
    p, q, v = (deles.params_[k] for k in ("p", "q", "v"))
    assert gg.log_verossimilhanca((p, q, v), s["compras"], s["valor_medio"]) == pytest.approx(meu.log_verossimilhanca, abs=0.05)
    np.testing.assert_allclose(
        gg.valor_esperado_condicional(ParametrosGammaGamma(p, q, v), s["compras"], s["valor_medio"]),
        deles.conditional_expected_average_profit(s["compras"], s["valor_medio"]),
        rtol=1e-6,
    )
