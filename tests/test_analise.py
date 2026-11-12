import numpy as np
import pandas as pd
import pytest

from valor_cliente import analise, bgnbd
from valor_cliente import avaliacao as av
from valor_cliente import gamma_gamma as gg
from valor_cliente.bgnbd import ParametrosBGNBD
from valor_cliente.gamma_gamma import ParametrosGammaGamma


def test_trajetoria_depois_da_primeira_compra_acumula_por_semana():
    compras = pd.DataFrame({
        "cliente": [1, 1, 1, 1, 2],
        "dia": pd.to_datetime(["2010-01-01", "2010-01-08", "2010-01-09", "2010-04-11", "2010-02-01"]),
        "receita": [10.0, 50.0, 30.0, 99.0, 70.0],
    })
    primeira = pd.Series(pd.to_datetime(["2010-01-01", "2010-02-01"]), index=pd.Index([1, 2], name="cliente"))
    quantas, receita = analise.trajetoria_depois_da_primeira_compra(compras, primeira, semanas=4)
    np.testing.assert_array_equal(quantas[0], [0, 1, 2, 2, 2])  # dia 7 cai na semana 1; dia 8, na semana 2
    np.testing.assert_array_equal(receita[0], [0, 50, 80, 80, 80])  # a compra do dia 100 fica fora das 4 semanas
    np.testing.assert_array_equal(quantas[1], [0, 0, 0, 0, 0])  # a primeira compra não conta como recompra


def test_tempo_ate_a_recompra_censura_quem_ainda_nao_voltou():
    compras = pd.DataFrame({
        "cliente": [1, 1, 1, 2],
        "dia": pd.to_datetime(["2010-01-01", "2010-01-15", "2010-03-01", "2010-02-01"]),
        "receita": 1.0,
    })
    tempos = analise.tempo_ate_a_recompra(compras, "2010-03-01")
    assert tempos.loc[1, "semanas"] == 2.0 and bool(tempos.loc[1, "voltou"])
    assert tempos.loc[2, "semanas"] == pytest.approx(28 / 7) and not bool(tempos.loc[2, "voltou"])


def _base_simulada(n: int = 1500) -> tuple[pd.DataFrame, ParametrosBGNBD, ParametrosGammaGamma]:
    """Clientes gerados pelos próprios modelos, no formato de `dados.montar_base`."""
    bg = ParametrosBGNBD(r=0.6, alfa=8.0, a=1.2, b=3.0)
    gama = ParametrosGammaGamma(p=6.0, q=4.0, gama=15.0)
    gerador = np.random.default_rng(21)
    s = bgnbd.simular(bg, gerador.uniform(5.0, 52.0, n), 52.0, gerador)
    passado = gg.simular(gama, s["x"] + 1, gerador)
    escala = passado["media_verdadeira"] / gama.p  # cada compra é gama(p, nu), de escala 1 / nu = média / p
    futuras = s["compras_futuras"]
    receita_futura = np.where(futuras > 0, gerador.gamma(gama.p * np.maximum(futuras, 1), escala), 0.0)
    base = pd.DataFrame({
        "cliente": np.arange(n), "x": s["x"].astype(int), "t_x": s["t_x"], "T": s["T"], "compras": (s["x"] + 1).astype(int),
        "valor_medio": passado["valor_medio"], "dias_calado": (s["T"] - s["t_x"]) * 7,
        "compras_futuras": futuras.astype(int), "receita_futura": receita_futura,
    })
    base["receita"] = base["valor_medio"] * base["compras"]
    return base, bg, gama


def test_quando_o_mundo_e_o_do_modelo_ele_fica_calibrado_e_ordena_melhor_que_o_acaso():
    base, bg, gama = _base_simulada()
    previsoes = analise.prever(base, bg, gama, 52.0)
    indices = av.indices_de_bootstrap(len(base), 60, semente=1)

    erros, _ = analise.erro_nas_compras(base, previsoes, indices)
    assert abs(erros.loc["BG/NBD", "vies_do_total"]) < 0.10  # sem viés quando as hipóteses valem
    assert erros.loc["BG/NBD", "erro_absoluto_medio"] < erros.loc["Taxa histórica do cliente", "erro_absoluto_medio"]
    assert erros.loc["BG/NBD", "eam_inferior"] < erros.loc["BG/NBD", "erro_absoluto_medio"] < erros.loc["BG/NBD", "eam_superior"]

    captura = analise.captura_de_receita(base, previsoes, indices)
    assert captura.loc[analise.ACASO, "top10"] == pytest.approx(0.10)
    assert captura.loc[analise.MODELO, "top10"] > 0.25
    assert captura.loc[analise.TETO, "top10"] >= captura.loc[analise.MODELO, "top10"]
    assert captura.loc[analise.MODELO, "top10_menos_modelo"] == 0.0

    calibracao = analise.calibracao_por_frequencia(base, previsoes)
    assert list(calibracao.index) == [r for r in analise.ROTULOS_DE_FREQUENCIA if r in set(calibracao.index)]  # faixas em ordem
    assert calibracao["clientes"].sum() == len(base)


def test_reajustes_por_bootstrap_ficam_em_torno_do_ajuste():
    base, _, _ = _base_simulada(800)
    bg, gama = analise.ajustar_modelos(base)
    reajustes = analise.reajustes_por_bootstrap(base, bg, gama, repeticoes=12)
    assert len(reajustes) == 12
    assert reajustes["r"].min() < bg.r < reajustes["r"].max()
    assert reajustes["p"].min() < gama.p < reajustes["p"].max()
