# Otimizacao de Rotas para Distribuicao de Medicamentos e Insumos (VRP Hospitalar)

Modulo `tsp/` do Tech Challenge - Fase 2. Resolve o problema de roteamento de
veiculos (VRP) para distribuicao de medicamentos e insumos entre hospitais
publicos de Sao Paulo, usando algoritmo genetico, com restricoes de
capacidade de carga, autonomia dos veiculos e prioridade de entrega, alem de
integracao com LLM para geracao de instrucoes e relatorios.

> Escopo: este modulo utiliza **somente** os dados em `tsp/bases/` (matriz de
> distancias/duracoes entre hospitais e catalogo de veiculos). Nenhum outro
> diretorio do repositorio e usado por este pipeline.

## Como executar

```bash
# a partir da raiz do repositorio, com o virtualenv do projeto ativo

# roda o TSP base (Pygame) e, na sequencia, o VRP completo com relatorios
python tsp/run.py

# roda apenas o TSP base (algoritmo genetico classico, sem restricoes de frota)
python tsp/tsp.py
```

`tsp/run.py` executa as duas etapas em sequencia: primeiro abre a janela
Pygame com o TSP base (feche a janela ou pressione `Q` para avancar), depois
roda o VRP hospitalar completo e imprime um resumo comparativo dos dois.

Saidas geradas em `tsp/output/` (pela etapa VRP):
- `mapa_rotas_otimizadas.html` - mapa interativo (Plotly) das rotas por veiculo.
- `convergencia_algoritmo_genetico.html` - curva de convergencia do GA.
- `instrucoes_motoristas.txt` - instrucoes de entrega por rota.
- `relatorio_operacional.txt` - relatorio comparando a solucao otimizada com uma baseline.

Rodar os testes:

```bash
python -m pytest tsp/tests/ -v
```

## Integracao com LLM (opcional)

Por padrao, instrucoes e relatorios sao gerados por um motor de texto baseado
em template, 100% offline e reproduzivel. Para usar uma LLM real (compativel
com a API de chat da OpenAI), defina as variaveis de ambiente:

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_BASE_URL="https://api.openai.com/v1/chat/completions"  # opcional
export OPENAI_MODEL="gpt-4o-mini"  # opcional
```

Alternativamente, e possivel usar um modelo local via [Ollama](https://ollama.com)
(sem custo, sem chave de API e sem enviar dados hospitalares para fora da maquina):

```bash
ollama serve                 # inicia o servidor local (padrao: http://localhost:11434)
ollama pull llama3.1         # baixa o modelo escolhido (uma vez)

export OLLAMA_MODEL="llama3.1"
export OLLAMA_BASE_URL="http://localhost:11434/api/chat"  # opcional
```

A prioridade e sempre da opcao mais simples/gratuita para a mais custosa:
Template (padrao, sem configuracao) > Ollama local > OpenAI (nuvem, paga).
Se `OLLAMA_MODEL` e `OPENAI_API_KEY` estiverem definidas ao mesmo tempo, o
Ollama tem prioridade. Quando nenhuma das duas esta definida, o pipeline usa
automaticamente o gerador baseado em template (ver `tsp/llm_integration.py`).

## Estrutura dos modulos

| Arquivo | Responsabilidade |
|---|---|
| `config.py` | Caminhos, seed e hiperparametros centralizados. |
| `models.py` | Dataclasses: `Hospital`, `Vehicle`, `VehicleRoute`, `VrpSolution`, `DeliveryPriority`. |
| `data_loader.py` | Carrega e valida `bases/matriz_distacias_hospitais.csv` e `bases/veiculos.csv`; gera demanda/prioridade sinteticas. |
| `distance_matrix.py` | Monta a matriz de custos (distancia/duracao) e projecao 2D (MDS) para visualizacao. |
| `vrp.py` | Decodifica a "rota gigante" (cromossomo) em rotas por veiculo respeitando capacidade/autonomia; calcula fitness. |
| `genetic_algorithm.py` | Base de TSP fornecida no desafio (mantida), com operadores de selecao (`select_parents_by_fitness`, `tournament_selection`) adicionados e reaproveitados pelo VRP. |
| `optimizer.py` | Executa o algoritmo genetico do VRP e calcula a solucao baseline. |
| `visualization.py` | Graficos interativos Plotly (mapa de rotas e convergencia). |
| `llm_integration.py` | Geracao de instrucoes/relatorios/respostas via template ou LLM real. |
| `tsp.py` | **TSP base**: algoritmo genetico classico do caixeiro viajante aplicado aos hospitais reais (1 rota, sem restricoes de frota), com visualizacao Pygame. Evoluido do arquivo base do desafio. |
| `run.py` | **Ponto de entrada principal**: executa o TSP base e o VRP hospitalar em sequencia e apresenta um resumo comparativo dos dois. |
| `benchmark_att48.py`, `draw_functions.py`, `genetic_algorithm.py` (bloco `__main__`) | Referencias do TSP classico (benchmark att48 e demo Pygame original) mantidas do projeto base; `draw_functions.py` e reaproveitado por `tsp.py`. |
| `tests/test_vrp_pipeline.py`, `tests/test_llm_integration.py` | Testes objetivos: integridade dos dados, restricoes de capacidade/autonomia, convergencia do GA, selecao/chamada dos clientes LLM. |

## Premissas assumidas (dados sinteticos documentados)

As bases fornecidas em `tsp/bases/` nao contem alguns atributos necessarios
para um VRP realista. As premissas abaixo sao aplicadas de forma
**deterministica** (seed fixa `RANDOM_SEED = 42`), garantindo reprodutibilidade:

- **Demanda (kg) e prioridade de entrega por hospital**: sorteadas
  (`data_loader.gerar_demandas_hospitais`), pois a matriz de distancias nao
  traz volume de insumos nem criticidade. ~30% das entregas sao marcadas
  como criticas (`DeliveryPriority.CRITICAL`).
- **Capacidade de carga do veiculo**: estimada por segmento/modelo
  (`config.CAPACIDADE_KG_POR_SEGMENTO`), pois `veiculos.csv` traz apenas
  dados de consumo do PBE (Programa Brasileiro de Etiquetagem).
- **Tanque de combustivel**: assumido constante (`TANQUE_LITROS_PADRAO = 50L`).
- **Autonomia do veiculo**: calculada a partir do consumo urbano **real**
  (`consumo_cidade`, km/l) multiplicado pelo tanque assumido.
- **Centro de Distribuicao (deposito)**: o hospital de `id = 1` e usado como
  CD (`config.DEPOT_HOSPITAL_ID`), pois a base nao possui um deposito
  logistico separado dos hospitais.
- **Coordenadas do mapa**: como a base nao tem latitude/longitude, as
  posicoes exibidas no mapa sao estimadas via MDS classico (Torgerson) a
  partir da matriz real de distancias, preservando as distancias relativas
  entre hospitais para fins de visualizacao.

## Modelagem do VRP

- **Representacao genetica**: cromossomo = permutacao ("rota gigante") de
  todos os hospitais, exceto o deposito.
- **Decodificacao (split)**: a rota gigante e percorrida em ordem, acumulando
  paradas no veiculo atual enquanto a capacidade de carga e a autonomia
  forem respeitadas; ao violar uma restricao, a rota e fechada (retorno ao
  CD) e a proxima parada e atribuida ao proximo veiculo da frota (com
  rotacao, permitindo multiplas viagens do mesmo veiculo no dia).
- **Fitness** (`vrp.calcular_fitness_vrp`, quanto menor melhor): soma de
  distancia total percorrida + penalidade de atraso na entrega de itens
  criticos (posicao na sequencia global de despacho, com peso maior para
  criticos) + penalidade por entregas nao atendidas (quando nenhum veiculo
  comporta aquela demanda isoladamente).
- **Operadores geneticos**: geracao de populacao, crossover de ordem (OX) e
  mutacao reaproveitados de `genetic_algorithm.py` (ja existiam no projeto
  base); selecao por amostragem ponderada pelo inverso do fitness; elitismo.

### Sobre o resultado distancia x priorizacao

O algoritmo genetico otimiza o fitness combinado, nao apenas a distancia. Em
cenarios com muitas entregas criticas, o GA pode aceitar uma distancia total
levemente maior para garantir que os hospitais criticos sejam atendidos bem
mais cedo na sequencia de despacho (metrica "posicao media de entregas
criticas" no relatorio operacional). Esse comparativo evidencia o ganho
operacional real do sistema para o contexto hospitalar, mesmo quando a
distancia bruta nao diminui.

## Requisitos entregues

1. **Algoritmo genetico para TSP/VRP**: representacao, selecao, crossover,
   mutacao, elitismo e fitness com distancia + prioridade + restricoes.
2. **Restricoes realistas**: prioridade de entrega, capacidade de carga,
   autonomia de veiculos, multiplos veiculos (VRP).
3. **Visualizacao**: mapa interativo das rotas (Plotly) e grafico de
   convergencia do GA.
4. **Integracao com LLM**: geracao de instrucoes para motoristas, relatorios
   operacionais comparando com baseline, e resposta a perguntas em linguagem
   natural sobre as rotas (`llm_integration.responder_pergunta`).
