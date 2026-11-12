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
from valor_cliente import sobrevivencia as sv

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


def _tri(pt: str, en: str, es: str) -> dict:
    return {"pt": pt, "en": en, "es": es}


def _pct_idioma(valor: float, idioma: str, casas: int = 0) -> str:
    texto = f"{valor * 100:.{casas}f}%"
    return texto if idioma == "en" else texto.replace(".", ",")


def _num_idioma(valor: float, idioma: str, casas: int = 1) -> str:
    texto = f"{valor:.{casas}f}"
    return texto if idioma == "en" else texto.replace(".", ",")


def graficos_extras(
    captura: pd.DataFrame, curvas_de_captura: pd.DataFrame, calibracao: pd.DataFrame, mensal: pd.DataFrame,
    sobrevivencia: dict, silencio: pd.DataFrame,
) -> list[dict]:
    """Os outros achados do README como especificações em dados, para o site desenhar. Mesmo cálculo das figuras."""
    extras = []

    # 1. Captura de receita (figura captura_de_receita.png)
    passo = max(1, int(np.ceil(len(curvas_de_captura) / 80)))
    curvas = curvas_de_captura.iloc[::passo]
    if curvas.index[-1] != curvas_de_captura.index[-1]:
        curvas = pd.concat([curvas, curvas_de_captura.iloc[[-1]]])

    def serie_captura(coluna: str) -> list:
        return [[round(float(x), 4), round(float(y), 4)] for x, y in curvas[coluna].items()]

    m, g, r = (captura.loc[n, "top10"] for n in (analise.MODELO, analise.GASTO, analise.RFM))
    extras.append({
        "tipo": "linhas",
        "titulo": _tri(
            "Para achar os melhores clientes, o modelo empata com a lista de quem mais gastou",
            "To find the best customers, the model only ties with a list of top spenders",
            "Para hallar a los mejores clientes, el modelo empata con la lista de los que más gastaron",
        ),
        "eixo_x": _tri("clientes abordados, do topo da lista para baixo", "customers contacted, from the top of the list down", "clientes contactados, desde el principio de la lista"),
        "eixo_y": _tri("receita do ano seguinte acumulada", "cumulative next-year revenue", "ingresos acumulados del año siguiente"),
        "formato_x": "percentual",
        "formato_y": "percentual",
        "series": [
            {"nome": _tri("BG/NBD + Gamma-Gamma", "BG/NBD + Gamma-Gamma", "BG/NBD + Gamma-Gamma"), "papel": "principal", "pontos": serie_captura(analise.MODELO)},
            {"nome": _tri("Gasto histórico total", "Total past spend", "Gasto histórico total"), "papel": "base", "pontos": serie_captura(analise.GASTO)},
            {"nome": _tri("Regra de RFM por quintos", "Quintile RFM rule", "Regla RFM por quintiles"), "papel": "alternativa", "pontos": serie_captura(analise.RFM)},
            {"nome": _tri("Ordem perfeita (teto)", "Perfect ranking (ceiling)", "Orden perfecto (techo)"), "papel": "neutro", "pontos": serie_captura(analise.TETO)},
        ],
        "leitura": {
            idioma: texto.format(m=_pct_idioma(m, idioma), g=_pct_idioma(g, idioma), r=_pct_idioma(r, idioma))
            for idioma, texto in {
                "pt": "Os 10% de clientes no topo de cada lista concentram {m} da receita do ano seguinte pelo modelo, {g} pelo gasto histórico e {r} pela regra de RFM: para priorizar, a lista simples basta.",
                "en": "The top 10% of each list holds {m} of next-year revenue for the model, {g} for past spend and {r} for the RFM rule: for prioritising, the simple list is enough.",
                "es": "El 10% superior de cada lista concentra el {m} de los ingresos del año siguiente con el modelo, el {g} con el gasto histórico y el {r} con la regla RFM: para priorizar, basta la lista simple.",
            }.items()
        },
    })

    # 2. Retorno por silêncio (figura retorno_por_silencio.png)
    rotulos_silencio = {
        "pt": analise.ROTULOS_DE_SILENCIO,
        "en": ["up to 4", "5 to 13", "14 to 26", "27 to 39", "40 or more"],
        "es": ["hasta 4", "5 a 13", "14 a 26", "27 a 39", "40 o más"],
    }
    uma = silencio[silencio["grupo"] == "Comprou uma vez"].set_index("semanas_calado").reindex(analise.ROTULOS_DE_SILENCIO)
    varias = silencio[silencio["grupo"] == "Comprou duas vezes ou mais"].set_index("semanas_calado").reindex(analise.ROTULOS_DE_SILENCIO)

    def serie_silencio(tabela: pd.DataFrame, coluna: str) -> list:
        return [[rotulo, round(float(tabela.loc[rotulo, coluna]), 4)] for rotulo in analise.ROTULOS_DE_SILENCIO]

    extras.append({
        "tipo": "barras",
        "titulo": _tri(
            "Não existe o dia em que o cliente vai embora: a chance de volta só vai caindo",
            "There is no day a customer leaves: the chance of coming back just keeps fading",
            "No existe el día en que el cliente se va: la probabilidad de volver solo va bajando",
        ),
        "eixo_x": _tri("semanas sem comprar no corte", "weeks without buying at the cutoff", "semanas sin comprar en el corte"),
        "eixo_y": _tri("voltou a comprar em 26 semanas", "bought again within 26 weeks", "volvió a comprar en 26 semanas"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            {"nome": _tri("Comprou duas vezes ou mais: real", "Bought twice or more: actual", "Compró dos veces o más: real"), "papel": "neutro", "pontos": serie_silencio(varias, "voltou_26"), "rotulos": rotulos_silencio},
            {"nome": _tri("Comprou duas vezes ou mais: BG/NBD previa", "Bought twice or more: BG/NBD forecast", "Compró dos veces o más: lo que preveía el BG/NBD"), "papel": "principal", "pontos": serie_silencio(varias, "modelo_26"), "rotulos": rotulos_silencio},
            {"nome": _tri("Comprou uma vez: real", "Bought once: actual", "Compró una vez: real"), "papel": "alternativa", "pontos": serie_silencio(uma, "voltou_26"), "rotulos": rotulos_silencio},
            {"nome": _tri("Comprou uma vez: BG/NBD previa", "Bought once: BG/NBD forecast", "Compró una vez: lo que preveía el BG/NBD"), "papel": "base", "pontos": serie_silencio(uma, "modelo_26"), "rotulos": rotulos_silencio},
        ],
        "leitura": {
            idioma: texto.format(
                a=_pct_idioma(varias.iloc[0]["voltou_26"], idioma), b=_pct_idioma(varias.iloc[2]["voltou_26"], idioma),
                c=_pct_idioma(uma.iloc[0]["voltou_26"], idioma), d=_pct_idioma(uma.iloc[-1]["voltou_26"], idioma),
            )
            for idioma, texto in {
                "pt": "Entre quem já voltou alguma vez, {a} dos que compraram no último mês voltaram em seis meses, contra {b} dos calados havia três a seis meses; quem comprou uma vez só começa em {c} e cai a {d}. O BG/NBD prometia volta demais em todas as faixas.",
                "en": "Among repeat buyers, {a} of those who bought in the last month came back within six months, versus {b} of those silent for three to six months; one-time buyers start at {c} and fall to {d}. BG/NBD promised too many returns in every band.",
                "es": "Entre quienes ya habían vuelto alguna vez, el {a} de los que compraron el último mes volvió en seis meses, frente al {b} de los que llevaban de tres a seis meses sin comprar; quien compró una sola vez empieza en {c} y baja a {d}. El BG/NBD prometía demasiados regresos en todas las franjas.",
            }.items()
        },
    })

    # 3. Calibração por faixa de frequência (figura calibracao_por_frequencia.png)
    faixas_pt = list(calibracao.index)
    traducao_faixas = {
        "en": {"3 a 4": "3 to 4", "5 a 7": "5 to 7", "8 a 15": "8 to 15", "16 ou mais": "16 or more"},
        "es": {"3 a 4": "3 a 4", "5 a 7": "5 a 7", "8 a 15": "8 a 15", "16 ou mais": "16 o más"},
    }
    rotulos_faixas = {"pt": faixas_pt, **{i: [t.get(f, f) for f in faixas_pt] for i, t in traducao_faixas.items()}}

    def serie_faixa(coluna: str) -> list:
        return [[faixa, round(float(calibracao.loc[faixa, coluna]), 3)] for faixa in faixas_pt]

    excesso_zero = float(calibracao.iloc[0]["modelo_sobre_real"])
    excesso_topo = float(calibracao.iloc[-1]["modelo_sobre_real"])
    extras.append({
        "tipo": "barras",
        "titulo": _tri(
            "O modelo prevê compras demais para quem comprou pouco e acerta só os mais frequentes",
            "The model over-forecasts light buyers and only gets the most frequent ones right",
            "El modelo prevé compras de más a quien compró poco y solo acierta con los más frecuentes",
        ),
        "eixo_x": _tri("recompras no ano de calibração", "repeat purchases in the calibration year", "recompras en el año de calibración"),
        "eixo_y": _tri("compras por cliente no ano seguinte", "purchases per customer the following year", "compras por cliente al año siguiente"),
        "formato_x": "numero",
        "formato_y": "numero",
        "series": [
            {"nome": _tri("Real", "Actual", "Real"), "papel": "neutro", "pontos": serie_faixa("real"), "rotulos": rotulos_faixas},
            {"nome": _tri("BG/NBD", "BG/NBD", "BG/NBD"), "papel": "principal", "pontos": serie_faixa("modelo"), "rotulos": rotulos_faixas},
            {"nome": _tri("Taxa histórica do cliente", "Customer's past rate", "Tasa histórica del cliente"), "papel": "base", "pontos": serie_faixa("taxa_historica"), "rotulos": rotulos_faixas},
        ],
        "leitura": {
            idioma: texto.format(z=_num_idioma(excesso_zero, idioma), t=_num_idioma(excesso_topo, idioma, 2))
            for idioma, texto in {
                "pt": "Para quem nunca tinha recomprado, o modelo previu {z} vezes as compras reais; só no grupo mais frequente a razão chega a {t}. A taxa histórica erra para cima quase igual.",
                "en": "For customers who had never bought again, the model forecast {z} times the actual purchases; only in the most frequent group does the ratio reach {t}. The past rate overshoots almost as much.",
                "es": "Para quienes nunca habían vuelto a comprar, el modelo previó {z} veces las compras reales; solo en el grupo más frecuente la razón llega a {t}. La tasa histórica se pasa casi igual.",
            }.items()
        },
    })

    # 4. Sazonalidade (figura sazonalidade.png)
    def serie_mes(coluna: str) -> list:
        return [[f"{mes}-01", round(float(valor), 1)] for mes, valor in mensal[coluna].items()]

    abaixo = int((mensal["real"] < mensal["modelo"]).sum())
    extras.append({
        "tipo": "linhas",
        "titulo": _tri(
            "O modelo prevê um ano plano e alto demais; só no pico de novembro a realidade o alcança",
            "The model forecasts a flat, inflated year; reality only catches up at the November peak",
            "El modelo prevé un año plano y alto; la realidad solo lo alcanza en el pico de noviembre",
        ),
        "eixo_x": _tri("mês do ano de validação", "month of the validation year", "mes del año de validación"),
        "eixo_y": _tri("compras no mês", "purchases in the month", "compras en el mes"),
        "formato_x": "data",
        "formato_y": "numero",
        "series": [
            {"nome": _tri("Real", "Actual", "Real"), "papel": "neutro", "pontos": serie_mes("real")},
            {"nome": _tri("BG/NBD", "BG/NBD", "BG/NBD"), "papel": "principal", "pontos": serie_mes("modelo")},
            {"nome": _tri("Taxa histórica do cliente", "Customer's past rate", "Tasa histórica del cliente"), "papel": "base", "pontos": serie_mes("taxa_historica")},
        ],
        "leitura": {
            idioma: texto.format(n=abaixo, total=len(mensal))
            for idioma, texto in {
                "pt": "Compras por mês dos clientes que já existiam no corte: a realidade ficou abaixo da previsão em {n} dos {total} meses. O modelo não tem sazonalidade e projetou para o ano inteiro o ritmo do fim de 2010.",
                "en": "Monthly purchases by customers who already existed at the cutoff: reality came in below the forecast in {n} of {total} months. The model has no seasonality and projected the late-2010 pace onto the whole year.",
                "es": "Compras por mes de los clientes que ya existían en el corte: la realidad quedó por debajo de lo previsto en {n} de {total} meses. El modelo no tiene estacionalidad y proyectó a todo el año el ritmo de finales de 2010.",
            }.items()
        },
    })

    # 5. Tempo até a recompra, Kaplan-Meier (figura tempo_ate_a_recompra.png)
    nomes = list(sobrevivencia["curvas"])
    semanas = np.arange(0, 40)

    def serie_km(nome: str, coluna: str = "sobrevivencia") -> list:
        valores = 1.0 - sv.sobrevivencia_em(sobrevivencia["curvas"][nome], semanas, coluna)
        return [[int(s), round(float(v), 4)] for s, v in zip(semanas, valores)]

    tabela = sobrevivencia["tabela"]
    mediana_antigos = float(tabela.loc[nomes[0], "semanas_medianas_ate_voltar"])
    mediana_novos = float(tabela.loc[nomes[2], "semanas_medianas_ate_voltar"])
    extras.append({
        "tipo": "linhas",
        "titulo": {
            idioma: texto.format(a=f"{mediana_antigos:.0f}", n=f"{mediana_novos:.0f}")
            for idioma, texto in {
                "pt": "Quem aparece em dez/2009 volta em {a} semanas; cliente novo de verdade leva {n}",
                "en": "Customers first seen in Dec 2009 return in {a} weeks; truly new ones take {n}",
                "es": "Quien aparece en dic/2009 vuelve en {a} semanas; un cliente nuevo de verdad tarda {n}",
            }.items()
        },
        "eixo_x": _tri("semanas desde a primeira compra", "weeks since first purchase", "semanas desde la primera compra"),
        "eixo_y": _tri("já voltou a comprar", "already bought again", "ya volvió a comprar"),
        "formato_x": "numero",
        "formato_y": "percentual",
        "series": [
            {"nome": _tri("Clientes novos da validação (dez/2010 em diante)", "New customers in the validation year (Dec 2010 on)", "Clientes nuevos del año de validación (desde dic/2010)"), "papel": "neutro", "pontos": serie_km(nomes[2])},
            {"nome": _tri("Primeira compra de jan a nov/2010", "First purchase Jan to Nov 2010", "Primera compra de ene a nov/2010"), "papel": "principal", "pontos": serie_km(nomes[1])},
            {"nome": _tri("Primeira compra em dez/2009 (primeiro mês da base)", "First purchase in Dec 2009 (first month of data)", "Primera compra en dic/2009 (primer mes de la base)"), "papel": "base", "pontos": serie_km(nomes[0])},
        ],
        # a curva mostra 1 - S(t): o limite inferior de "já voltou" é 1 - superior de S, e vice-versa
        "faixa": {"serie": 0, "inferior": serie_km(nomes[2], "superior"), "superior": serie_km(nomes[2], "inferior")},
        "leitura": {
            idioma: texto.format(v=_pct_idioma(float(tabela.loc[nomes[2], "voltou_em_26"]), idioma), d=_pct_idioma(float(tabela.loc[nomes[0], "voltou_em_26"]), idioma))
            for idioma, texto in {
                "pt": "Kaplan-Meier do tempo até a segunda compra, com quem ainda não voltou tratado como censurado: {v} dos clientes novos voltam em seis meses, contra {d} de quem aparece no primeiro mês da base, que em boa parte já era cliente antes.",
                "en": "Kaplan-Meier time to second purchase, treating those who have not returned yet as censored: {v} of new customers come back within six months, versus {d} of those first seen in the dataset's first month, many of whom were already customers.",
                "es": "Kaplan-Meier del tiempo hasta la segunda compra, con quienes aún no volvieron tratados como censurados: el {v} de los clientes nuevos vuelve en seis meses, frente al {d} de quienes aparecen en el primer mes de la base, que en buena parte ya eran clientes.",
            }.items()
        },
    })
    return extras


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
        "para_o_site": {
            **bloco_para_o_site(limpeza, novo, captura, silencio),
            "graficos_extras": graficos_extras(captura, curvas_de_captura, calibracao, mensal, sobrevivencia, silencio),
        },
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
