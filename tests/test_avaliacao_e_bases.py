import numpy as np
import pandas as pd
import pytest

from valor_cliente import avaliacao as av
from valor_cliente import linhas_de_base as lb


def test_receita_capturada_casos_de_resposta_conhecida():
    receita = np.array([100.0, 50.0, 30.0, 10.0, 5.0, 3.0, 1.0, 1.0, 0.0, 0.0])
    assert av.receita_capturada(receita, receita, 0.1) == pytest.approx(0.5)  # ordem perfeita: o maior tem metade
    assert av.receita_capturada(receita, receita, 0.2) == pytest.approx(0.75)
    assert av.receita_capturada(-receita, receita, 0.2) == pytest.approx(0.0)  # ordem invertida
    assert av.receita_capturada(np.ones(10), receita, 0.2) == pytest.approx(0.2)  # sem distinguir ninguém


def test_receita_capturada_trata_empate_na_fronteira_pela_media_do_grupo():
    receita = np.array([40.0, 30.0, 20.0, 10.0])
    pontuacao = np.array([3.0, 2.0, 2.0, 1.0])
    # 50% = 2 vagas: o primeiro entra, e a segunda vaga vale a média dos dois empatados (25)
    assert av.receita_capturada(pontuacao, receita, 0.5) == pytest.approx((40 + 25) / 100)


def test_curva_de_captura_cresce_e_termina_em_um():
    gerador = np.random.default_rng(0)
    receita = gerador.exponential(100.0, 500)
    curva = av.curva_de_captura(receita + gerador.normal(0, 50, 500), receita, [0.1, 0.3, 0.6, 1.0])
    assert np.all(np.diff(curva) > 0) and curva[-1] == pytest.approx(1.0)


def test_erros_de_previsao():
    erros = av.erros_de_previsao([1.0, 2.0, 3.0], [1.0, 4.0, 1.0])
    assert erros["erro_absoluto_medio"] == pytest.approx(4 / 3)
    assert erros["raiz_do_erro_quadratico"] == pytest.approx(np.sqrt(8 / 3))
    assert erros["vies_do_total"] == pytest.approx(0.0)


def test_bootstrap_e_intervalo():
    indices = av.indices_de_bootstrap(50, 400, semente=1)
    assert indices.shape == (400, 50) and indices.min() >= 0 and indices.max() < 50
    assert np.array_equal(indices, av.indices_de_bootstrap(50, 400, semente=1))  # semente fixa, mesmo sorteio
    valores = np.random.default_rng(2).normal(10.0, 2.0, 50)
    medias = av.bootstrap(lambda linha: valores[linha].mean(), indices)
    inferior, superior = av.intervalo(medias)
    assert inferior < valores.mean() < superior
    assert superior - inferior == pytest.approx(2 * 1.96 * valores.std() / np.sqrt(50), rel=0.2)


def test_intervalo_de_wilson_valor_de_referencia():
    inferior, superior = av.intervalo_de_wilson(10, 100)
    assert inferior == pytest.approx(0.0552, abs=5e-4) and superior == pytest.approx(0.1744, abs=5e-4)
    assert av.intervalo_de_wilson(0, 20)[0] == pytest.approx(0.0, abs=1e-12)  # nunca sai de 0 a 1
    assert np.isnan(av.intervalo_de_wilson(0, 0)[0])


def test_calibracao_por_faixa():
    faixa = pd.Series(["0", "0", "1+", "1+"])
    tabela = av.calibracao_por_faixa(faixa, [0, 2, 4, 6], {"modelo": np.array([1, 1, 5, 5])})
    assert tabela.loc["0", "real"] == 1 and tabela.loc["1+", "modelo"] == 5 and tabela.loc["0", "clientes"] == 2


def test_taxa_historica_e_media_da_base():
    x, T = np.array([0, 2, 6]), np.array([10.0, 20.0, 30.0])
    np.testing.assert_allclose(lb.compras_pela_taxa_historica(x, T, 10.0), [0.0, 1.0, 2.0])
    np.testing.assert_allclose(lb.compras_pela_media_da_base(x, T, 15.0), [2.0, 2.0, 2.0])  # 8 recompras em 60 semanas
    assert lb.compras_pela_taxa_historica([3], [0.0], 10.0)[0] == 0.0  # cliente do último dia: sem taxa


def test_faixas_de_rfm_mantem_empates_juntos():
    frequencia = np.array([0, 0, 0, 0, 0, 0, 1, 2, 3, 9])
    notas = lb.faixas(frequencia)
    assert len(set(notas[:6])) == 1  # quem empata em zero fica na mesma faixa
    assert notas[-1] == 5 and np.all(np.diff(notas) >= 0)
    assert list(lb.faixas([10, 20, 30, 40, 50], maior_e_melhor=False)) == [5, 4, 3, 2, 1]


def test_pontuacao_rfm_soma_as_tres_notas():
    notas = lb.pontuacao_rfm(recencia=[1, 50, 100, 200, 300], frequencia=[9, 4, 2, 1, 0], valor=[500, 400, 300, 200, 100])
    assert list(notas["RFM"]) == [15, 12, 9, 6, 3]
