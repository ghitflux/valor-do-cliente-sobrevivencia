import numpy as np
import pandas as pd
import pytest

from valor_cliente import dados

PRIMEIRA, SEGUNDA = "Year 2009-2010", "Year 2010-2011"


def _bruto() -> pd.DataFrame:
    """Quinze linhas que exercitam cada passo da limpeza. Tudo em memória, sem arquivo."""
    linhas = [
        # aba, fatura, item, quantidade, data, preço, cliente
        (PRIMEIRA, "100", "10001", 2, "2010-01-05 10:00", 5.0, 1),      # compra válida (10); cancelada só em 2011
        (PRIMEIRA, "100", "POST", 1, "2010-01-05 10:00", 18.0, 1),      # frete: não é produto
        (PRIMEIRA, "101", "10002", 3, "2010-02-01 09:00", 4.0, None),   # sem cliente
        (PRIMEIRA, "102", "10003", 10, "2010-03-01 09:00", 2.0, 2),     # compra válida (20), cancelada dias depois
        (PRIMEIRA, "C103", "10003", -10, "2010-03-10 09:00", 2.0, 2),   # o cancelamento dela
        (PRIMEIRA, "104", "10004", 1, "2010-03-01 11:00", 7.0, 2),      # outra fatura no mesmo dia (7)
        (PRIMEIRA, "105", "10005", 5, "2010-04-01 09:00", 0.0, 1),      # preço zero
        (PRIMEIRA, "106", "10001", 1, "2010-12-02 09:00", 5.0, 1),      # repetida na segunda aba
        (PRIMEIRA, "C107", "10001", -1, "2010-05-01 09:00", 5.0, 3),    # cancelamento sem compra correspondente
        (PRIMEIRA, "108", "10006", 4, "2010-06-01 09:00", 25.0, 3),     # compra válida (100), estornada como "Manual"
        (PRIMEIRA, "C109", "M", -1, "2010-06-03 09:00", 100.0, 3),      # o estorno manual, de mesmo valor
        (SEGUNDA, "106", "10001", 1, "2010-12-02 09:00", 5.0, 1),       # a versão que fica
        (SEGUNDA, "A110", "B", 1, "2011-01-01 09:00", 50.0, 1),         # fatura de ajuste, não é venda
        (SEGUNDA, "C112", "10001", -2, "2011-01-15 09:00", 5.0, 1),     # cancela a compra de 2010-01-05, não a de fevereiro
        (SEGUNDA, "111", "10001", 2, "2011-02-01 09:00", 5.0, 1),       # compra válida (10), posterior ao cancelamento
    ]
    bruto = pd.DataFrame(linhas, columns=["aba", "fatura", "codigo_item", "quantidade", "data", "preco", "cliente"])
    bruto["data"] = pd.to_datetime(bruto["data"])
    return bruto


def test_limpeza_conta_cada_passo_e_agrega_por_cliente_e_dia():
    por_dia, canceladas, relatorio = dados.limpar(_bruto())
    assert relatorio["linhas_brutas"] == 15
    assert relatorio["linhas_repetidas_entre_abas"] == 1
    assert relatorio["linhas_sem_cliente"] == 1
    assert relatorio["linhas_de_cancelamento"] == 4
    assert relatorio["linhas_de_outras_faturas_nao_venda"] == 1
    assert relatorio["linhas_com_quantidade_ou_preco_nao_positivo"] == 1
    assert relatorio["linhas_de_itens_nao_produto"] == 1
    assert relatorio["linhas_de_compra_validas"] == 6
    assert relatorio["clientes"] == 3 and relatorio["dias_de_compra"] == 5

    esperado = {(1, "2010-01-05"): 10.0, (1, "2010-12-02"): 5.0, (1, "2011-02-01"): 10.0, (2, "2010-03-01"): 27.0, (3, "2010-06-01"): 100.0}
    obtido = {(c, str(d.date())): r for c, d, r in zip(por_dia["cliente"], por_dia["dia"], por_dia["receita"])}
    assert obtido == esperado
    assert por_dia.loc[por_dia["cliente"] == 2, "faturas"].item() == 2


def test_cancelamento_casa_com_a_compra_anterior_mais_recente():
    _, canceladas, relatorio = dados.limpar(_bruto())
    obtido = {(c, str(d.date()), str(k.date())): v for c, d, k, v in canceladas.itertuples(index=False)}
    assert obtido == {
        (2, "2010-03-01", "2010-03-10"): 20.0,   # mesmo item, quantidade e preço
        (3, "2010-06-01", "2010-06-03"): 100.0,  # estorno "Manual" casado pelo valor
        (1, "2010-01-05", "2011-01-15"): 10.0,   # a compra anterior ao cancelamento, não a posterior
    }
    assert relatorio["linhas_de_compra_canceladas_depois"] == 3
    assert relatorio["valor_das_compras_canceladas_depois"] == pytest.approx(130.0)


def test_cancelamento_so_e_descontado_depois_que_acontece():
    por_dia, canceladas, _ = dados.limpar(_bruto())

    def receita(data: str) -> dict:
        conhecidas = dados.compras_conhecidas_em(por_dia, canceladas, data)
        return {(c, str(d.date())): r for c, d, r in conhecidas.itertuples(index=False)}

    assert receita("2010-03-05") == {(1, "2010-01-05"): 10.0, (2, "2010-03-01"): 27.0}  # cancelamento ainda não existe
    no_fim_de_2010 = receita("2010-12-31")
    assert no_fim_de_2010[(2, "2010-03-01")] == 7.0           # já descontado
    assert (3, "2010-06-01") not in no_fim_de_2010            # dia todo cancelado: deixa de ser compra
    assert no_fim_de_2010[(1, "2010-01-05")] == 10.0          # só será cancelada em 2011: no corte ainda vale
    assert (1, "2010-01-05") not in receita("2011-12-31")


def test_base_por_cliente_separa_calibracao_e_validacao_sem_olhar_o_futuro():
    compras = pd.DataFrame({
        "cliente": [1, 1, 1, 1, 1, 2, 3],
        "dia": pd.to_datetime(["2010-01-01", "2010-01-15", "2010-03-12", "2010-07-01", "2010-08-01", "2010-02-01", "2010-05-01"]),
        "receita": [100.0, 50.0, 30.0, 80.0, 20.0, 40.0, 60.0],
        "faturas": 1,
    })
    cancelamentos = pd.DataFrame({
        "cliente": [2], "dia": pd.to_datetime(["2010-02-01"]), "dia_do_cancelamento": pd.to_datetime(["2010-06-15"]), "valor": [40.0],
    })
    base = dados.montar_base(compras, cancelamentos, "2010-03-31", "2010-12-31").set_index("cliente")
    assert list(base.index) == [1, 2]  # o cliente 3 só aparece depois do corte

    um = base.loc[1]
    assert um["x"] == 2 and um["compras"] == 3
    assert um["t_x"] == pytest.approx(70 / 7) and um["T"] == pytest.approx(89 / 7)
    assert um["receita"] == 180.0 and um["valor_medio"] == 60.0 and um["dias_calado"] == 19
    assert um["compras_futuras"] == 2 and um["receita_futura"] == 100.0

    dois = base.loc[2]
    # a compra do cliente 2 foi cancelada em junho, depois do corte: na calibração ela ainda existe
    assert dois["x"] == 0 and dois["t_x"] == 0.0 and dois["receita"] == 40.0
    assert dois["compras_futuras"] == 0 and dois["receita_futura"] == 0.0
    assert np.issubdtype(base["compras_futuras"].dtype, np.integer)
