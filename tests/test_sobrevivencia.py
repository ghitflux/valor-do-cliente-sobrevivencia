import numpy as np
import pytest

from valor_cliente import sobrevivencia as sv

# Exemplo clássico dos livros de sobrevivência: remissão de leucemia com 6-MP (Freireich et al., 1963).
# Tempos em semanas; evento = recaída observada, 0 = censurado.
TEMPOS = [6, 6, 6, 6, 7, 9, 10, 10, 11, 13, 16, 17, 19, 20, 22, 23, 25, 32, 32, 34, 35]
EVENTOS = [1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0]


def test_kaplan_meier_reproduz_o_exemplo_de_livro():
    curva = sv.kaplan_meier(TEMPOS, EVENTOS)
    assert list(curva["tempo"]) == [6, 7, 10, 13, 16, 22, 23]
    assert list(curva["em_risco"]) == [21, 17, 15, 12, 11, 7, 6]
    assert list(curva["eventos"]) == [3, 1, 1, 1, 1, 1, 1]
    np.testing.assert_allclose(curva["sobrevivencia"], [0.857, 0.807, 0.753, 0.690, 0.627, 0.538, 0.448], atol=6e-4)
    np.testing.assert_allclose(curva["erro_padrao"], [0.0764, 0.0869, 0.0963, 0.1068, 0.1141, 0.1282, 0.1346], atol=6e-5)
    assert sv.tempo_mediano(curva) == 23


def test_sem_censura_e_a_proporcao_que_ainda_nao_teve_o_evento():
    duracao = np.array([1, 2, 2, 3, 5, 8, 8, 9, 12, 15])
    curva = sv.kaplan_meier(duracao, np.ones(10, dtype=bool))
    for tempo, s in zip(curva["tempo"], curva["sobrevivencia"]):
        assert s == pytest.approx((duracao > tempo).mean())


def test_intervalo_fica_entre_zero_e_um_e_contem_a_estimativa():
    curva = sv.kaplan_meier(TEMPOS, EVENTOS)
    assert ((curva["inferior"] >= 0) & (curva["superior"] <= 1)).all()
    assert ((curva["inferior"] < curva["sobrevivencia"]) & (curva["sobrevivencia"] < curva["superior"])).all()


def test_intervalo_cobre_a_curva_verdadeira_em_dados_simulados_com_censura():
    gerador = np.random.default_rng(3)
    verdadeira = np.exp(-10.0 / 20.0)  # S(10) de uma exponencial de média 20
    cobriu = 0
    for _ in range(300):
        tempo = gerador.exponential(20.0, 200)
        censura = gerador.uniform(0.0, 40.0, 200)
        curva = sv.kaplan_meier(np.minimum(tempo, censura), tempo <= censura)
        inferior, superior = sv.sobrevivencia_em(curva, 10.0, "inferior")[0], sv.sobrevivencia_em(curva, 10.0, "superior")[0]
        cobriu += inferior <= verdadeira <= superior
    assert 0.91 <= cobriu / 300 <= 0.99  # nominal: 95%


def test_curva_em_degraus_e_chance_de_voltar():
    curva = sv.kaplan_meier(TEMPOS, EVENTOS)
    np.testing.assert_allclose(sv.sobrevivencia_em(curva, [0, 5.9, 6, 6.5, 22.5, 40]), [1.0, 1.0, 0.857, 0.857, 0.538, 0.448], atol=6e-4)
    # quem chegou à semana 10 sem o evento: chance de tê-lo nas 13 semanas seguintes = 1 - S(23) / S(10)
    assert sv.chance_de_voltar(curva, 10, 13)[0] == pytest.approx(1 - 0.448 / 0.753, abs=2e-3)
    assert sv.chance_de_voltar(curva, 0, 5)[0] == 0.0
