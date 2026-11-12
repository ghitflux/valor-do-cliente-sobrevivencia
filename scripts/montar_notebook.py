"""Monta analise.ipynb com nbformat. Depois de montar, execute:

    uv run python scripts/montar_notebook.py
    uv run jupyter nbconvert --to notebook --execute --inplace analise.ipynb

O notebook é uma narrativa fina: chama o pacote, mostra a tabela e a figura, e discute.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

RAIZ = Path(__file__).resolve().parents[1]

CELULAS: list[tuple[str, str]] = [
    ("md", """# Quanto vale um cliente novo nos próximos meses, e quando dá para considerar que ele foi embora?

É a conta que define o teto do custo de aquisição (quanto dá para pagar por um cliente) e o momento de gastar com
reativação. A base é a **Online Retail II** (UCI, CC BY 4.0): dois anos de vendas de um varejista online britânico,
boa parte para revendedores.

O desenho é o de quem usaria o resultado: **um ano para aprender** (1/12/2009 a 30/11/2010) e **o ano seguinte para
conferir** (1/12/2010 a 30/11/2011). Nada do segundo ano entra no ajuste.

Os modelos (BG/NBD, Gamma-Gamma, Kaplan-Meier) estão implementados em `src/valor_cliente/`, em NumPy/SciPy, e
conferidos em `tests/` contra integrais numéricas, dados simulados e exemplos publicados."""),
    ("code", """import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display

from valor_cliente import analise, dados, graficos
from valor_cliente import avaliacao as av

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
pd.set_option("display.max_columns", 30)


def mostrar(figura):
    display(figura)
    plt.close(figura)"""),
    ("md", """## 1. Os dados e a limpeza

O bruto tem uma linha por item de fatura. `scripts/baixar_dados.py` baixa, limpa e grava o extrato usado aqui: uma
linha por cliente e dia com compra. Cada passo da limpeza está contado abaixo."""),
    ("code", """compras, cancelamentos, limpeza = dados.carregar_compras(), dados.carregar_cancelamentos(), dados.carregar_limpeza()
pd.Series({k: v for k, v in limpeza.items() if k not in ("fonte", "sha256_do_zip")}, name="valor").to_frame()"""),
    ("md", """Três decisões que mudam o resultado:

- **Uma compra = um dia com compra.** Várias faturas no mesmo dia contam como uma ocasião.
- **Cancelamentos.** Tirar só as faturas "C" deixaria na base a compra que foi desfeita (há um pedido de 77 mil
  libras cancelado minutos depois). Cada cancelamento é casado com a compra original.
- **Sem informação do futuro nem na limpeza.** Uma compra de novembro de 2010 cancelada em janeiro de 2011 ainda
  existe quando o modelo é ajustado: o cancelamento só é descontado a partir da data em que acontece."""),
    ("code", """base = dados.montar_base(compras, cancelamentos, analise.CORTE, analise.FIM_DA_VALIDACAO)
compras_liquidas = dados.compras_conhecidas_em(compras, cancelamentos, pd.Timestamp.max)
horizonte = analise.semanas_entre(analise.CORTE, analise.FIM_DA_VALIDACAO)
display(base.head())
pd.Series(analise.resumo_da_base(base, horizonte), name="valor").to_frame()"""),
    ("md", """## 2. Os modelos ajustados

- **BG/NBD**: cada cliente compra a uma taxa própria enquanto está ativo e, depois de cada recompra, pode abandonar
  de vez. Quatro parâmetros descrevem como taxa e abandono variam na base.
- **Gamma-Gamma**: cada cliente tem um valor médio por compra próprio; a média observada é puxada para a média da
  base, e puxada menos quanto mais compras o cliente tiver."""),
    ("code", """bg, gama = analise.ajustar_modelos(base)
previsoes = analise.prever(base, bg, gama, horizonte)
parametros = analise.parametros(bg, gama, previsoes)
display(pd.DataFrame({"BG/NBD": pd.Series(parametros["bgnbd"]), "Gamma-Gamma": pd.Series(parametros["gamma_gamma"])}))
pd.Series({k: v for k, v in parametros.items() if not isinstance(v, dict)}, name="valor").to_frame()"""),
    ("code", """pd.Series(parametros["probabilidade_vivo"], name="P(vivo)").to_frame()"""),
    ("md", """**O primeiro sinal de problema.** O abandono médio por recompra saiu perto de zero, e a probabilidade de estar
"vivo" passa de 96% para 99 em cada 100 clientes. O modelo olhou um ano de compras e concluiu que ninguém vai embora.
Na prática ele virou um modelo sem abandono. O ano seguinte mostra o preço disso."""),
    ("md", """## 3. Quantas compras cada cliente fez no ano seguinte

Três previsões por cliente: o BG/NBD, a taxa histórica do próprio cliente (repete o ritmo) e a média da base (o mesmo
número para todos). Intervalos de 95% por bootstrap de clientes."""),
    ("code", """indices = av.indices_de_bootstrap(len(base), analise.REPETICOES, analise.SEMENTE)
erros, diferencas = analise.erro_nas_compras(base, previsoes, indices)
display(erros)
pd.Series(diferencas, name="valor").to_frame()"""),
    ("md", """O modelo erra um pouco menos por cliente do que a taxa histórica (a diferença no erro absoluto é pequena; no erro
quadrático é clara, porque o modelo não exagera nos clientes de poucas compras e ritmo alto). Mas os dois **preveem
compras demais no total**, e o modelo mais do que a regra simples.

Por faixa de frequência, o excesso está em quem comprou pouco:"""),
    ("code", """calibracao = analise.calibracao_por_frequencia(base, previsoes)
display(calibracao)
mostrar(graficos.calibracao_por_frequencia(calibracao))"""),
    ("md", """E mês a mês: o modelo prevê um ano plano. A realidade tem vale em janeiro e fevereiro e pico em novembro, e fica
abaixo do previsto em onze dos doze meses."""),
    ("code", """mensal = analise.acompanhamento_mensal(base, bg, compras_liquidas)
display(mensal)
mostrar(graficos.sazonalidade(mensal))"""),
    ("md", """## 4. Onde está a receita do ano seguinte

Para o negócio, a pergunta prática é de ordenação: se eu só puder cuidar de perto de 10% ou 20% dos clientes, quais?
Cada método gera uma lista; mede-se quanto da receita do ano seguinte está no topo dela. A coluna `menos_modelo`
compara cada método com o modelo nas mesmas reamostras."""),
    ("code", """captura = analise.captura_de_receita(base, previsoes, indices)
display(captura)
mostrar(graficos.captura_de_receita(analise.curvas_de_captura(base, previsoes, pontos=101), captura))"""),
    ("md", """**Empate.** A lista do modelo e a lista de quem mais gastou até hoje capturam praticamente a mesma receita, e o
intervalo da diferença inclui o zero. A regra de RFM por quintos perde: ao somar três notas de 1 a 5, ela achata
justamente a diferença entre o cliente grande e o enorme, que é onde a receita está. O teto (ordem perfeita) mostra
que não sobra muito para ganhar."""),
    ("md", """## 5. O valor por compra (Gamma-Gamma)

A hipótese do modelo é que o valor por compra não depende da frequência. Conferindo:"""),
    ("code", """independencia = analise.independencia_frequencia_valor(base)
display(pd.Series({k: v for k, v in independencia.items() if k != "ticket_por_faixa_de_compras"}, name="valor").to_frame())
independencia["ticket_por_faixa_de_compras"]"""),
    ("md", """A hipótese não vale exatamente: quem compra mais vezes gasta um pouco mais por compra (correlação fraca, mas com
intervalo longe do zero). Multiplicar compras esperadas por ticket esperado, como se fossem independentes, subestima
um pouco os clientes grandes.

E o modelo prevê melhor o ticket futuro do que a média crua do cliente?"""),
    ("code", """analise.erro_no_ticket(base, previsoes)"""),
    ("md", """Na média, sim, e o ganho está onde se esperava: em quem só tinha uma compra no histórico. Na mediana, a média crua
do cliente erra menos: puxar para a média da base ajuda nos casos extremos e atrapalha um pouco nos comuns."""),
    ("md", """## 6. Quanto vale um cliente novo

A previsão do modelo para quem acabou de fazer a primeira compra: recompras esperadas em *t* semanas vezes o ticket
médio da base. A incerteza dos parâmetros vem de reajustar os dois modelos em 200 reamostras de clientes.

A conferência usa os **clientes novos do ano de validação**: gente cuja primeira compra na base aconteceu depois do
corte, quando já havia um ano de histórico sem eles."""),
    ("code", """reajustes = analise.reajustes_por_bootstrap(base, bg, gama)
novo = analise.valor_do_cliente_novo(compras, cancelamentos, base, bg, gama, reajustes)
novo["tabela"].T"""),
    ("code", """mostrar(graficos.valor_do_cliente_novo(novo["curvas"], novo["tabela"].loc[f"{analise.HORIZONTE_PRINCIPAL} semanas"]))"""),
    ("md", """**O modelo promete quase o dobro do que os clientes novos entregaram**, e a faixa de incerteza dele é estreita:
ela mede o erro de amostragem dos parâmetros, não o erro de o modelo estar descrevendo a população errada.

De onde vem o erro? A base começa em dezembro de 2009 e não diz quem já era cliente antes. Quem aparece no primeiro
mês é, em boa parte, cliente antigo, que compra muito mais. As linhas de diagnóstico da tabela refazem as contas sem
esse primeiro mês: a previsão cai bastante, mas continua acima do real. (Essa variante foi tentada depois de ver o
erro; ela explica a causa, não é uma validação limpa.)

O valor de *um* cliente também varia muito mais do que a média sugere:"""),
    ("code", """display(novo["distribuicao"])
pd.Series({k: v for k, v in novo.items() if k not in ("tabela", "curvas", "distribuicao", "diagnostico_bgnbd")}, name="valor").to_frame()"""),
    ("md", """## 7. Quando considerar que o cliente foi embora

Aqui não há contrato nem cancelamento: o abandono nunca é observado, só o silêncio. Duas ferramentas:

**Kaplan-Meier** para o tempo até a segunda compra. Quem ainda não voltou quando os dados acabam entra como
censurado (sabe-se só que o tempo dele é maior do que o observado)."""),
    ("code", """sobrevivencia = analise.curvas_de_sobrevivencia(compras, cancelamentos)
display(sobrevivencia["tabela"])
mostrar(graficos.tempo_ate_a_recompra(sobrevivencia["curvas"], sobrevivencia["tabela"]))"""),
    ("md", """A curva de quem aparece em dezembro de 2009 confirma o diagnóstico da seção 6: esse grupo volta rápido demais
para ser de clientes novos.

A chance de voltar nas 26 semanas seguintes, dado que o cliente já está calado há algum tempo, sai da própria curva:
1 − S(silêncio + 26) / S(silêncio)."""),
    ("code", """pd.DataFrame({grupo: {k: v["chance_de_voltar_em_26_semanas"] for k, v in valores.items()} for grupo, valores in sobrevivencia["chance_de_voltar"].items()})"""),
    ("md", """**A conferência direta.** No corte, cada cliente estava calado há um certo tempo. Quantos voltaram nas 26 e nas
52 semanas seguintes? Ao lado, a probabilidade de compra em 26 semanas que o BG/NBD dava a cada grupo."""),
    ("code", """silencio = analise.retorno_por_silencio(base, bg, compras_liquidas)
display(silencio)
mostrar(graficos.retorno_por_silencio(silencio))"""),
    ("md", """Não aparece um ponto de corte: a chance de volta cai aos poucos com o silêncio, e mesmo entre quem comprou uma vez
e estava calado havia mais de nove meses, cerca de um em cada quatro voltou dentro de um ano. O que muda muito é o
ponto de partida: quem só comprou uma vez já começa com chance baixa. O BG/NBD, que não enxergou abandono, promete
volta demais em todas as faixas."""),
    ("md", """## 8. O resultado depende do corte?

Refazendo tudo com outros cortes. A coluna do meio é a análise principal."""),
    ("code", """analise.sensibilidade_ao_corte(compras, cancelamentos).T"""),
    ("md", """- **Ordenação: estável.** Em todos os cortes o modelo fica de zero a dois pontos acima do gasto histórico, e sempre
  acima da regra de RFM.
- **Volume: instável.** O excesso de compras previstas vai de quase zero a 50% conforme o corte. É pior quando a
  calibração termina no pico de fim de ano (tudo parece vivo e acelerando) e some quando o modelo já viu o silêncio de
  janeiro e fevereiro do segundo ano: só aí o abandono médio estimado sai do zero.

## Conclusão

1. Com um ano de histórico, o modelo de valor do cliente **ordena bem, mas não melhor do que "quem mais gastou"**.
2. **Como previsão de volume e de valor do cliente novo, ele erra para cima**, e a regra simples erra junto: o problema
   está nos dados (não se sabe quem é novo; um ano sazonal esconde o abandono), não na conta.
3. **"Foi embora" não tem data.** O que há é uma chance de volta que cai com o silêncio e que depende, antes de tudo,
   de o cliente já ter voltado alguma vez."""),
]


def main() -> None:
    caderno = new_notebook()
    caderno.cells = [new_markdown_cell(texto) if tipo == "md" else new_code_cell(texto) for tipo, texto in CELULAS]
    caderno.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    caderno.metadata["language_info"] = {"name": "python"}
    nbformat.write(caderno, RAIZ / "analise.ipynb")
    print(f"notebook montado: {RAIZ / 'analise.ipynb'} ({len(caderno.cells)} células)")


if __name__ == "__main__":
    main()
