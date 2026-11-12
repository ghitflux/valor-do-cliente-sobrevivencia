"""Roda a análise completa e grava reports/resultados.json e as figuras do README.

Uso: uv run python scripts/rodar_analise.py
Lê só o extrato versionado em data/ (não precisa do bruto nem de rede).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from valor_cliente import analise, dados, graficos
from valor_cliente import avaliacao as av

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "reports"
FIGURAS = SAIDA / "figuras"


def _json(tabela: pd.DataFrame, orient: str = "index"):
    return json.loads(tabela.to_json(orient=orient, force_ascii=False))


def _libras(valor: float, idioma: str) -> str:
    texto = f"{valor:,.0f}"
    return "£" + (texto if idioma == "en" else texto.replace(",", "."))


def _inteiro(valor: float, idioma: str) -> str:
    texto = f"{valor:,.0f}"
    return texto if idioma == "en" else texto.replace(",", ".")


def _pct(valor: float) -> str:
    return f"{valor * 100:.0f}%"


def bloco_para_o_site(limpeza: dict, novo: dict, captura: pd.DataFrame, silencio: pd.DataFrame) -> dict:
    """Textos e gráfico que o site do portfólio desenha, nos três idiomas. Todo número sai dos resultados."""
    linha = novo["tabela"].loc[f"{analise.HORIZONTE_PRINCIPAL} semanas"]
    curvas = novo["curvas"]
    modelo, real = linha["modelo_receita"], linha["real_receita"]
    top_modelo = captura.loc[analise.MODELO, "top10"]
    top_gasto = captura.loc[analise.GASTO, "top10"]
    top_rfm = captura.loc[analise.RFM, "top10"]
    calados = silencio[(silencio["grupo"] == "Comprou uma vez") & (silencio["semanas_calado"] == analise.ROTULOS_DE_SILENCIO[-1])].iloc[0]
    numero_chave = f"£{modelo:.0f} → £{real:.0f}"
    assert len(numero_chave) <= 12, numero_chave

    def pontos(coluna: str) -> list[list[float]]:
        return [[int(semana), round(float(valor), 1)] for semana, valor in curvas[coluna].items()]

    return {
        "numero_chave": {"pt": numero_chave, "en": numero_chave, "es": numero_chave},
        "pergunta": {
            "pt": "Quanto vale um cliente novo nos próximos meses, e quando dá para considerar que ele foi embora?",
            "en": "How much is a new customer worth over the next few months, and when is it fair to say they are gone?",
            "es": "¿Cuánto vale un cliente nuevo en los próximos meses y cuándo se puede dar por perdido?",
        },
        "resultado": {
            "pt": (
                f"Com um ano de histórico, o modelo BG/NBD + Gamma-Gamma prometia {_libras(modelo, 'pt')} em recompras por cliente novo em seis meses; "
                f"os clientes novos do ano seguinte entregaram {_libras(real, 'pt')}. Para ordenar quem já é cliente, o modelo empata com a lista de quem mais "
                f"gastou: os 10% do topo concentram {_pct(top_modelo)} da receita futura, contra {_pct(top_gasto)} da lista simples e {_pct(top_rfm)} da regra de RFM."
            ),
            "en": (
                f"With one year of history, the BG/NBD + Gamma-Gamma model promised {_libras(modelo, 'en')} in repeat revenue per new customer over six months; "
                f"the customers who actually arrived the following year delivered {_libras(real, 'en')}. For ranking existing customers the model merely ties with a "
                f"plain list of top spenders: its top 10% holds {_pct(top_modelo)} of future revenue, versus {_pct(top_gasto)} for the simple list and {_pct(top_rfm)} for an RFM rule."
            ),
            "es": (
                f"Con un año de historial, el modelo BG/NBD + Gamma-Gamma prometía {_libras(modelo, 'es')} en recompras por cliente nuevo en seis meses; "
                f"los clientes nuevos del año siguiente dejaron {_libras(real, 'es')}. Para ordenar a quienes ya son clientes, el modelo empata con la lista de los que "
                f"más gastaron: el 10% superior concentra el {_pct(top_modelo)} de los ingresos futuros, frente al {_pct(top_gasto)} de la lista simple y el {_pct(top_rfm)} de la regla RFM."
            ),
        },
        "detalhe": {
            "pt": (
                "O erro vem dos dados, não da conta: a base não diz quem é novo de verdade, e um ano que termina no pico de novembro esconde o abandono "
                "(a faixa azul é a incerteza dos parâmetros, e a realidade fica bem fora dela). E não existe o dia em que o cliente vai embora: de quem comprou uma "
                f"vez e estava calado havia mais de nove meses, {_pct(calados['voltou_52'])} ainda voltaram no ano seguinte."
            ),
            "en": (
                "The error comes from the data, not the maths: the dataset cannot tell who is truly new, and a year that ends at the November peak hides churn "
                "(the blue band is parameter uncertainty, and reality sits well outside it). There is also no day on which a customer leaves: among one-time buyers "
                f"silent for more than nine months, {_pct(calados['voltou_52'])} still came back within the next year."
            ),
            "es": (
                "El error viene de los datos, no de la cuenta: la base no dice quién es nuevo de verdad, y un año que termina en el pico de noviembre esconde el "
                "abandono (la franja azul es la incertidumbre de los parámetros, y la realidad queda muy fuera de ella). Tampoco existe el día en que el cliente se va: "
                f"de quienes compraron una vez y llevaban más de nueve meses en silencio, el {_pct(calados['voltou_52'])} volvió durante el año siguiente."
            ),
        },
        "dados": {
            "pt": f"Online Retail II (UCI, CC BY 4.0): {_inteiro(limpeza['clientes'], 'pt')} clientes e {_inteiro(limpeza['dias_de_compra'], 'pt')} dias de compra de um varejista online britânico, de dezembro de 2009 a dezembro de 2011.",
            "en": f"Online Retail II (UCI, CC BY 4.0): {_inteiro(limpeza['clientes'], 'en')} customers and {_inteiro(limpeza['dias_de_compra'], 'en')} purchase days from a UK online retailer, December 2009 to December 2011.",
            "es": f"Online Retail II (UCI, CC BY 4.0): {_inteiro(limpeza['clientes'], 'es')} clientes y {_inteiro(limpeza['dias_de_compra'], 'es')} días de compra de un minorista online británico, de diciembre de 2009 a diciembre de 2011.",
        },
        "etiquetas": ["BG/NBD", "Gamma-Gamma", "Kaplan-Meier", "CLV", "validação temporal", "bootstrap"],
        "grafico": {
            "tipo": "linhas",
            "titulo": {
                "pt": "Receita de recompra por cliente novo: prevista no corte e realizada",
                "en": "Repeat revenue per new customer: forecast at the cutoff vs. what happened",
                "es": "Ingresos por recompra de un cliente nuevo: previstos en el corte y reales",
            },
            "eixo_x": {"pt": "semanas desde a primeira compra", "en": "weeks since first purchase", "es": "semanas desde la primera compra"},
            "eixo_y": {"pt": "receita acumulada por cliente (£)", "en": "cumulative revenue per customer (£)", "es": "ingresos acumulados por cliente (£)"},
            "formato_x": "numero",
            "formato_y": "numero",
            "series": [
                {"nome": {"pt": "Modelo BG/NBD + Gamma-Gamma", "en": "BG/NBD + Gamma-Gamma model", "es": "Modelo BG/NBD + Gamma-Gamma"}, "papel": "principal", "pontos": pontos("modelo")},
                {"nome": {"pt": "Média da base", "en": "Customer-base average", "es": "Promedio de la base"}, "papel": "base", "pontos": pontos("media_da_base")},
                {"nome": {"pt": "Modelo sem os clientes de dez/2009", "en": "Model without the Dec 2009 customers", "es": "Modelo sin los clientes de dic/2009"}, "papel": "alternativa", "pontos": pontos("diagnostico_modelo")},
                {"nome": {"pt": "Real (clientes novos do ano seguinte)", "en": "Actual (next year's new customers)", "es": "Real (clientes nuevos del año siguiente)"}, "papel": "neutro", "pontos": pontos("real")},
            ],
            "faixa": {"serie": 0, "inferior": pontos("modelo_inferior"), "superior": pontos("modelo_superior")},
        },
    }


def _curva_para_json(curva: pd.DataFrame, maximo: int = 80) -> list:
    passo = max(1, int(np.ceil(len(curva) / maximo)))
    return _json(curva.iloc[::passo][["tempo", "em_risco", "sobrevivencia", "inferior", "superior"]].round(4), "records")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = time.perf_counter()
    FIGURAS.mkdir(parents=True, exist_ok=True)

    compras, cancelamentos, limpeza = dados.carregar_compras(), dados.carregar_cancelamentos(), dados.carregar_limpeza()
    base = dados.montar_base(compras, cancelamentos, analise.CORTE, analise.FIM_DA_VALIDACAO)
    compras_liquidas = dados.compras_conhecidas_em(compras, cancelamentos, pd.Timestamp.max)
    horizonte = analise.semanas_entre(analise.CORTE, analise.FIM_DA_VALIDACAO)

    bg, gama = analise.ajustar_modelos(base)
    previsoes = analise.prever(base, bg, gama, horizonte)
    indices = av.indices_de_bootstrap(len(base), analise.REPETICOES, analise.SEMENTE)

    resumo = analise.resumo_da_base(base, horizonte)
    parametros = analise.parametros(bg, gama, previsoes)
    erros, diferencas = analise.erro_nas_compras(base, previsoes, indices)
    calibracao = analise.calibracao_por_frequencia(base, previsoes)
    mensal = analise.acompanhamento_mensal(base, bg, compras_liquidas)
    captura = analise.captura_de_receita(base, previsoes, indices)
    curvas_de_captura = analise.curvas_de_captura(base, previsoes, pontos=101)
    independencia = analise.independencia_frequencia_valor(base)
    ticket = analise.erro_no_ticket(base, previsoes)
    reajustes = analise.reajustes_por_bootstrap(base, bg, gama)
    novo = analise.valor_do_cliente_novo(compras, cancelamentos, base, bg, gama, reajustes)
    sobrevivencia = analise.curvas_de_sobrevivencia(compras, cancelamentos)
    silencio = analise.retorno_por_silencio(base, bg, compras_liquidas)
    cortes = analise.sensibilidade_ao_corte(compras, cancelamentos)

    linha_principal = novo["tabela"].loc[f"{analise.HORIZONTE_PRINCIPAL} semanas"]
    figuras = {
        "valor_do_cliente_novo": graficos.valor_do_cliente_novo(novo["curvas"], linha_principal),
        "captura_de_receita": graficos.captura_de_receita(curvas_de_captura, captura),
        "calibracao_por_frequencia": graficos.calibracao_por_frequencia(calibracao),
        "sazonalidade": graficos.sazonalidade(mensal),
        "tempo_ate_a_recompra": graficos.tempo_ate_a_recompra(sobrevivencia["curvas"], sobrevivencia["tabela"]),
        "retorno_por_silencio": graficos.retorno_por_silencio(silencio),
    }
    for nome, figura in figuras.items():
        figura.savefig(FIGURAS / f"{nome}.png")
        plt.close(figura)

    intervalos_dos_parametros = {
        coluna: {"inferior": float(reajustes[coluna].quantile(0.025)), "superior": float(reajustes[coluna].quantile(0.975))}
        for coluna in reajustes.columns
    }
    resultados = {
        "limpeza": limpeza,
        "base": resumo,
        "parametros": {**parametros, "intervalos_de_95_por_bootstrap": intervalos_dos_parametros, "reajustes": int(len(reajustes))},
        "erro_nas_compras": {"tabela": _json(erros), **diferencas},
        "calibracao_por_frequencia": _json(calibracao),
        "acompanhamento_mensal": _json(mensal),
        "captura_de_receita": _json(captura),
        "curvas_de_captura": _json(curvas_de_captura.round(4).reset_index(), "records"),
        "independencia_frequencia_valor": {
            **{k: v for k, v in independencia.items() if k != "ticket_por_faixa_de_compras"},
            "ticket_por_faixa_de_compras": _json(independencia["ticket_por_faixa_de_compras"]),
        },
        "erro_no_ticket": _json(ticket),
        "cliente_novo": {
            **{k: v for k, v in novo.items() if k not in ("tabela", "curvas", "distribuicao")},
            "tabela": _json(novo["tabela"]),
            "curvas": _json(novo["curvas"].round(2).reset_index(), "records"),
            "distribuicao": _json(novo["distribuicao"]),
        },
        "sobrevivencia": {
            "tabela": _json(sobrevivencia["tabela"]),
            "chance_de_voltar": sobrevivencia["chance_de_voltar"],
            "curvas": {nome: _curva_para_json(curva) for nome, curva in sobrevivencia["curvas"].items()},
        },
        "retorno_por_silencio": _json(silencio, "records"),
        "sensibilidade_ao_corte": _json(cortes),
        "bootstrap": {"repeticoes_das_metricas": analise.REPETICOES, "reajustes_dos_modelos": analise.REPETICOES_DE_AJUSTE, "semente": analise.SEMENTE},
        "para_o_site": bloco_para_o_site(limpeza, novo, captura, silencio),
    }
    (SAIDA / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print(resumo)
    print(parametros)
    print(erros.to_string())
    print(diferencas)
    print(calibracao.to_string())
    print(mensal.to_string())
    print(captura.to_string())
    print({k: v for k, v in independencia.items() if k != "ticket_por_faixa_de_compras"})
    print(independencia["ticket_por_faixa_de_compras"].to_string())
    print(ticket.to_string())
    print(novo["tabela"].T.to_string())
    print(novo["distribuicao"].to_string())
    print(sobrevivencia["tabela"].to_string())
    print(json.dumps(sobrevivencia["chance_de_voltar"], indent=1, ensure_ascii=False))
    print(silencio.to_string())
    print(cortes.T.to_string())
    print(f"Gravado em {SAIDA / 'resultados.json'} e {FIGURAS} em {time.perf_counter() - inicio:.0f} s")


if __name__ == "__main__":
    main()
