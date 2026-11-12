"""Cada tabela do README e do notebook sai de uma função daqui.

Desenho: calibração de 1/12/2009 a 30/11/2010 (um ano), validação de 1/12/2010 a 30/11/2011 (o ano
seguinte). Nada do período de validação entra no ajuste, nem pela limpeza dos cancelamentos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from valor_cliente import avaliacao as av
from valor_cliente import bgnbd, dados
from valor_cliente import gamma_gamma as gg
from valor_cliente import linhas_de_base as lb
from valor_cliente import sobrevivencia as sv
from valor_cliente.bgnbd import ParametrosBGNBD
from valor_cliente.gamma_gamma import ParametrosGammaGamma

CORTE = pd.Timestamp("2010-11-30")
FIM_DA_VALIDACAO = pd.Timestamp("2011-11-30")
HORIZONTES_DO_CLIENTE_NOVO = (13, 26, 39)  # semanas depois da primeira compra
HORIZONTE_PRINCIPAL = 26
SEMENTE = 42
REPETICOES = 2000  # bootstrap das métricas de validação (reamostra clientes)
REPETICOES_DE_AJUSTE = 200  # bootstrap que reajusta os modelos (incerteza dos parâmetros)

LIMITES_DE_FREQUENCIA = [-1, 0, 1, 2, 4, 7, 15, np.inf]
ROTULOS_DE_FREQUENCIA = ["0", "1", "2", "3 a 4", "5 a 7", "8 a 15", "16 ou mais"]
LIMITES_DE_SILENCIO = [-1, 4, 13, 26, 39, np.inf]
ROTULOS_DE_SILENCIO = ["até 4", "5 a 13", "14 a 26", "27 a 39", "40 ou mais"]

MODELO = "BG/NBD + Gamma-Gamma"
TAXA = "Taxa histórica x ticket do cliente"
GASTO = "Gasto histórico total"
RFM = "RFM (M = gasto total)"
RFM_TICKET = "RFM (M = ticket médio)"
ACASO = "Média da base (não ordena)"
TETO = "Ordem perfeita (teto)"


def semanas_entre(inicio, fim) -> float:
    return (pd.Timestamp(fim) - pd.Timestamp(inicio)).days / dados.SEMANA


def ajustar_modelos(base: pd.DataFrame) -> tuple[ParametrosBGNBD, ParametrosGammaGamma]:
    """BG/NBD nas recompras e Gamma-Gamma no valor médio por compra (todas as compras da calibração)."""
    return (
        bgnbd.ajustar(base["x"], base["t_x"], base["T"]),
        gg.ajustar(base["compras"], base["valor_medio"]),
    )


def prever(base: pd.DataFrame, bg: ParametrosBGNBD, gama: ParametrosGammaGamma, horizonte: float) -> pd.DataFrame:
    """Previsão de cada método para cada cliente, só com o que se sabia no corte."""
    x, t_x, T = base["x"].to_numpy(float), base["t_x"].to_numpy(), base["T"].to_numpy()
    p = pd.DataFrame(index=base.index)
    p["compras_modelo"] = bgnbd.compras_esperadas_condicional(bg, horizonte, x, t_x, T)
    p["compras_taxa"] = lb.compras_pela_taxa_historica(x, T, horizonte)
    p["compras_media"] = lb.compras_pela_media_da_base(x, T, horizonte)
    p["ticket_modelo"] = gg.valor_esperado_condicional(gama, base["compras"], base["valor_medio"])
    p["receita_modelo"] = p["compras_modelo"] * p["ticket_modelo"]
    p["receita_taxa"] = p["compras_taxa"] * base["valor_medio"]
    p["receita_media"] = p["compras_media"] * base["valor_medio"].mean()
    p["gasto_historico"] = base["receita"]
    p["rfm"] = lb.pontuacao_rfm(base["dias_calado"], x, base["receita"])["RFM"].to_numpy()
    p["rfm_ticket"] = lb.pontuacao_rfm(base["dias_calado"], x, base["valor_medio"])["RFM"].to_numpy()
    p["p_vivo"] = bgnbd.probabilidade_vivo(bg, x, t_x, T)
    p["p_comprar"] = bgnbd.probabilidade_de_comprar(bg, horizonte, x, t_x, T)
    return p


def resumo_da_base(base: pd.DataFrame, horizonte: float) -> dict:
    receita_futura = base["receita_futura"].to_numpy()
    return {
        "corte": str(CORTE.date()),
        "fim_da_validacao": str(FIM_DA_VALIDACAO.date()),
        "semanas_de_validacao": round(horizonte, 1),
        "clientes": int(len(base)),
        "parcela_sem_recompra_na_calibracao": float((base["x"] == 0).mean()),
        "recompras_medias_na_calibracao": float(base["x"].mean()),
        "semanas_medias_de_historico": float(base["T"].mean()),
        "ticket_medio_por_compra": float(base["valor_medio"].mean()),
        "ticket_mediano_por_compra": float(base["valor_medio"].median()),
        "receita_na_calibracao": float(base["receita"].sum()),
        "compras_medias_na_validacao": float(base["compras_futuras"].mean()),
        "parcela_sem_compra_na_validacao": float((base["compras_futuras"] == 0).mean()),
        "receita_na_validacao": float(receita_futura.sum()),
        "parcela_da_receita_futura_nos_10_maiores": av.receita_capturada(receita_futura, receita_futura, 0.1),
    }


def parametros(bg: ParametrosBGNBD, gama: ParametrosGammaGamma, previsoes: pd.DataFrame) -> dict:
    """Parâmetros ajustados e o que eles dizem em linguagem de negócio."""
    vivo = previsoes["p_vivo"].to_numpy()
    return {
        "bgnbd": bg.como_dicionario(),
        "gamma_gamma": gama.como_dicionario(),
        "compras_por_semana_de_um_cliente_medio": bg.r / bg.alfa,
        "abandono_medio_por_recompra": bg.a / (bg.a + bg.b),
        "probabilidade_vivo": {
            "media": float(vivo.mean()),
            "minimo": float(vivo.min()),
            "percentil_1": float(np.quantile(vivo, 0.01)),
            "parcela_abaixo_de_90": float((vivo < 0.9).mean()),
        },
        "ticket_medio_da_base_pelo_modelo": gg.valor_medio_da_base(gama),
        "peso_da_base_com_1_compra": float(gg.peso_da_media_da_base(gama, 1)),
        "peso_da_base_com_5_compras": float(gg.peso_da_media_da_base(gama, 5)),
    }


# --------------------------------------------------------------------------------------
# Validação: quantas compras
# --------------------------------------------------------------------------------------

def erro_nas_compras(base: pd.DataFrame, previsoes: pd.DataFrame, indices: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """Erro por cliente e viés do total, com intervalo de 95% por bootstrap de clientes."""
    real = base["compras_futuras"].to_numpy(float)
    metodos = {"BG/NBD": "compras_modelo", "Taxa histórica do cliente": "compras_taxa", "Média da base": "compras_media"}
    linhas, reamostras = {}, {}
    for nome, coluna in metodos.items():
        previsto = previsoes[coluna].to_numpy()
        erro = previsto - real
        absoluto = np.abs(erro)[indices].mean(axis=1)
        quadratico = np.sqrt((erro**2)[indices].mean(axis=1))
        vies = previsto[indices].sum(axis=1) / real[indices].sum(axis=1) - 1.0
        reamostras[nome] = (absoluto, quadratico)
        pontual = av.erros_de_previsao(previsto, real)
        linhas[nome] = {
            "erro_absoluto_medio": pontual["erro_absoluto_medio"],
            "eam_inferior": av.intervalo(absoluto)[0], "eam_superior": av.intervalo(absoluto)[1],
            "raiz_do_erro_quadratico": pontual["raiz_do_erro_quadratico"],
            "req_inferior": av.intervalo(quadratico)[0], "req_superior": av.intervalo(quadratico)[1],
            "vies_do_total": pontual["vies_do_total"],
            "vies_inferior": av.intervalo(vies)[0], "vies_superior": av.intervalo(vies)[1],
            "total_previsto": float(previsto.sum()),
        }
    tabela = pd.DataFrame(linhas).T
    diferenca_absoluto = reamostras["BG/NBD"][0] - reamostras["Taxa histórica do cliente"][0]
    diferenca_quadratico = reamostras["BG/NBD"][1] - reamostras["Taxa histórica do cliente"][1]
    diferencas = {
        "total_real": float(real.sum()),
        "eam_modelo_menos_taxa": float(tabela.loc["BG/NBD", "erro_absoluto_medio"] - tabela.loc["Taxa histórica do cliente", "erro_absoluto_medio"]),
        "eam_modelo_menos_taxa_ic": list(av.intervalo(diferenca_absoluto)),
        "req_modelo_menos_taxa": float(tabela.loc["BG/NBD", "raiz_do_erro_quadratico"] - tabela.loc["Taxa histórica do cliente", "raiz_do_erro_quadratico"]),
        "req_modelo_menos_taxa_ic": list(av.intervalo(diferenca_quadratico)),
    }
    return tabela, diferencas


def faixa_de_frequencia(base: pd.DataFrame) -> pd.Series:
    return pd.cut(base["x"], LIMITES_DE_FREQUENCIA, labels=ROTULOS_DE_FREQUENCIA)


def calibracao_por_frequencia(base: pd.DataFrame, previsoes: pd.DataFrame) -> pd.DataFrame:
    """Compras médias previstas e reais na validação, por faixa de recompras na calibração."""
    tabela = av.calibracao_por_faixa(
        faixa_de_frequencia(base), base["compras_futuras"],
        {"modelo": previsoes["compras_modelo"], "taxa_historica": previsoes["compras_taxa"], "media_da_base": previsoes["compras_media"]},
    )
    tabela["modelo_sobre_real"] = tabela["modelo"] / tabela["real"]
    tabela.index = tabela.index.astype(str)
    return tabela


def acompanhamento_mensal(base: pd.DataFrame, bg: ParametrosBGNBD, compras_liquidas: pd.DataFrame) -> pd.DataFrame:
    """Compras previstas e reais dos clientes da calibração, mês a mês da validação.

    O previsto de cada mês é a diferença da esperança acumulada entre o fim do mês e o do anterior.
    A taxa histórica prevê o mesmo ritmo o ano todo.
    """
    x, t_x, T = base["x"].to_numpy(float), base["t_x"].to_numpy(), base["T"].to_numpy()
    futuras = compras_liquidas[
        (compras_liquidas["dia"] > CORTE) & (compras_liquidas["dia"] <= FIM_DA_VALIDACAO) & compras_liquidas["cliente"].isin(base["cliente"])
    ]
    reais = futuras.groupby(futuras["dia"].dt.to_period("M")).size()
    ritmo_semanal = lb.compras_pela_taxa_historica(x, T, 1.0).sum()
    linhas, acumulado, anterior = [], 0.0, CORTE
    for mes in pd.period_range(CORTE + pd.Timedelta(days=1), FIM_DA_VALIDACAO, freq="M"):
        fim_do_mes = min(mes.end_time.normalize(), FIM_DA_VALIDACAO)
        ate_aqui = float(bgnbd.compras_esperadas_condicional(bg, semanas_entre(CORTE, fim_do_mes), x, t_x, T).sum())
        linhas.append({
            "mes": str(mes), "real": int(reais.get(mes, 0)), "modelo": ate_aqui - acumulado,
            "taxa_historica": ritmo_semanal * semanas_entre(anterior, fim_do_mes),
        })
        acumulado, anterior = ate_aqui, fim_do_mes
    tabela = pd.DataFrame(linhas).set_index("mes")
    tabela["modelo_sobre_real"] = tabela["modelo"] / tabela["real"]
    return tabela


# --------------------------------------------------------------------------------------
# Validação: onde está a receita
# --------------------------------------------------------------------------------------

def _pontuacoes(base: pd.DataFrame, previsoes: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        MODELO: previsoes["receita_modelo"].to_numpy(),
        TAXA: previsoes["receita_taxa"].to_numpy(),
        GASTO: previsoes["gasto_historico"].to_numpy(),
        RFM: previsoes["rfm"].to_numpy(float),
        RFM_TICKET: previsoes["rfm_ticket"].to_numpy(float),
        ACASO: previsoes["receita_media"].to_numpy(),
        TETO: base["receita_futura"].to_numpy(),
    }


def captura_de_receita(base: pd.DataFrame, previsoes: pd.DataFrame, indices: np.ndarray) -> pd.DataFrame:
    """Parte da receita da validação que fica nos 10% e 20% de clientes que cada método põe no topo.

    Intervalos por bootstrap de clientes. A coluna de diferença compara cada método com o modelo na
    mesma reamostra (bootstrap pareado), que é o que diz se a distância entre os dois é ruído.
    """
    receita = base["receita_futura"].to_numpy()
    pontuacoes = _pontuacoes(base, previsoes)
    linhas = {nome: {} for nome in pontuacoes}
    for fracao, rotulo in ((0.1, "top10"), (0.2, "top20")):
        reamostras = {
            nome: av.bootstrap(lambda linha, p=pontuacao: av.receita_capturada(p[linha], receita[linha], fracao), indices)
            for nome, pontuacao in pontuacoes.items()
        }
        for nome, pontuacao in pontuacoes.items():
            diferenca = reamostras[nome] - reamostras[MODELO]
            pontual = av.receita_capturada(pontuacao, receita, fracao)
            linhas[nome].update({
                rotulo: pontual,
                f"{rotulo}_inferior": av.intervalo(reamostras[nome])[0],
                f"{rotulo}_superior": av.intervalo(reamostras[nome])[1],
                f"{rotulo}_menos_modelo": pontual - av.receita_capturada(pontuacoes[MODELO], receita, fracao),
                f"{rotulo}_menos_modelo_inferior": av.intervalo(diferenca)[0],
                f"{rotulo}_menos_modelo_superior": av.intervalo(diferenca)[1],
            })
    tabela = pd.DataFrame(linhas).T
    tabela["correlacao_de_postos"] = [float(stats.spearmanr(p, receita).statistic) if np.ptp(p) > 0 else 0.0 for p in pontuacoes.values()]
    return tabela


def curvas_de_captura(base: pd.DataFrame, previsoes: pd.DataFrame, pontos: int = 41) -> pd.DataFrame:
    """Curva de ganho: receita futura acumulada conforme se desce na lista ordenada por cada método."""
    receita = base["receita_futura"].to_numpy()
    fracoes = np.round(np.linspace(0.0, 1.0, pontos), 4)
    curvas = {nome: av.curva_de_captura(pontuacao, receita, fracoes) for nome, pontuacao in _pontuacoes(base, previsoes).items()}
    return pd.DataFrame(curvas, index=pd.Index(fracoes, name="fracao_dos_clientes"))


# --------------------------------------------------------------------------------------
# Valor por compra (Gamma-Gamma)
# --------------------------------------------------------------------------------------

def independencia_frequencia_valor(base: pd.DataFrame, repeticoes: int = 1000) -> dict:
    """A hipótese do Gamma-Gamma: quem compra mais vezes não gasta mais (nem menos) por compra."""
    compras, ticket = base["compras"].to_numpy(float), base["valor_medio"].to_numpy()
    indices = av.indices_de_bootstrap(len(base), repeticoes, SEMENTE + 1)
    postos = av.bootstrap(lambda linha: stats.spearmanr(compras[linha], ticket[linha]).statistic, indices)
    linear = av.bootstrap(lambda linha: np.corrcoef(compras[linha], ticket[linha])[0, 1], indices)
    faixa = pd.cut(base["compras"], [0, 1, 2, 5, 10, np.inf], labels=["1", "2", "3 a 5", "6 a 10", "11 ou mais"])
    por_faixa = base.groupby(faixa, observed=True)["valor_medio"].agg(clientes="size", ticket_mediano="median", ticket_medio="mean")
    por_faixa.index = por_faixa.index.astype(str)
    return {
        "correlacao_de_postos": float(stats.spearmanr(compras, ticket).statistic),
        "correlacao_de_postos_ic": list(av.intervalo(postos)),
        "correlacao_linear": float(np.corrcoef(compras, ticket)[0, 1]),
        "correlacao_linear_ic": list(av.intervalo(linear)),
        "ticket_por_faixa_de_compras": por_faixa,
    }


def erro_no_ticket(base: pd.DataFrame, previsoes: pd.DataFrame, repeticoes: int = REPETICOES) -> pd.DataFrame:
    """Entre quem voltou a comprar: erro ao prever o valor médio por compra na validação."""
    voltou = (base["compras_futuras"] > 0).to_numpy()
    real = (base["receita_futura"] / base["compras_futuras"].where(base["compras_futuras"] > 0))[voltou].to_numpy()
    candidatos = {
        "Gamma-Gamma": previsoes["ticket_modelo"].to_numpy()[voltou],
        "Média do próprio cliente": base["valor_medio"].to_numpy()[voltou],
        "Média da base": np.full(voltou.sum(), base["valor_medio"].mean()),
    }
    uma_compra = (base["compras"] == 1).to_numpy()[voltou]
    indices = av.indices_de_bootstrap(int(voltou.sum()), repeticoes, SEMENTE + 2)
    referencia = np.abs(candidatos["Média do próprio cliente"] - real)
    linhas = {}
    for nome, previsto in candidatos.items():
        erro = np.abs(previsto - real)
        diferenca = (erro - referencia)[indices].mean(axis=1)
        linhas[nome] = {
            "clientes": int(voltou.sum()),
            "erro_absoluto_medio": float(erro.mean()),
            "erro_absoluto_mediano": float(np.median(erro)),
            "eam_com_1_compra_no_historico": float(erro[uma_compra].mean()),
            "eam_com_2_ou_mais": float(erro[~uma_compra].mean()),
            "eam_menos_media_do_cliente": float((erro - referencia).mean()),
            "diferenca_inferior": av.intervalo(diferenca)[0],
            "diferenca_superior": av.intervalo(diferenca)[1],
        }
    return pd.DataFrame(linhas).T


# --------------------------------------------------------------------------------------
# Incerteza dos parâmetros
# --------------------------------------------------------------------------------------

def reajustes_por_bootstrap(base: pd.DataFrame, bg: ParametrosBGNBD, gama: ParametrosGammaGamma, repeticoes: int = REPETICOES_DE_AJUSTE) -> pd.DataFrame:
    """Reajusta os dois modelos em reamostras de clientes: é de onde sai a incerteza dos parâmetros.

    Sortear clientes com reposição equivale a dar a cada um um peso inteiro (quantas vezes saiu).
    """
    gerador = np.random.default_rng(SEMENTE + 3)
    n = len(base)
    linhas = []
    for _ in range(repeticoes):
        pesos = np.bincount(gerador.integers(0, n, n), minlength=n).astype(float)
        b = bgnbd.ajustar(base["x"], base["t_x"], base["T"], pesos=pesos, inicio=bg)
        g = gg.ajustar(base["compras"], base["valor_medio"], pesos=pesos, inicio=gama)
        linhas.append({"r": b.r, "alfa": b.alfa, "a": b.a, "b": b.b, "p": g.p, "q": g.q, "gama": g.gama})
    return pd.DataFrame(linhas)


def _bg(linha) -> ParametrosBGNBD:
    return ParametrosBGNBD(linha.r, linha.alfa, linha.a, linha.b)


def _gg(linha) -> ParametrosGammaGamma:
    return ParametrosGammaGamma(linha.p, linha.q, linha.gama)


# --------------------------------------------------------------------------------------
# Quanto vale um cliente novo
# --------------------------------------------------------------------------------------

def trajetoria_depois_da_primeira_compra(compras_liquidas: pd.DataFrame, primeira: pd.Series, semanas: int) -> tuple[np.ndarray, np.ndarray]:
    """Recompras e receita de recompra acumuladas, semana a semana, de cada cliente de `primeira`.

    `primeira` é a data da primeira compra de cada cliente (índice = cliente). Devolve duas matrizes
    (clientes x semanas + 1); a coluna w é o acumulado até w semanas depois da primeira compra.
    """
    compras = compras_liquidas[compras_liquidas["cliente"].isin(primeira.index)]
    dias = (compras["dia"] - compras["cliente"].map(primeira)).dt.days.to_numpy()
    dentro = (dias > 0) & (dias <= 7 * semanas)
    posicao = primeira.index.get_indexer(compras["cliente"].to_numpy()[dentro])
    semana = np.ceil(dias[dentro] / 7).astype(int)
    quantas = np.zeros((len(primeira), semanas + 1))
    receita = np.zeros((len(primeira), semanas + 1))
    np.add.at(quantas, (posicao, semana), 1.0)
    np.add.at(receita, (posicao, semana), compras["receita"].to_numpy()[dentro])
    return quantas.cumsum(axis=1), receita.cumsum(axis=1)


def _media_com_intervalo(valores: np.ndarray, semente: int, repeticoes: int = REPETICOES) -> tuple[float, float, float]:
    indices = av.indices_de_bootstrap(len(valores), repeticoes, semente)
    inferior, superior = av.intervalo(valores[indices].mean(axis=1))
    return float(valores.mean()), inferior, superior


def valor_do_cliente_novo(
    compras: pd.DataFrame, cancelamentos: pd.DataFrame, base: pd.DataFrame,
    bg: ParametrosBGNBD, gama: ParametrosGammaGamma, reajustes: pd.DataFrame,
) -> dict:
    """Recompras e receita de recompra de um cliente novo: o que cada método prevê e o que aconteceu.

    Previsões (só com a calibração):
    - modelo: E[recompras em t] do BG/NBD para quem acabou de chegar, vezes o ticket médio da base
      pelo Gamma-Gamma; intervalo pelos reajustes em bootstrap (incerteza dos parâmetros);
    - média da base: recompras por cliente-semana da base inteira, vezes t, vezes o ticket médio;
    - coortes antigas: o que os clientes que já tinham t semanas de casa fizeram nas primeiras t semanas.
    Realidade: clientes cuja primeira compra na base aconteceu depois do corte (já havia pelo menos um
    ano de histórico sem eles) e que puderam ser acompanhados por t semanas.
    Diagnóstico (feito depois de ver o erro): as mesmas contas sem os clientes que aparecem no primeiro
    mês da base, que são em boa parte clientes antigos cuja primeira compra real é anterior aos dados.
    """
    tudo = dados.compras_conhecidas_em(compras, cancelamentos, pd.Timestamp.max)
    calibracao = dados.compras_conhecidas_em(compras, cancelamentos, CORTE)
    fim_dos_dados = compras["dia"].max()
    primeira_geral = tudo.groupby("cliente")["dia"].min()
    primeira_na_calibracao = calibracao.groupby("cliente")["dia"].min()
    fim_do_primeiro_mes = primeira_na_calibracao.min() + pd.offsets.MonthEnd(0)

    sem_primeiro_mes = base[base["primeira_compra"] > fim_do_primeiro_mes]
    bg_diagnostico, gama_diagnostico = ajustar_modelos(sem_primeiro_mes)
    ritmo_da_base = base["x"].sum() / base["T"].sum()
    ticket_da_base = float(base["valor_medio"].mean())
    ticket_do_modelo = gg.valor_medio_da_base(gama)
    tickets_reajustados = np.array([gg.valor_medio_da_base(_gg(linha)) for linha in reajustes.itertuples()])

    linhas, curvas = {}, {}
    for semanas in HORIZONTES_DO_CLIENTE_NOVO:
        prazo = pd.Timedelta(weeks=semanas)
        novos = primeira_geral[(primeira_geral > CORTE) & (primeira_geral <= fim_dos_dados - prazo)]
        quantas, receita = trajetoria_depois_da_primeira_compra(tudo, novos, semanas)
        antigos = primeira_na_calibracao[primeira_na_calibracao <= CORTE - prazo]
        quantas_antigos, receita_antigos = trajetoria_depois_da_primeira_compra(calibracao, antigos, semanas)
        depois_do_primeiro_mes = (antigos > fim_do_primeiro_mes).to_numpy()

        esperadas = float(bgnbd.compras_esperadas_cliente_novo(bg, semanas))
        esperadas_reajustes = np.array([float(bgnbd.compras_esperadas_cliente_novo(_bg(l), semanas)) for l in reajustes.itertuples()])
        esperadas_diagnostico = float(bgnbd.compras_esperadas_cliente_novo(bg_diagnostico, semanas))
        primeira_compra = tudo.merge(novos.rename("dia").reset_index(), on=["cliente", "dia"])["receita"]
        real_recompras = _media_com_intervalo(quantas[:, -1], SEMENTE + 10 + semanas)
        real_receita = _media_com_intervalo(receita[:, -1], SEMENTE + 20 + semanas)
        linhas[f"{semanas} semanas"] = {
            "clientes_novos_acompanhados": int(len(novos)),
            "real_recompras": real_recompras[0], "real_recompras_inferior": real_recompras[1], "real_recompras_superior": real_recompras[2],
            "real_receita": real_receita[0], "real_receita_inferior": real_receita[1], "real_receita_superior": real_receita[2],
            "real_parcela_sem_recompra": float((quantas[:, -1] == 0).mean()),
            "real_receita_mediana": float(np.median(receita[:, -1])),
            "real_valor_da_primeira_compra": float(primeira_compra.mean()),
            "modelo_recompras": esperadas,
            "modelo_recompras_inferior": av.intervalo(esperadas_reajustes)[0], "modelo_recompras_superior": av.intervalo(esperadas_reajustes)[1],
            "modelo_receita": esperadas * ticket_do_modelo,
            "modelo_receita_inferior": av.intervalo(esperadas_reajustes * tickets_reajustados)[0],
            "modelo_receita_superior": av.intervalo(esperadas_reajustes * tickets_reajustados)[1],
            "modelo_sobre_real": esperadas * ticket_do_modelo / real_receita[0],
            "media_da_base_recompras": float(ritmo_da_base * semanas),
            "media_da_base_receita": float(ritmo_da_base * semanas * ticket_da_base),
            "coortes_antigas_clientes": int(len(antigos)),
            "coortes_antigas_recompras": float(quantas_antigos[:, -1].mean()),
            "coortes_antigas_receita": float(receita_antigos[:, -1].mean()),
            "diagnostico_modelo_recompras": esperadas_diagnostico,
            "diagnostico_modelo_receita": esperadas_diagnostico * gg.valor_medio_da_base(gama_diagnostico),
            "diagnostico_coortes_clientes": int(depois_do_primeiro_mes.sum()),
            "diagnostico_coortes_recompras": float(quantas_antigos[depois_do_primeiro_mes, -1].mean()),
            "diagnostico_coortes_receita": float(receita_antigos[depois_do_primeiro_mes, -1].mean()),
        }
        if semanas == HORIZONTE_PRINCIPAL:
            eixo = np.arange(semanas + 1)
            indices = av.indices_de_bootstrap(len(novos), REPETICOES, SEMENTE + 30)
            medias = np.stack([receita[linha].mean(axis=0) for linha in indices])
            curva_reajustes = np.stack([
                bgnbd.compras_esperadas_cliente_novo(_bg(l), eixo) * gg.valor_medio_da_base(_gg(l)) for l in reajustes.itertuples()
            ])
            curvas = pd.DataFrame({
                "real": receita.mean(axis=0),
                "real_inferior": np.quantile(medias, 0.025, axis=0),
                "real_superior": np.quantile(medias, 0.975, axis=0),
                "modelo": bgnbd.compras_esperadas_cliente_novo(bg, eixo) * ticket_do_modelo,
                "modelo_inferior": np.quantile(curva_reajustes, 0.025, axis=0),
                "modelo_superior": np.quantile(curva_reajustes, 0.975, axis=0),
                "media_da_base": ritmo_da_base * eixo * ticket_da_base,
                "coortes_antigas": receita_antigos.mean(axis=0),
                "diagnostico_modelo": bgnbd.compras_esperadas_cliente_novo(bg_diagnostico, eixo) * gg.valor_medio_da_base(gama_diagnostico),
            }, index=pd.Index(eixo, name="semanas_desde_a_primeira_compra"))
            distribuicao = _distribuicao_do_cliente_novo(bg, gama, semanas, receita[:, -1])

    return {
        "tabela": pd.DataFrame(linhas).T,
        "curvas": curvas,
        "distribuicao": distribuicao,
        "fim_do_primeiro_mes": str(fim_do_primeiro_mes.date()),
        "clientes_do_primeiro_mes": int(len(base) - len(sem_primeiro_mes)),
        "novos_por_mes_depois_do_primeiro": float(
            sem_primeiro_mes.groupby(sem_primeiro_mes["primeira_compra"].dt.to_period("M")).size().mean()
        ),
        "novos_por_mes_na_validacao": float(
            primeira_geral[(primeira_geral > CORTE) & (primeira_geral <= FIM_DA_VALIDACAO)].dt.to_period("M").value_counts().mean()
        ),
        "diagnostico_bgnbd": bg_diagnostico.como_dicionario(),
    }


def _distribuicao_do_cliente_novo(bg: ParametrosBGNBD, gama: ParametrosGammaGamma, semanas: int, real: np.ndarray) -> pd.DataFrame:
    """O valor de UM cliente novo varia muito: distribuição simulada pelo modelo e distribuição real."""
    gerador = np.random.default_rng(SEMENTE + 4)
    n = 200_000
    recompras = bgnbd.simular(bg, np.zeros(n), float(semanas), gerador)["compras_futuras"]
    nu = gerador.gamma(gama.q, 1.0 / gama.gama, n)
    simulada = np.where(recompras > 0, gerador.gamma(gama.p * np.maximum(recompras, 1.0), 1.0 / nu), 0.0)

    def resumo(valores: np.ndarray) -> dict:
        return {
            "parcela_sem_recompra": float((valores == 0).mean()),
            "mediana": float(np.median(valores)),
            "percentil_75": float(np.quantile(valores, 0.75)),
            "percentil_90": float(np.quantile(valores, 0.90)),
            "percentil_99": float(np.quantile(valores, 0.99)),
            "media": float(valores.mean()),
        }

    return pd.DataFrame({"modelo (simulado)": resumo(simulada), "real (novos da validação)": resumo(real)}).T


# --------------------------------------------------------------------------------------
# Sobrevivência: tempo até a recompra
# --------------------------------------------------------------------------------------

def tempo_ate_a_recompra(compras_liquidas: pd.DataFrame, censura) -> pd.DataFrame:
    """Para cada cliente: semanas da primeira à segunda compra, ou até a censura se ainda não voltou."""
    ordenadas = compras_liquidas.sort_values(["cliente", "dia"])
    ordem = ordenadas.groupby("cliente").cumcount()
    primeira = ordenadas[ordem == 0].set_index("cliente")["dia"]
    segunda = ordenadas[ordem == 1].set_index("cliente")["dia"].reindex(primeira.index)
    fim = segunda.fillna(pd.Timestamp(censura))
    return pd.DataFrame({
        "primeira_compra": primeira,
        "semanas": (fim - primeira).dt.days / dados.SEMANA,
        "voltou": segunda.notna(),
    })


def curvas_de_sobrevivencia(compras: pd.DataFrame, cancelamentos: pd.DataFrame, repeticoes: int = 500) -> dict:
    """Kaplan-Meier do tempo até a segunda compra, em três grupos.

    Dois vistos no corte (só calibração): quem aparece no primeiro mês da base e quem aparece depois.
    Um visto no fim dos dados: os clientes novos da validação. A censura é o fim do que se observou.
    """
    calibracao = tempo_ate_a_recompra(dados.compras_conhecidas_em(compras, cancelamentos, CORTE), CORTE)
    fim_do_primeiro_mes = calibracao["primeira_compra"].min() + pd.offsets.MonthEnd(0)
    geral = tempo_ate_a_recompra(dados.compras_conhecidas_em(compras, cancelamentos, pd.Timestamp.max), compras["dia"].max())
    grupos = {
        "Primeira compra em dez/2009 (visto no corte)": calibracao[calibracao["primeira_compra"] <= fim_do_primeiro_mes],
        "Primeira compra de jan a nov/2010 (visto no corte)": calibracao[calibracao["primeira_compra"] > fim_do_primeiro_mes],
        "Clientes novos da validação (dez/2010 em diante)": geral[geral["primeira_compra"] > CORTE],
    }
    curvas, linhas, voltar = {}, {}, {}
    silencios = [0, 4, 13]
    for semente, (nome, grupo) in enumerate(grupos.items()):
        duracao, voltou = grupo["semanas"].to_numpy(), grupo["voltou"].to_numpy()
        curva = sv.kaplan_meier(duracao, voltou)
        curvas[nome] = curva
        linhas[nome] = {"clientes": int(len(grupo)), "voltaram": int(voltou.sum()), "semanas_medianas_ate_voltar": sv.tempo_mediano(curva)}
        for semanas in (13, 26):
            linhas[nome].update({
                f"voltou_em_{semanas}": float(1 - sv.sobrevivencia_em(curva, semanas)[0]),
                f"voltou_em_{semanas}_inferior": float(1 - sv.sobrevivencia_em(curva, semanas, "superior")[0]),
                f"voltou_em_{semanas}_superior": float(1 - sv.sobrevivencia_em(curva, semanas, "inferior")[0]),
            })
        indices = av.indices_de_bootstrap(len(grupo), repeticoes, SEMENTE + 40 + semente)
        reamostras = np.stack([
            sv.chance_de_voltar(sv.kaplan_meier(duracao[linha], voltou[linha]), silencios, HORIZONTE_PRINCIPAL) for linha in indices
        ])
        pontual = sv.chance_de_voltar(curva, silencios, HORIZONTE_PRINCIPAL)
        voltar[nome] = {
            f"calado há {s} semanas": {
                "chance_de_voltar_em_26_semanas": float(pontual[i]),
                "inferior": float(np.quantile(reamostras[:, i], 0.025)),
                "superior": float(np.quantile(reamostras[:, i], 0.975)),
            }
            for i, s in enumerate(silencios)
        }
    return {"curvas": curvas, "tabela": pd.DataFrame(linhas).T, "chance_de_voltar": voltar}


def retorno_por_silencio(base: pd.DataFrame, bg: ParametrosBGNBD, compras_liquidas: pd.DataFrame) -> pd.DataFrame:
    """Dos clientes calados há tanto tempo no corte, quantos voltaram a comprar em 26 e em 52 semanas.

    É a conferência direta, no período de validação, de "quando dá para considerar que foi embora",
    ao lado da probabilidade de compra em 26 semanas que o BG/NBD dava a cada grupo.
    """
    futuras = compras_liquidas[(compras_liquidas["dia"] > CORTE) & (compras_liquidas["dia"] <= FIM_DA_VALIDACAO)]
    ate_26 = set(futuras.loc[futuras["dia"] <= CORTE + pd.Timedelta(weeks=26), "cliente"])
    ate_o_fim = set(futuras["cliente"])
    quadro = pd.DataFrame({
        "grupo": np.where(base["x"] == 0, "Comprou uma vez", "Comprou duas vezes ou mais"),
        "silencio": pd.cut(base["dias_calado"] / dados.SEMANA, LIMITES_DE_SILENCIO, labels=ROTULOS_DE_SILENCIO),
        "voltou_26": base["cliente"].isin(ate_26).to_numpy(),
        "voltou_52": base["cliente"].isin(ate_o_fim).to_numpy(),
        "modelo_26": bgnbd.probabilidade_de_comprar(bg, 26.0, base["x"], base["t_x"], base["T"]),
    })
    linhas = []
    for (grupo, silencio), recorte in quadro.groupby(["grupo", "silencio"], observed=True, sort=True):
        n = len(recorte)
        linha = {"grupo": grupo, "semanas_calado": str(silencio), "clientes": n, "modelo_26": float(recorte["modelo_26"].mean())}
        for coluna in ("voltou_26", "voltou_52"):
            inferior, superior = av.intervalo_de_wilson(int(recorte[coluna].sum()), n)
            linha.update({coluna: float(recorte[coluna].mean()), f"{coluna}_inferior": inferior, f"{coluna}_superior": superior})
        linhas.append(linha)
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------------------
# Sensibilidade ao corte
# --------------------------------------------------------------------------------------

CORTES_ALTERNATIVOS = [
    ("2010-08-31", "2011-08-31"),
    ("2010-11-30", "2011-11-30"),
    ("2010-12-31", "2011-11-30"),
    ("2011-02-28", "2011-11-30"),
    ("2011-05-31", "2011-11-30"),
]


def sensibilidade_ao_corte(compras: pd.DataFrame, cancelamentos: pd.DataFrame, repeticoes: int = 500) -> pd.DataFrame:
    """Refaz ajuste e validação com outros cortes: o achado depende de quanto histórico o modelo vê?"""
    inicio = compras["dia"].min()
    linhas = {}
    for i, (corte, fim) in enumerate(CORTES_ALTERNATIVOS):
        base = dados.montar_base(compras, cancelamentos, corte, fim)
        horizonte = semanas_entre(corte, fim)
        bg, gama = ajustar_modelos(base)
        p = prever(base, bg, gama, horizonte)
        real, receita = base["compras_futuras"].to_numpy(float), base["receita_futura"].to_numpy()
        indices = av.indices_de_bootstrap(len(base), repeticoes, SEMENTE + 50 + i)
        modelo = p["compras_modelo"].to_numpy()
        vies = modelo[indices].sum(axis=1) / real[indices].sum(axis=1) - 1.0
        diferenca = av.bootstrap(
            lambda l: av.receita_capturada(p["receita_modelo"].to_numpy()[l], receita[l], 0.1)
            - av.receita_capturada(p["gasto_historico"].to_numpy()[l], receita[l], 0.1),
            indices,
        )
        linhas[f"{corte} → {fim}"] = {
            "semanas_de_calibracao": round(semanas_entre(inicio, corte), 0),
            "semanas_de_validacao": round(horizonte, 0),
            "clientes": int(len(base)),
            "abandono_medio_por_recompra": bg.a / (bg.a + bg.b),
            "probabilidade_vivo_media": float(p["p_vivo"].mean()),
            "vies_modelo": float(modelo.sum() / real.sum() - 1.0),
            "vies_modelo_inferior": av.intervalo(vies)[0], "vies_modelo_superior": av.intervalo(vies)[1],
            "vies_taxa_historica": float(p["compras_taxa"].sum() / real.sum() - 1.0),
            "eam_modelo": av.erros_de_previsao(modelo, real)["erro_absoluto_medio"],
            "eam_taxa_historica": av.erros_de_previsao(p["compras_taxa"], real)["erro_absoluto_medio"],
            "top10_modelo": av.receita_capturada(p["receita_modelo"], receita, 0.1),
            "top10_gasto_historico": av.receita_capturada(p["gasto_historico"], receita, 0.1),
            "top10_rfm": av.receita_capturada(p["rfm"], receita, 0.1),
            "top10_modelo_menos_gasto_inferior": av.intervalo(diferenca)[0],
            "top10_modelo_menos_gasto_superior": av.intervalo(diferenca)[1],
        }
    return pd.DataFrame(linhas).T
