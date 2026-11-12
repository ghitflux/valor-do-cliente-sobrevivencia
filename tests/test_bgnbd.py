import numpy as np
import pytest
from scipy import stats

from valor_cliente import bgnbd
from valor_cliente.bgnbd import ParametrosBGNBD

# Parâmetros com densidades suaves (r, a, b > 1): a integral numérica converge sem truques.
SUAVE = ParametrosBGNBD(r=1.6, alfa=9.0, a=1.8, b=3.5)
# Parâmetros publicados por Fader, Hardie e Lee (2005) para a base CDNOW.
CDNOW = ParametrosBGNBD(r=0.243, alfa=4.414, a=0.793, b=2.426)
CASOS = [(0, 0.0, 30.0), (1, 5.0, 30.0), (3, 12.0, 26.0), (6, 25.0, 26.0)]


def _integrar(p: ParametrosBGNBD, funcao) -> float:
    """Integral dupla de funcao(taxa, abandono) ponderada pelas duas distribuições da base.

    Quadratura de Gauss-Legendre numa grade de 500 x 300 pontos: conferência numérica independente
    das fórmulas fechadas (não usa nenhuma função gama além das próprias densidades).
    """
    nos_taxa, pesos_taxa = np.polynomial.legendre.leggauss(500)
    nos_abandono, pesos_abandono = np.polynomial.legendre.leggauss(300)
    limite = stats.gamma.ppf(1 - 1e-13, p.r, scale=1.0 / p.alfa)  # acima disso a gama não tem massa
    taxa = (nos_taxa + 1) / 2 * limite
    abandono = (nos_abandono + 1) / 2
    densidade = np.outer(
        stats.gamma.pdf(taxa, p.r, scale=1.0 / p.alfa) * pesos_taxa * limite / 2,
        stats.beta.pdf(abandono, p.a, p.b) * pesos_abandono / 2,
    )
    return float(np.sum(funcao(taxa[:, None], abandono[None, :]) * densidade))


def _verossimilhanca_individual(taxa, abandono, x: int, t_x: float, T: float) -> tuple[np.ndarray, np.ndarray]:
    """(parcela "vivo em T", parcela "abandonou depois da última compra") para um cliente de taxa e abandono dados."""
    vivo = (1 - abandono) ** x * taxa**x * np.exp(-taxa * T)
    morto = abandono * (1 - abandono) ** (x - 1) * taxa**x * np.exp(-taxa * t_x) if x > 0 else 0.0 * vivo
    return vivo, morto


@pytest.mark.parametrize("x,t_x,T", CASOS)
def test_verossimilhanca_fechada_bate_com_a_integral_numerica(x, t_x, T):
    numerica = _integrar(SUAVE, lambda taxa, ab: sum(_verossimilhanca_individual(taxa, ab, x, t_x, T)))
    fechada = np.exp(bgnbd.log_verossimilhanca_por_cliente(SUAVE.r, SUAVE.alfa, SUAVE.a, SUAVE.b, x, t_x, T))
    assert float(fechada) == pytest.approx(numerica, rel=1e-6)


@pytest.mark.parametrize("x,t_x,T", CASOS)
def test_probabilidade_vivo_bate_com_a_integral_numerica(x, t_x, T):
    vivo = _integrar(SUAVE, lambda taxa, ab: _verossimilhanca_individual(taxa, ab, x, t_x, T)[0])
    total = _integrar(SUAVE, lambda taxa, ab: sum(_verossimilhanca_individual(taxa, ab, x, t_x, T)))
    assert float(bgnbd.probabilidade_vivo(SUAVE, x, t_x, T)) == pytest.approx(vivo / total, rel=1e-6)


@pytest.mark.parametrize("x,t_x,T", CASOS)
def test_esperanca_condicional_bate_com_a_integral_numerica(x, t_x, T):
    horizonte = 39.0

    def compras_futuras_se_vivo(taxa: float, ab: float) -> float:
        # vivo em T, o cliente faz em média (1 - exp(-taxa * ab * t)) / ab compras antes de abandonar
        return (1 - np.exp(-taxa * ab * horizonte)) / ab * _verossimilhanca_individual(taxa, ab, x, t_x, T)[0]

    numerador = _integrar(SUAVE, compras_futuras_se_vivo)
    total = _integrar(SUAVE, lambda taxa, ab: sum(_verossimilhanca_individual(taxa, ab, x, t_x, T)))
    assert float(bgnbd.compras_esperadas_condicional(SUAVE, horizonte, x, t_x, T)) == pytest.approx(numerador / total, rel=1e-6)


@pytest.mark.parametrize("x,t_x,T", CASOS)
def test_probabilidade_de_comprar_bate_com_a_integral_numerica(x, t_x, T):
    horizonte = 26.0
    numerador = _integrar(
        SUAVE, lambda taxa, ab: (1 - np.exp(-taxa * horizonte)) * _verossimilhanca_individual(taxa, ab, x, t_x, T)[0]
    )
    total = _integrar(SUAVE, lambda taxa, ab: sum(_verossimilhanca_individual(taxa, ab, x, t_x, T)))
    assert float(bgnbd.probabilidade_de_comprar(SUAVE, horizonte, x, t_x, T)) == pytest.approx(numerador / total, rel=1e-6)


def test_exemplo_publicado_da_base_cdnow():
    # Fader, Hardie e Lee, "Implementing the BG/NBD model in Excel": com os parâmetros da CDNOW, o cliente
    # com x = 2, t_x = 30,43 e T = 38,86 semanas tem 1,226 compra esperada nas 39 semanas seguintes.
    assert float(bgnbd.compras_esperadas_condicional(CDNOW, 39.0, 2, 30.43, 38.86)) == pytest.approx(1.226, abs=5e-4)


def test_forma_estavel_e_forma_do_artigo_dao_o_mesmo_numero():
    x = np.array([0, 1, 2, 5, 12, 30])
    t_x = np.array([0.0, 3.0, 20.0, 31.0, 38.0, 50.0])
    T = np.array([38.0, 38.0, 39.0, 40.0, 39.0, 52.0])
    for parametros in (SUAVE, CDNOW):
        estavel = bgnbd.compras_esperadas_condicional(parametros, 39.0, x, t_x, T)
        artigo = bgnbd.compras_esperadas_condicional_artigo(parametros, 39.0, x, t_x, T)
        np.testing.assert_allclose(estavel, artigo, rtol=1e-8)


def test_cliente_novo_e_o_caso_sem_historico_e_cresce_com_o_tempo():
    semanas = np.array([4.0, 13.0, 26.0, 52.0])
    esperado = bgnbd.compras_esperadas_cliente_novo(CDNOW, semanas)
    assert np.all(np.diff(esperado) > 0)
    assert float(esperado[-1]) == pytest.approx(float(bgnbd.compras_esperadas_condicional(CDNOW, 52.0, 0, 0.0, 0.0)))
    # conferência independente: média de (1 - exp(-taxa * ab * t)) / ab sobre a base, por integral numérica
    numerica = _integrar(SUAVE, lambda taxa, ab: (1 - np.exp(-taxa * ab * 26.0)) / ab)
    assert float(bgnbd.compras_esperadas_cliente_novo(SUAVE, 26.0)) == pytest.approx(numerica, rel=1e-6)


def test_quem_nunca_recomprou_tem_probabilidade_vivo_um_e_o_silencio_derruba_os_outros():
    assert float(bgnbd.probabilidade_vivo(CDNOW, 0, 0.0, 30.0)) == 1.0
    silencio_curto = float(bgnbd.probabilidade_vivo(CDNOW, 4, 20.0, 22.0))
    silencio_longo = float(bgnbd.probabilidade_vivo(CDNOW, 4, 20.0, 60.0))
    assert silencio_longo < silencio_curto < 1.0
    # a chance de comprar de novo cai com o silêncio também para quem nunca recomprou
    assert float(bgnbd.probabilidade_de_comprar(CDNOW, 26.0, 0, 0.0, 60.0)) < float(bgnbd.probabilidade_de_comprar(CDNOW, 26.0, 0, 0.0, 5.0))


def test_formulas_batem_com_o_processo_simulado():
    verdade = ParametrosBGNBD(r=0.6, alfa=8.0, a=1.2, b=3.0)
    gerador = np.random.default_rng(7)
    T = gerador.uniform(20.0, 52.0, 200_000)
    horizonte = 39.0
    s = bgnbd.simular(verdade, T, horizonte, gerador)
    vivo = bgnbd.probabilidade_vivo(verdade, s["x"], s["t_x"], s["T"])
    esperadas = bgnbd.compras_esperadas_condicional(verdade, horizonte, s["x"], s["t_x"], s["T"])
    comprar = bgnbd.probabilidade_de_comprar(verdade, horizonte, s["x"], s["t_x"], s["T"])
    for grupo in (s["x"] == 0, s["x"] == 1, (s["x"] >= 2) & (s["x"] <= 4), s["x"] >= 5):
        assert vivo[grupo].mean() == pytest.approx(s["vivo"][grupo].mean(), abs=0.01)
        assert esperadas[grupo].mean() == pytest.approx(s["compras_futuras"][grupo].mean(), rel=0.04)
        assert comprar[grupo].mean() == pytest.approx((s["compras_futuras"][grupo] > 0).mean(), abs=0.01)
    novo = bgnbd.compras_esperadas_cliente_novo(verdade, 30.0)
    recem_chegados = bgnbd.simular(verdade, np.zeros(200_000), 30.0, gerador)
    assert float(novo) == pytest.approx(recem_chegados["compras_futuras"].mean(), rel=0.03)


def test_ajuste_recupera_os_parametros_de_dados_simulados():
    verdade = ParametrosBGNBD(r=0.6, alfa=8.0, a=1.2, b=3.0)
    gerador = np.random.default_rng(11)
    s = bgnbd.simular(verdade, gerador.uniform(20.0, 52.0, 20_000), 0.0, gerador)
    ajustado = bgnbd.ajustar(s["x"], s["t_x"], s["T"])
    assert ajustado.convergiu
    assert ajustado.r == pytest.approx(verdade.r, rel=0.10)
    assert ajustado.alfa == pytest.approx(verdade.alfa, rel=0.12)
    # a e b, separados, são mal identificados; o que os dados fixam é o abandono médio a / (a + b)
    assert ajustado.a / (ajustado.a + ajustado.b) == pytest.approx(verdade.a / (verdade.a + verdade.b), abs=0.04)
    # e o que importa para o negócio: a previsão para um cliente novo
    assert float(bgnbd.compras_esperadas_cliente_novo(ajustado, 52.0)) == pytest.approx(
        float(bgnbd.compras_esperadas_cliente_novo(verdade, 52.0)), rel=0.05
    )
    # a verossimilhança no ponto ajustado não pode ser pior do que nos parâmetros verdadeiros
    assert ajustado.log_verossimilhanca >= bgnbd.log_verossimilhanca((verdade.r, verdade.alfa, verdade.a, verdade.b), s["x"], s["t_x"], s["T"]) - 1e-6


def test_pesos_equivalem_a_repetir_clientes():
    x, t_x, T = np.array([0, 2, 5]), np.array([0.0, 10.0, 30.0]), np.array([20.0, 25.0, 40.0])
    pesos = np.array([3, 1, 2])
    parametros = (0.5, 6.0, 0.9, 2.5)
    repetido = bgnbd.log_verossimilhanca(parametros, np.repeat(x, pesos), np.repeat(t_x, pesos), np.repeat(T, pesos))
    assert bgnbd.log_verossimilhanca(parametros, x, t_x, T, pesos) == pytest.approx(repetido)
