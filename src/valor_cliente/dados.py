"""Dados: baixa a base Online Retail II, converte, limpa e monta o resumo por cliente.

Fonte: Chen, D. (2019). Online Retail II. UCI Machine Learning Repository, id 502.
https://doi.org/10.24432/C5CG6D · licença CC BY 4.0.

O bruto (45 MB zipado) fica em `data/brutos/`, fora do git. O que é versionado é um extrato
agregado por cliente e dia (`data/compras_por_dia.csv`) mais a lista de compras canceladas
depois (`data/cancelamentos_casados.csv`) e o relatório da limpeza (`data/limpeza.json`).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
AGENTE = "portfolio-estudos/1.0"
SHA256_DO_ZIP = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"
TAMANHO_MINIMO_DO_ZIP = 40_000_000

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "data"
PASTA_BRUTOS = PASTA_DADOS / "brutos"
ARQUIVO_ZIP = PASTA_BRUTOS / "online_retail_ii.zip"
ARQUIVO_XLSX = PASTA_BRUTOS / "online_retail_II.xlsx"
ARQUIVO_PARQUET = PASTA_BRUTOS / "transacoes.parquet"
ARQUIVO_COMPRAS = PASTA_DADOS / "compras_por_dia.csv"
ARQUIVO_CANCELAMENTOS = PASTA_DADOS / "cancelamentos_casados.csv"
ARQUIVO_LIMPEZA = PASTA_DADOS / "limpeza.json"

SEMANA = 7.0  # a unidade de tempo dos modelos é a semana


# --------------------------------------------------------------------------------------
# Download e conversão (rodam uma vez, por scripts/baixar_dados.py)
# --------------------------------------------------------------------------------------

def sha256_do_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def baixar(destino: Path = ARQUIVO_ZIP) -> Path:
    """Baixa o zip da UCI (se ainda não existir) e confere tamanho e hash."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists():
        pedido = urllib.request.Request(URL, headers={"User-Agent": AGENTE})
        parcial = destino.with_suffix(".parcial")
        try:
            with urllib.request.urlopen(pedido, timeout=120) as resposta, parcial.open("wb") as saida:
                for bloco in iter(lambda: resposta.read(1 << 20), b""):
                    saida.write(bloco)
            parcial.replace(destino)
        finally:
            parcial.unlink(missing_ok=True)
    tamanho = destino.stat().st_size
    if tamanho < TAMANHO_MINIMO_DO_ZIP:
        raise RuntimeError(f"Download incompleto: {tamanho} bytes em {destino}")
    resumo = sha256_do_arquivo(destino)
    if resumo != SHA256_DO_ZIP:
        raise RuntimeError(f"O zip mudou na origem: sha256 {resumo}, esperado {SHA256_DO_ZIP}")
    return destino


def converter_para_parquet(arquivo_zip: Path = ARQUIVO_ZIP, destino: Path = ARQUIVO_PARQUET) -> Path:
    """Lê as duas abas do .xlsx em fluxo (pouca memória) e grava um parquet só."""
    import openpyxl
    import pyarrow as pa
    import pyarrow.parquet as pq

    with zipfile.ZipFile(arquivo_zip) as pacote:
        membros = [m for m in pacote.namelist() if m.lower().endswith(".xlsx")]
        if len(membros) != 1:
            raise RuntimeError(f"Esperava um .xlsx no zip, achei {membros}")
        with pacote.open(membros[0]) as origem, ARQUIVO_XLSX.open("wb") as saida:  # nome fixo: não confia no nome do zip
            for bloco in iter(lambda: origem.read(1 << 20), b""):
                saida.write(bloco)

    esquema = pa.schema([
        ("aba", pa.string()), ("fatura", pa.string()), ("codigo_item", pa.string()), ("descricao", pa.string()),
        ("quantidade", pa.int64()), ("data", pa.timestamp("s")), ("preco", pa.float64()),
        ("cliente", pa.int64()), ("pais", pa.string()),
    ])
    planilha = openpyxl.load_workbook(ARQUIVO_XLSX, read_only=True)
    try:
        with pq.ParquetWriter(destino, esquema, compression="zstd") as escritor:
            for aba in planilha.worksheets:
                linhas = aba.iter_rows(values_only=True)
                cabecalho = [str(c).strip() for c in next(linhas)]
                esperado = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
                if cabecalho != esperado:
                    raise RuntimeError(f"Cabeçalho inesperado na aba {aba.title}: {cabecalho}")
                bloco: list[tuple] = []
                for linha in linhas:
                    bloco.append(linha)
                    if len(bloco) >= 100_000:
                        escritor.write_table(_tabela(bloco, aba.title, esquema))
                        bloco = []
                if bloco:
                    escritor.write_table(_tabela(bloco, aba.title, esquema))
    finally:
        planilha.close()
    ARQUIVO_XLSX.unlink(missing_ok=True)  # o parquet substitui o .xlsx extraído
    return destino


def _tabela(bloco: list[tuple], aba: str, esquema):
    import pyarrow as pa

    fatura, item, descricao, quantidade, data, preco, cliente, pais = zip(*bloco)
    return pa.table(
        {
            "aba": [aba] * len(bloco),
            "fatura": [None if v is None else str(v) for v in fatura],
            "codigo_item": [None if v is None else str(v) for v in item],
            "descricao": [None if v is None else str(v) for v in descricao],
            "quantidade": [None if v is None else int(v) for v in quantidade],
            "data": list(data),
            "preco": [None if v is None else float(v) for v in preco],
            "cliente": [None if v is None else int(v) for v in cliente],
            "pais": [None if v is None else str(v) for v in pais],
        },
        schema=esquema,
    )


# --------------------------------------------------------------------------------------
# Limpeza e extrato versionado
# --------------------------------------------------------------------------------------

def limpar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Do bruto (uma linha por item de fatura) ao extrato por cliente e dia.

    Devolve (compras por cliente e dia, compras canceladas depois, relatório com a contagem de cada passo).
    Passos, na ordem:
    1. as duas abas do .xlsx repetem 1 a 9 de dezembro de 2010: fica a versão da segunda aba;
    2. saem as linhas sem código de cliente (não dá para acompanhar ninguém);
    3. as faturas de cancelamento (começam com "C") saem das compras e são guardadas para o passo 7;
    4. saem as outras faturas que não são venda (prefixo "A", ajuste de dívida);
    5. saem quantidade ou preço não positivos;
    6. saem os itens que não são produto: código que não começa com cinco dígitos
       (frete, taxas, ajuste manual, desconto, amostra, vale-presente, códigos internos);
    7. cada cancelamento é casado com a compra que ele desfaz (mesmo cliente, item, quantidade e preço,
       compra anterior ao cancelamento; ou, para estorno lançado como "Manual", mesmo cliente e mesmo valor).
       A compra casada não é apagada aqui: vai para uma tabela à parte com a data do cancelamento, para
       que a análise só a desconte quando o cancelamento já era conhecido (sem informação do futuro).
    Devolução parcial (quantidade diferente da compra) não casa e fica como receita bruta.
    """
    relatorio: dict = {"linhas_brutas": int(len(bruto))}
    dados = bruto.copy()
    dados["dia"] = dados["data"].dt.normalize()

    abas = sorted(dados["aba"].unique())
    if len(abas) > 1:
        inicio_da_segunda = dados.loc[dados["aba"] == abas[-1], "data"].min()
        repetidas = (dados["aba"] == abas[0]) & (dados["data"] >= inicio_da_segunda)
    else:
        repetidas = pd.Series(False, index=dados.index)
    relatorio["linhas_repetidas_entre_abas"] = int(repetidas.sum())
    dados = dados[~repetidas]

    sem_cliente = dados["cliente"].isna()
    relatorio["linhas_sem_cliente"] = int(sem_cliente.sum())
    dados = dados[~sem_cliente].copy()
    dados["cliente"] = dados["cliente"].astype("int64")
    dados["valor"] = dados["quantidade"] * dados["preco"]

    cancelamento = dados["fatura"].str.startswith("C")
    relatorio["linhas_de_cancelamento"] = int(cancelamento.sum())
    relatorio["valor_dos_cancelamentos"] = float(-dados.loc[cancelamento, "valor"].sum())
    cancelamentos = dados[cancelamento]
    relatorio["valor_dos_cancelamentos_de_itens_nao_produto"] = float(
        -cancelamentos.loc[~cancelamentos["codigo_item"].str.match(r"\d{5}"), "valor"].sum()
    )
    compras = dados[~cancelamento]

    outra_fatura = ~compras["fatura"].str.fullmatch(r"\d+")
    relatorio["linhas_de_outras_faturas_nao_venda"] = int(outra_fatura.sum())
    compras = compras[~outra_fatura]

    nao_positivo = (compras["quantidade"] <= 0) | (compras["preco"] <= 0)
    relatorio["linhas_com_quantidade_ou_preco_nao_positivo"] = int(nao_positivo.sum())
    compras = compras[~nao_positivo]

    nao_produto = ~compras["codigo_item"].str.match(r"\d{5}")
    relatorio["linhas_de_itens_nao_produto"] = int(nao_produto.sum())
    relatorio["valor_dos_itens_nao_produto"] = float(compras.loc[nao_produto, "valor"].sum())
    compras = compras[~nao_produto]
    relatorio["linhas_de_compra_validas"] = int(len(compras))
    relatorio["receita_bruta"] = float(compras["valor"].sum())

    casadas = _casar_cancelamentos(compras, cancelamentos)
    relatorio["linhas_de_compra_canceladas_depois"] = int(len(casadas))
    relatorio["valor_das_compras_canceladas_depois"] = float(casadas["valor"].sum())

    por_dia = (
        compras.groupby(["cliente", "dia"], as_index=False)
        .agg(receita=("valor", "sum"), faturas=("fatura", "nunique"))
        .sort_values(["cliente", "dia"], ignore_index=True)
    )
    por_dia["receita"] = por_dia["receita"].round(2)
    canceladas = (
        casadas.groupby(["cliente", "dia", "dia_do_cancelamento"], as_index=False)["valor"].sum()
        .sort_values(["cliente", "dia", "dia_do_cancelamento"], ignore_index=True)
    )
    canceladas["valor"] = canceladas["valor"].round(2)

    relatorio = {chave: round(valor, 2) if isinstance(valor, float) else valor for chave, valor in relatorio.items()}
    relatorio.update({
        "clientes": int(por_dia["cliente"].nunique()),
        "dias_de_compra": int(len(por_dia)),
        "primeiro_dia": str(por_dia["dia"].min().date()),
        "ultimo_dia": str(por_dia["dia"].max().date()),
    })
    return por_dia, canceladas, relatorio


def _casar_cancelamentos(compras: pd.DataFrame, cancelamentos: pd.DataFrame) -> pd.DataFrame:
    """Para cada linha de cancelamento, acha a compra mais recente, ainda não casada, que ela desfaz."""
    compras = compras.assign(linha=np.arange(len(compras)), valor_abs=compras["valor"].round(2))
    cancelamentos = cancelamentos.assign(quantidade=-cancelamentos["quantidade"], valor_abs=(-cancelamentos["valor"]).round(2))
    cancelamentos = cancelamentos[cancelamentos["quantidade"] > 0].sort_values("data")
    pares: list[tuple[int, pd.Timestamp]] = []  # (linha da compra, dia do cancelamento)

    sem_par = _casar_por_chave(compras, cancelamentos, ["cliente", "codigo_item", "quantidade", "preco"], pares)
    # estorno lançado como "Manual": não repete o código do item, então casa pelo valor exato
    manuais = sem_par[sem_par["codigo_item"].str.upper() == "M"]
    ja_casadas = {linha for linha, _ in pares}
    _casar_por_chave(compras[~compras["linha"].isin(ja_casadas)], manuais, ["cliente", "valor_abs"], pares)

    tabela = pd.DataFrame(pares, columns=["linha", "dia_do_cancelamento"])
    tabela["dia_do_cancelamento"] = pd.to_datetime(tabela["dia_do_cancelamento"])
    return compras.merge(tabela, on="linha")[["cliente", "dia", "dia_do_cancelamento", "valor"]]


def _casar_por_chave(compras: pd.DataFrame, cancelamentos: pd.DataFrame, chave: list[str], pares: list) -> pd.DataFrame:
    """Casa em ordem de data; acrescenta os pares a `pares` e devolve os cancelamentos que ficaram sem compra."""
    if cancelamentos.empty:
        return cancelamentos
    candidatas = compras.merge(cancelamentos[chave].drop_duplicates(), on=chave).sort_values("data")
    filas = {k: list(zip(grupo["data"], grupo["linha"])) for k, grupo in candidatas.groupby(chave)}
    casou = []
    for cancelamento in cancelamentos.itertuples(index=False):
        fila = filas.get(tuple(getattr(cancelamento, coluna) for coluna in chave), [])
        # a compra mais recente que seja anterior (ou simultânea) ao cancelamento
        posicao = next((i for i in range(len(fila) - 1, -1, -1) if fila[i][0] <= cancelamento.data), None)
        casou.append(posicao is not None)
        if posicao is not None:
            pares.append((fila.pop(posicao)[1], cancelamento.dia))
    return cancelamentos[~np.array(casou, dtype=bool)]


def gerar_extrato() -> dict:
    """Lê o parquet bruto, limpa e grava os três arquivos versionados."""
    colunas = ["aba", "fatura", "codigo_item", "quantidade", "data", "preco", "cliente"]
    por_dia, canceladas, relatorio = limpar(pd.read_parquet(ARQUIVO_PARQUET, columns=colunas))
    por_dia.to_csv(ARQUIVO_COMPRAS, index=False, date_format="%Y-%m-%d", lineterminator="\n")
    canceladas.to_csv(ARQUIVO_CANCELAMENTOS, index=False, date_format="%Y-%m-%d", lineterminator="\n")
    relatorio["fonte"] = URL
    relatorio["sha256_do_zip"] = SHA256_DO_ZIP
    ARQUIVO_LIMPEZA.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return relatorio


# --------------------------------------------------------------------------------------
# Leitura do extrato e resumo por cliente (o que a análise usa)
# --------------------------------------------------------------------------------------

def carregar_compras() -> pd.DataFrame:
    """Uma linha por cliente e dia com compra: receita bruta do dia e número de faturas."""
    return pd.read_csv(ARQUIVO_COMPRAS, parse_dates=["dia"])


def carregar_cancelamentos() -> pd.DataFrame:
    """Compras que foram canceladas depois, com o dia em que o cancelamento aconteceu."""
    return pd.read_csv(ARQUIVO_CANCELAMENTOS, parse_dates=["dia", "dia_do_cancelamento"])


def carregar_limpeza() -> dict:
    return json.loads(ARQUIVO_LIMPEZA.read_text(encoding="utf-8"))


def compras_conhecidas_em(compras: pd.DataFrame, cancelamentos: pd.DataFrame, data) -> pd.DataFrame:
    """As compras como eram conhecidas no fim do dia `data`.

    Só entram compras feitas até `data`, e só são descontados os cancelamentos que já tinham
    acontecido até `data`. Um dia cuja receita foi toda cancelada deixa de contar como compra.
    É isso que impede a limpeza de levar informação do período de validação para a calibração.
    """
    data = pd.Timestamp(data)
    conhecidas = compras[compras["dia"] <= data]
    desconto = (
        cancelamentos[cancelamentos["dia_do_cancelamento"] <= data]
        .groupby(["cliente", "dia"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "cancelado"})
    )
    conhecidas = conhecidas.merge(desconto, on=["cliente", "dia"], how="left")
    conhecidas["receita"] = (conhecidas["receita"] - conhecidas["cancelado"].fillna(0.0)).round(2)
    return conhecidas.loc[conhecidas["receita"] > 0, ["cliente", "dia", "receita"]].reset_index(drop=True)


def montar_base(compras: pd.DataFrame, cancelamentos: pd.DataFrame, corte, fim_da_validacao) -> pd.DataFrame:
    """Uma linha por cliente que comprou até `corte`: o que se sabia no corte e o que aconteceu depois.

    Calibração (só com o que era conhecido em `corte`):
      x = recompras (dias com compra depois do primeiro), t_x = semanas entre a primeira e a última
      compra, T = semanas da primeira compra até o corte, valor_medio = receita média por dia de compra.
    Validação, de `corte` (exclusive) a `fim_da_validacao`, com os cancelamentos conhecidos no fim dos dados:
      compras_futuras e receita_futura.
    """
    corte, fim_da_validacao = pd.Timestamp(corte), pd.Timestamp(fim_da_validacao)
    calibracao = compras_conhecidas_em(compras, cancelamentos, corte)
    por_cliente = calibracao.groupby("cliente").agg(
        primeira=("dia", "min"), ultima=("dia", "max"), compras=("dia", "size"), receita=("receita", "sum")
    )
    base = pd.DataFrame(index=por_cliente.index)
    base["primeira_compra"] = por_cliente["primeira"]
    base["x"] = por_cliente["compras"] - 1
    base["t_x"] = (por_cliente["ultima"] - por_cliente["primeira"]).dt.days / SEMANA
    base["T"] = (corte - por_cliente["primeira"]).dt.days / SEMANA
    base["compras"] = por_cliente["compras"]
    base["receita"] = por_cliente["receita"]
    base["valor_medio"] = por_cliente["receita"] / por_cliente["compras"]
    base["dias_calado"] = (corte - por_cliente["ultima"]).dt.days

    tudo = compras_conhecidas_em(compras, cancelamentos, pd.Timestamp.max)
    futuro = tudo[(tudo["dia"] > corte) & (tudo["dia"] <= fim_da_validacao)]
    por_cliente_futuro = futuro.groupby("cliente").agg(compras_futuras=("dia", "size"), receita_futura=("receita", "sum"))
    base = base.join(por_cliente_futuro).fillna({"compras_futuras": 0, "receita_futura": 0.0})
    base["compras_futuras"] = base["compras_futuras"].astype(int)
    return base.reset_index()
