"""Baixa a base Online Retail II (UCI, id 502), converte para parquet e regera o extrato versionado.

Uso: uv run python scripts/baixar_dados.py

O zip (45 MB) e o parquet ficam em data/brutos/, fora do git. O extrato agregado por cliente e dia
(data/compras_por_dia.csv), as compras canceladas depois (data/cancelamentos_casados.csv) e o
relatório da limpeza (data/limpeza.json) são versionados: quem não quiser baixar pode rodar a
análise direto com eles.
"""

from __future__ import annotations

import sys
import time

from valor_cliente import dados


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    inicio = time.perf_counter()
    arquivo = dados.baixar()
    print(f"zip conferido: {arquivo} ({arquivo.stat().st_size / 1e6:.1f} MB, sha256 ok)")
    if not dados.ARQUIVO_PARQUET.exists():
        print("convertendo o .xlsx para parquet (leva alguns minutos, uma vez só)...")
        dados.converter_para_parquet()
    print(f"parquet: {dados.ARQUIVO_PARQUET} ({dados.ARQUIVO_PARQUET.stat().st_size / 1e6:.1f} MB)")
    relatorio = dados.gerar_extrato()
    for chave, valor in relatorio.items():
        print(f"  {chave}: {valor}")
    print(f"extrato gravado em {dados.ARQUIVO_COMPRAS} em {time.perf_counter() - inicio:.0f} s")


if __name__ == "__main__":
    main()
