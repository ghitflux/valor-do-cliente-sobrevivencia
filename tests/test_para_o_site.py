"""Forma do bloco `para_o_site` em reports/resultados.json (o site desenha os gráficos a partir dele)."""

import json
import re
from pathlib import Path

import pytest

ARQUIVO = Path(__file__).resolve().parents[1] / "reports" / "resultados.json"
IDIOMAS = {"pt", "en", "es"}
PAPEIS = {"principal", "base", "alternativa", "neutro"}
FORMATOS = {"numero", "percentual", "moeda", "data"}


@pytest.fixture(scope="module")
def site() -> dict:
    if not ARQUIVO.exists():
        pytest.skip("reports/resultados.json ainda não foi gerado")
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))["para_o_site"]


def _tres_idiomas(campo) -> bool:
    return isinstance(campo, dict) and set(campo) == IDIOMAS and all(isinstance(v, str) and v.strip() for v in campo.values())


def _conferir_grafico(g: dict, extra: bool) -> None:
    assert g["tipo"] in {"linhas", "barras", "pontos"}
    for campo in ("titulo", "eixo_x", "eixo_y"):
        assert _tres_idiomas(g[campo]), campo
    if extra:
        assert _tres_idiomas(g["leitura"])
        assert all(len(t) <= 90 for t in g["titulo"].values()), g["titulo"]
    assert g["formato_x"] in FORMATOS and g["formato_y"] in FORMATOS
    assert 1 <= len(g["series"]) <= 4
    limite = 300 if g["tipo"] == "pontos" else 80
    for serie in g["series"]:
        assert _tres_idiomas(serie["nome"]) and serie["papel"] in PAPEIS
        assert 1 <= len(serie["pontos"]) <= limite
        for x, y in serie["pontos"]:
            assert isinstance(y, (int, float))
            if g["tipo"] == "barras":
                assert isinstance(x, str)
            elif g["formato_x"] == "data":
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)
            else:
                assert isinstance(x, (int, float))
        if "rotulos" in serie:
            assert g["tipo"] == "barras" and set(serie["rotulos"]) == IDIOMAS
            assert all(len(r) == len(serie["pontos"]) for r in serie["rotulos"].values())
    if "faixa" in g:
        assert g["tipo"] == "linhas"
        faixa = g["faixa"]
        n = len(g["series"][faixa["serie"]]["pontos"])
        assert len(faixa["inferior"]) == len(faixa["superior"]) == n
        assert all(i[1] <= s[1] + 1e-9 for i, s in zip(faixa["inferior"], faixa["superior"]))


def test_grafico_principal_tem_a_forma_combinada(site):
    assert all(_tres_idiomas(site[c]) for c in ("numero_chave", "pergunta", "resultado", "detalhe", "dados"))
    assert all(len(v) <= 12 for v in site["numero_chave"].values())
    _conferir_grafico(site["grafico"], extra=False)


def test_graficos_extras_tem_a_forma_combinada(site):
    extras = site["graficos_extras"]
    assert 3 <= len(extras) <= 5
    for grafico in extras:
        _conferir_grafico(grafico, extra=True)
    titulos = [g["titulo"]["pt"] for g in extras]
    assert len(set(titulos)) == len(titulos)
