"""Figuras do estudo. A cor segue o método em todas elas:

tinta escura = o que aconteceu de verdade; azul = o modelo (BG/NBD + Gamma-Gamma);
laranja = a alternativa simples; verde-água = variante de diagnóstico; cinza = referência.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from valor_cliente import analise
from valor_cliente.estilo import (
    APAGADO, AQUA, AZUL, EIXO, ESTILO, LARANJA, SUPERFICIE, TINTA, TINTA_SECUNDARIA, milhar, nova_figura, numero, percentual,
)

REAL = TINTA


def _libras(valor: float) -> str:
    return f"£{milhar(valor)}"


def _rotulo_no_fim(ax, x: float, y: float, texto: str, deslocamento: float = 0.0, negrito: bool = False) -> None:
    ax.annotate(
        texto, (x, y), xytext=(7, deslocamento), textcoords="offset points", va="center", fontsize=9,
        color=TINTA if negrito else TINTA_SECUNDARIA, fontweight="bold" if negrito else "normal",
    )


def valor_do_cliente_novo(curvas: pd.DataFrame, linha: pd.Series) -> Figure:
    """Receita de recompra acumulada por cliente novo: previsões feitas no corte contra o que aconteceu."""
    semanas = curvas.index.to_numpy()
    fim = semanas[-1]
    with plt.rc_context(ESTILO):
        fig, ax = nova_figura(
            f"O modelo prometia {_libras(linha['modelo_receita'])} por cliente novo em seis meses; vieram {_libras(linha['real_receita'])}",
            "Receita média de recompra acumulada por cliente, em libras, nas 26 semanas depois da primeira compra. Faixas: intervalo de 95%.",
            altura=4.8,
        )
        fig.subplots_adjust(right=0.80, bottom=0.21)
        ax.fill_between(semanas, curvas["modelo_inferior"], curvas["modelo_superior"], color=AZUL, alpha=0.18, linewidth=0)
        ax.fill_between(semanas, curvas["real_inferior"], curvas["real_superior"], color=REAL, alpha=0.10, linewidth=0)
        ax.plot(semanas, curvas["media_da_base"], color=LARANJA, label="Média da base (ritmo médio x ticket médio)")
        ax.plot(semanas, curvas["modelo"], color=AZUL, label="BG/NBD + Gamma-Gamma, ajustado em um ano de base")
        ax.plot(semanas, curvas["diagnostico_modelo"], color=AQUA, label="O mesmo modelo sem os clientes de dez/2009 (diagnóstico)")
        ax.plot(semanas, curvas["real"], color=REAL, label=f"Real: {milhar(linha['clientes_novos_acompanhados'])} clientes novos da validação")
        _rotulo_no_fim(ax, fim, curvas["media_da_base"].iloc[-1], _libras(curvas["media_da_base"].iloc[-1]), deslocamento=5)
        _rotulo_no_fim(ax, fim, curvas["modelo"].iloc[-1], _libras(curvas["modelo"].iloc[-1]), deslocamento=-5, negrito=True)
        _rotulo_no_fim(ax, fim, curvas["diagnostico_modelo"].iloc[-1], _libras(curvas["diagnostico_modelo"].iloc[-1]))
        _rotulo_no_fim(ax, fim, curvas["real"].iloc[-1], _libras(curvas["real"].iloc[-1]), negrito=True)
        ax.set_xlim(0, fim)
        ax.set_ylim(0, None)
        ax.set_xticks([0, 4, 8, 13, 17, 21, 26])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _libras(v)))
        ax.set_xlabel("semanas desde a primeira compra")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8.5, columnspacing=1.4, handlelength=1.6)
        return fig


def captura_de_receita(curvas: pd.DataFrame, tabela: pd.DataFrame) -> Figure:
    """Curva de ganho: receita da validação acumulada pelos clientes ordenados por cada método."""
    with plt.rc_context(ESTILO):
        modelo, gasto, rfm = (tabela.loc[nome, "top10"] for nome in (analise.MODELO, analise.GASTO, analise.RFM))
        fig, ax = nova_figura(
            "Para achar os melhores clientes, o modelo empata com a lista de quem mais gastou",
            f"Parte da receita do ano seguinte nos clientes do topo de cada lista. Nos 10% do topo: modelo {percentual(modelo)}, "
            f"gasto histórico {percentual(gasto)}, RFM {percentual(rfm)}.",
            altura=4.8,
        )
        fig.subplots_adjust(bottom=0.21)
        x = curvas.index.to_numpy()
        ax.plot(x, curvas[analise.TETO], color=APAGADO, linewidth=1.2, label="Ordem perfeita (teto)")
        ax.plot(x, x, color=EIXO, linewidth=1.2, label="Ao acaso")
        ax.plot(x, curvas[analise.RFM], color=AQUA, label="Regra de RFM por quintos")
        ax.plot(x, curvas[analise.GASTO], color=LARANJA, label="Gasto histórico total")
        ax.plot(x, curvas[analise.MODELO], color=AZUL, label="BG/NBD + Gamma-Gamma")
        ax.text(0.34, 0.66, "No topo da lista do modelo:", fontsize=9, color=TINTA_SECUNDARIA)
        for fracao, chave, altura in ((0.1, "top10", 0.60), (0.2, "top20", 0.54)):
            valor = tabela.loc[analise.MODELO, chave]
            ax.plot(fracao, valor, "o", color=AZUL, zorder=5)
            ax.text(0.34, altura, f"{percentual(fracao)} dos clientes concentram {percentual(valor)} da receita", fontsize=9, color=TINTA)
        ax.set_xlim(0, 0.6)
        ax.set_ylim(0, 1.0)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: percentual(v)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: percentual(v)))
        ax.set_xlabel("clientes abordados, do topo da lista para baixo")
        ax.set_ylabel("receita futura acumulada")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=5, fontsize=8.5, columnspacing=1.2, handlelength=1.4)
        return fig


def calibracao_por_frequencia(tabela: pd.DataFrame) -> Figure:
    """Previsto dividido pelo real, por faixa de recompras na calibração (1 = acertou)."""
    with plt.rc_context(ESTILO):
        fig, ax = nova_figura(
            "O modelo prevê compras demais para quem comprou pouco e acerta só os mais frequentes",
            "Compras previstas para o ano seguinte divididas pelas reais, por faixa de recompras no ano de calibração.",
            altura=4.4,
        )
        fig.subplots_adjust(bottom=0.24)
        posicoes = np.arange(len(tabela))
        razao_taxa = tabela["taxa_historica"] / tabela["real"]
        ax.axhline(1.0, color=EIXO, linewidth=1.2, zorder=1)
        ax.annotate("previsão = realidade", (posicoes[len(posicoes) // 2], 1.0), xytext=(0, -9), textcoords="offset points", ha="center", color=APAGADO, fontsize=8.5)
        ax.plot(posicoes, razao_taxa, "-o", color=LARANJA, label="Taxa histórica do cliente", zorder=3)
        ax.plot(posicoes, tabela["modelo_sobre_real"], "-o", color=AZUL, label="BG/NBD", zorder=4)
        for i, acima in ((0, True), (len(tabela) - 1, False)):
            ax.annotate(
                f"{numero(tabela['modelo_sobre_real'].iloc[i], 1)}x", (posicoes[i], tabela["modelo_sobre_real"].iloc[i]),
                xytext=(0, 9 if acima else -13), textcoords="offset points", ha="center", fontsize=9, color=TINTA,
            )
        ax.annotate("prevê zero", (posicoes[0], razao_taxa.iloc[0]), xytext=(9, 6), textcoords="offset points", fontsize=8.5, color=TINTA_SECUNDARIA)
        ax.set_xticks(posicoes, [f"{rotulo}\n({milhar(n)} clientes)" for rotulo, n in zip(tabela.index, tabela["clientes"])], fontsize=8.5)
        ax.set_xlim(-0.4, len(tabela) - 0.6)
        ax.set_ylim(0, max(2.8, float(tabela["modelo_sobre_real"].max()) + 0.3))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{numero(v, 1)}x"))
        ax.set_xlabel("recompras no ano de calibração")
        ax.set_ylabel("previsto ÷ real")
        ax.legend(loc="upper right", ncol=2, fontsize=8.5)
        return fig


def sazonalidade(mensal: pd.DataFrame) -> Figure:
    """Compras por mês na validação: o modelo, a taxa histórica e o que aconteceu."""
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    rotulos = [f"{nomes[int(m[5:]) - 1]}/{m[2:4]}" for m in mensal.index]
    with plt.rc_context(ESTILO):
        pico = mensal["real"].idxmax()
        fig, ax = nova_figura(
            "O modelo prevê um ano plano e alto demais; só no pico de novembro a realidade o alcança",
            "Compras por mês, no ano de validação, dos clientes que já existiam no corte (30/11/2010).",
            altura=4.4,
        )
        fig.subplots_adjust(bottom=0.2)
        x = np.arange(len(mensal))
        ax.plot(x, mensal["taxa_historica"], "-o", color=LARANJA, label="Taxa histórica do cliente", markersize=6)
        ax.plot(x, mensal["modelo"], "-o", color=AZUL, label="BG/NBD", markersize=6)
        ax.plot(x, mensal["real"], "-o", color=REAL, label="Real", markersize=6)
        i_pico = list(mensal.index).index(pico)
        ax.annotate(milhar(mensal["real"].iloc[i_pico]), (i_pico, mensal["real"].iloc[i_pico]), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9, color=TINTA)
        i_vale = int(np.argmin(mensal["real"].to_numpy()))
        ax.annotate(milhar(mensal["real"].iloc[i_vale]), (i_vale, mensal["real"].iloc[i_vale]), xytext=(0, -14), textcoords="offset points", ha="center", fontsize=9, color=TINTA)
        ax.set_xticks(x, rotulos)
        ax.set_ylim(0, None)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: milhar(v)))
        ax.set_ylabel("compras no mês")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=3, fontsize=8.5)
        return fig


def tempo_ate_a_recompra(curvas: dict[str, pd.DataFrame], tabela: pd.DataFrame) -> Figure:
    """Kaplan-Meier, mostrado como a parcela que já fez a segunda compra."""
    cores = [APAGADO, AZUL, REAL]
    with plt.rc_context(ESTILO):
        nomes = list(curvas)
        fig, ax = nova_figura(
            f"Quem aparece em dez/2009 volta em {numero(tabela.loc[nomes[0], 'semanas_medianas_ate_voltar'], 0)} semanas; "
            f"cliente novo de verdade leva {numero(tabela.loc[nomes[2], 'semanas_medianas_ate_voltar'], 0)}",
            "Parcela que já fez a segunda compra, por semanas desde a primeira (Kaplan-Meier, faixa de 95%). No título, a mediana de cada grupo.",
            altura=4.8,
        )
        fig.subplots_adjust(bottom=0.25, right=0.9)
        for (nome, curva), cor in zip(curvas.items(), cores):
            visivel = curva[curva["tempo"] <= 39]
            tempo = np.concatenate([[0], visivel["tempo"]])
            ax.fill_between(
                tempo, np.concatenate([[0], 1 - visivel["superior"]]), np.concatenate([[0], 1 - visivel["inferior"]]),
                step="post", color=cor, alpha=0.15, linewidth=0,
            )
            ax.step(tempo, np.concatenate([[0], 1 - visivel["sobrevivencia"]]), where="post", color=cor, label=f"{nome}: {milhar(tabela.loc[nome, 'clientes'])} clientes")
            _rotulo_no_fim(ax, 39, 1 - visivel["sobrevivencia"].iloc[-1], percentual(1 - visivel["sobrevivencia"].iloc[-1]))
        ax.axvline(26, color=EIXO, linewidth=1.0, zorder=1)
        ax.set_xlim(0, 39)
        ax.set_ylim(0, 1)
        ax.set_xticks([0, 4, 8, 13, 17, 21, 26, 30, 35, 39])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: percentual(v)))
        ax.set_xlabel("semanas desde a primeira compra")
        ax.set_ylabel("já voltou a comprar")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=1, fontsize=8.5)
        return fig


def retorno_por_silencio(tabela: pd.DataFrame) -> Figure:
    """Quem voltou em 26 semanas, por tempo de silêncio no corte: real contra o que o BG/NBD dizia."""
    with plt.rc_context(ESTILO):
        fig, eixos = plt.subplots(1, 2, figsize=(8.2, 4.5), dpi=160, sharey=True)
        fig.subplots_adjust(top=0.74, left=0.09, right=0.97, bottom=0.2, wspace=0.08)
        fig.text(0.02, 0.955, "Não existe o dia em que o cliente vai embora: a chance de volta só vai caindo", fontsize=13, fontweight="bold", color=TINTA, va="top")
        fig.text(
            0.02, 0.885, "Parcela que voltou a comprar nas 26 semanas seguintes ao corte, pelo tempo que o cliente estava calado. Barras: intervalo de 95%.",
            fontsize=9.5, color=TINTA_SECUNDARIA, va="top",
        )
        for ax, grupo in zip(eixos, ["Comprou uma vez", "Comprou duas vezes ou mais"]):
            recorte = tabela[tabela["grupo"] == grupo].reset_index(drop=True)
            x = np.arange(len(recorte))
            ax.plot(x, recorte["modelo_26"], "-o", color=AZUL, label="O que o BG/NBD previa", zorder=3)
            ax.vlines(x, recorte["voltou_26_inferior"], recorte["voltou_26_superior"], color=REAL, linewidth=2, zorder=4)
            ax.plot(x, recorte["voltou_26"], "o", color=REAL, label="Real", zorder=5)
            for i in (0, len(recorte) - 1):
                ax.annotate(percentual(recorte["voltou_26"].iloc[i]), (x[i], recorte["voltou_26"].iloc[i]), xytext=(9, -1), textcoords="offset points", va="center", fontsize=9, color=TINTA)
            ax.set_title(f"{grupo} ({milhar(recorte['clientes'].sum())} clientes)", fontsize=10, color=TINTA_SECUNDARIA, loc="left")
            ax.set_xticks(x, recorte["semanas_calado"], fontsize=8.5)
            ax.set_xlim(-0.4, len(recorte) - 0.4)
            ax.set_ylim(0, 1)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: percentual(v)))
            ax.set_xlabel("semanas calado no corte")
        eixos[0].set_ylabel("voltou em 26 semanas")
        eixos[1].legend(loc="upper right", fontsize=8.5)
        fig.patch.set_facecolor(SUPERFICIE)
        return fig
