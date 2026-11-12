import numpy as np
import pytest
from scipy import integrate, stats

from valor_cliente import gamma_gamma as gg
from valor_cliente.gamma_gamma import ParametrosGammaGamma

# Parâmetros na ordem de grandeza dos que Fader e Hardie relatam para a base CDNOW (valores em dólares).
CDNOW = ParametrosGammaGamma(p=6.25, q=3.74, gama=15.44)


def test_densidade_da_media_observada_integra_um():
    for compras in (1, 3, 10):
        area, _ = integrate.quad(lambda m: np.exp(gg.log_verossimilhanca_por_cliente(CDNOW.p, CDNOW.q, CDNOW.gama, compras, m)), 0, np.inf)
        assert area == pytest.approx(1.0, abs=1e-6)


def test_media_da_base_e_a_do_artigo():
    # p * gama / (q - 1) = 6,25 * 15,44 / 2,74 = 35,22
    assert gg.valor_medio_da_base(CDNOW) == pytest.approx(35.22, abs=0.01)
    assert gg.valor_medio_da_base(ParametrosGammaGamma(p=2.0, q=0.9, gama=10.0)) == float("inf")


def test_valor_esperado_condicional_bate_com_a_integral_numerica():
    compras, media = 4, 62.0
    total = compras * media

    def posteriori(nu: float) -> float:
        # a soma de n compras gama(p, nu) é gama(p n, nu); nu é gama(q, gama) na base
        return stats.gamma.pdf(total, CDNOW.p * compras, scale=1.0 / nu) * stats.gamma.pdf(nu, CDNOW.q, scale=1.0 / CDNOW.gama)

    numerador, _ = integrate.quad(lambda nu: CDNOW.p / nu * posteriori(nu), 0, np.inf)
    denominador, _ = integrate.quad(posteriori, 0, np.inf)
    assert float(gg.valor_esperado_condicional(CDNOW, compras, media)) == pytest.approx(numerador / denominador, rel=1e-6)


def test_valor_esperado_e_media_ponderada_entre_a_base_e_o_cliente():
    compras = np.array([1, 2, 5, 20, 200])
    media = np.full(5, 90.0)
    peso = gg.peso_da_media_da_base(CDNOW, compras)
    esperado = gg.valor_esperado_condicional(CDNOW, compras, media)
    np.testing.assert_allclose(esperado, peso * gg.valor_medio_da_base(CDNOW) + (1 - peso) * media)
    assert np.all(np.diff(peso) < 0)  # mais compras, menos peso para a base
    assert np.all(np.diff(esperado) > 0) and esperado[-1] == pytest.approx(90.0, abs=0.2)


def test_ajuste_recupera_os_parametros_de_dados_simulados():
    gerador = np.random.default_rng(5)
    compras = gerador.integers(1, 9, 20_000)
    s = gg.simular(CDNOW, compras, gerador)
    ajustado = gg.ajustar(s["compras"], s["valor_medio"])
    assert ajustado.convergiu
    assert ajustado.p == pytest.approx(CDNOW.p, rel=0.10)
    assert ajustado.q == pytest.approx(CDNOW.q, rel=0.10)
    assert gg.valor_medio_da_base(ajustado) == pytest.approx(gg.valor_medio_da_base(CDNOW), rel=0.03)
    assert ajustado.log_verossimilhanca >= gg.log_verossimilhanca((CDNOW.p, CDNOW.q, CDNOW.gama), s["compras"], s["valor_medio"]) - 1e-6


def test_estimativa_encolhida_erra_menos_que_a_media_crua_do_cliente():
    gerador = np.random.default_rng(6)
    s = gg.simular(CDNOW, np.full(50_000, 2), gerador)
    encolhida = gg.valor_esperado_condicional(CDNOW, s["compras"], s["valor_medio"])
    erro_encolhida = np.mean((encolhida - s["media_verdadeira"]) ** 2)
    erro_crua = np.mean((s["valor_medio"] - s["media_verdadeira"]) ** 2)
    assert erro_encolhida < erro_crua
    assert encolhida.mean() == pytest.approx(s["media_verdadeira"].mean(), rel=0.02)  # sem viés na média


def test_pesos_equivalem_a_repetir_clientes():
    compras, media, pesos = np.array([1, 3, 6]), np.array([20.0, 55.0, 31.0]), np.array([2, 1, 4])
    parametros = (4.0, 3.0, 20.0)
    repetido = gg.log_verossimilhanca(parametros, np.repeat(compras, pesos), np.repeat(media, pesos))
    assert gg.log_verossimilhanca(parametros, compras, media, pesos) == pytest.approx(repetido)
