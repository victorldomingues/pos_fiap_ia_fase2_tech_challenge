# IADT - Fase 2 - Tech Challenge

Victor Luiz Domingues  
RM: rm375278

Este módulo implementa o Projeto 2 de otimização de rotas médicas com TSP/VRP usando algoritmos genéticos.
A solução considera prioridades de entrega, capacidade e autonomia dos veículos, com visualização de rotas e suporte de LLM para relatórios e instruções operacionais.

## Relatório técnico

O detalhamento completo da implementação, arquitetura, premissas, resultados,
integrações e evidências visuais está em [RELATORIO_TECNICO.md](../RELATORIO_TECNICO.md).

## Execução rápida do projeto tsp

1. Ative o ambiente virtual na raiz do repositório:

```bash
source .venv/bin/activate
```

2. Execute a solução principal (VRP por padrão):

```bash
python tsp/run.py
```

3. Opcional: execute apenas o TSP base (modo clássico com Pygame):

```bash
python tsp/tsp.py
```

4. Opcional: rode os testes da solução tsp:

```bash
python -m pytest tsp/tests/ -v
```

---

## Como executar

```bash
# a partir da raiz do repositório, com o virtualenv do projeto ativo

# roda somente o VRP completo com relatórios (padrão)
python tsp/run.py

# roda apenas o TSP base (algoritmo genético clássico, sem restrições de frota)
python tsp/tsp.py
```

Por padrão, [`tsp/run.py`](run.py) executa somente o VRP hospitalar (não abre janela
Pygame). Para também rodar o TSP base antes do VRP (útil para comparar os
dois), defina `EXECUTAR_TSP_BASE = True` em [`tsp/config.py`](config.py), ou chame
`main(executar_tsp_base=True)` programaticamente — nesse caso, feche a
janela do Pygame (ou pressione `Q`) para avançar para o VRP, que roda em
seguida e imprime um resumo comparativo dos dois.

Saídas geradas em `tsp/output/` (pela etapa VRP):
- `mapa_rotas_otimizadas.html` — mapa interativo (Plotly) das rotas por veículo.
- `mapa_rotas_openstreetmap.html` — mapa geografico OpenStreetMap com toggle de rotas pela legenda.
- `convergencia_algoritmo_genetico.html` — curva de convergência do GA.
- `instrucoes_motoristas.md` — instruções de entrega por rota.
- `relatorio_operacional.md` — relatório comparando a solução otimizada com uma baseline.

Rodar os testes:

```bash
# testes da solução TSP/VRP e integração LLM (pasta tsp/tests)
python -m pytest tsp/tests/ -v

# testes dos serviços de integração de dados (pasta tests na raiz)
python -m pytest tests/ -v
```

---

## Serviços e testes do repositório

Embora este README esteja focado na solução em `./tsp`, o repositório também
contém componentes de suporte importantes para o pipeline de dados:

1. [`./servicos`](../servicos/)
   1. [`servicos/open_street_map/service.py`](../servicos/open_street_map/service.py): encapsula a integração de geocodificação com OpenStreetMap/Nominatim (latitude/longitude).
   2. [`servicos/open_route/service.py`](../servicos/open_route/service.py): encapsula a integração com OpenRouteService para matriz de distância e duração entre hospitais.
   3. Esses serviços são usados principalmente pelos scripts em [`./casos_de_uso`](../casos_de_uso/) na etapa de preparação da base.

2. [`./tests`](../tests/) (raiz do repositório)
   1. Contém testes dos serviços externos de dados.
   2. Exemplo atual: validação de comportamento do serviço OpenStreetMap.

3. [`./tsp/tests`](tests/)
   1. Contém os testes da solução de otimização (TSP/VRP) e da camada de LLM.
   2. Cobertura principal: carga de dados, restrições do VRP, convergência do algoritmo genético e seleção de cliente LLM.

---

## Resultados visuais dos casos de uso

As imagens abaixo são os resultados gerados pelos casos de uso de
visualização (principalmente [`5-gerar_imagem_grafo.usecase.py`](../casos_de_uso/5-gerar_imagem_grafo.usecase.py) e
[`7-gerar_imagem_grafo_matriz_distancias.usecase.py`](../casos_de_uso/7-gerar_imagem_grafo_matriz_distancias.usecase.py)), salvas em
[`bases/graficos/`](../bases/graficos/).

### Grafo e mapa do conjunto de hospitais

1. Grafo cartesiano dos hospitais selecionados:

![Grafo hospitais públicos de São Paulo](../bases/graficos/grafo_hospitais_publicos_sao_paulo.png)

2. Mapa dos hospitais selecionados:

![Mapa hospitais públicos de São Paulo](../bases/graficos/mapa_hospitais_publicos_sao_paulo.png)

### Grafo ponderado pela matriz de custos

1. Grafo com pesos de distância (km):

![Grafo hospitais por distância](../bases/graficos/grafo_hospitais_distancia_matriz.png)

2. Grafo com pesos de duração (minutos):

![Grafo hospitais por duração](../bases/graficos/grafo_hospitais_duracao_matriz.png)

3. Mapa com pesos de distância (km):

![Mapa hospitais por distância](../bases/graficos/mapa_hospitais_distancia_matriz.png)

4. Mapa com pesos de duração (minutos):

![Mapa hospitais por duração](../bases/graficos/mapa_hospitais_duracao_matriz.png)

---

## Integração com LLM (opcional)

Por padrão, instruções e relatórios são gerados por um motor de texto baseado
em template, 100% offline e reproduzível. Para usar uma LLM real (compatível
com a API de chat da OpenAI), defina as variáveis de ambiente:

```bash
export OPENAI_API_KEY="sua-chave"
export OPENAI_BASE_URL="https://api.openai.com/v1/chat/completions"  # opcional
export OPENAI_MODEL="gpt-4o-mini"  # opcional
```

Alternativamente, é possível usar um modelo local via [Ollama](https://ollama.com)
(sem custo, sem chave de API e sem enviar dados hospitalares para fora da máquina):

```bash
ollama serve                 # inicia o servidor local (padrão: http://localhost:11434)
ollama pull llama3.1         # baixa o modelo escolhido (uma vez)

export OLLAMA_MODEL="llama3.1"
export OLLAMA_BASE_URL="http://localhost:11434/api/chat"  # opcional
```

A prioridade é sempre da opção mais simples/gratuita para a mais custosa:
Template (padrão, sem configuração) > Ollama local > OpenAI (nuvem, paga).
Se `OLLAMA_MODEL` e `OPENAI_API_KEY` estiverem definidas ao mesmo tempo, o
Ollama tem prioridade. Quando nenhuma das duas está definida, o pipeline usa
automaticamente o gerador baseado em template (ver [`tsp/llm_integration.py`](llm_integration.py)).

---

## Estrutura dos módulos

| Arquivo | Responsabilidade |
|---|---|
| [`config.py`](config.py) | Caminhos, seed e hiperparâmetros centralizados. |
| [`models.py`](models.py) | Dataclasses: `Hospital`, `Vehicle`, `VehicleRoute`, `VrpSolution`, `DeliveryPriority`. |
| [`data_loader.py`](data_loader.py) | Carrega e valida [`bases/matriz_distacias_hospitais.csv`](bases/matriz_distacias_hospitais.csv) e [`bases/veiculos.csv`](bases/veiculos.csv); gera demanda/prioridade sintéticas. |
| [`distance_matrix.py`](distance_matrix.py) | Monta a matriz de custos (distância/duração) e projeção 2D (MDS) para visualização. |
| [`vrp.py`](vrp.py) | Decodifica a "rota gigante" (cromossomo) em rotas por veículo respeitando capacidade/autonomia; calcula fitness. |
| [`genetic_algorithm.py`](genetic_algorithm.py) | Base de TSP fornecida no desafio (mantida), com operadores de seleção (`select_parents_by_fitness`, `tournament_selection`) adicionados e reaproveitados pelo VRP. |
| [`optimizer.py`](optimizer.py) | Executa o algoritmo genético do VRP e calcula a solução baseline. |
| [`visualization.py`](visualization.py) | Gráficos interativos Plotly (mapa de rotas e convergência). |
| [`llm_integration.py`](llm_integration.py) | Geração de instruções/relatórios/respostas via template ou LLM real. |
| [`tsp.py`](tsp.py) | **TSP base**: algoritmo genético clássico do caixeiro viajante aplicado aos hospitais reais (1 rota, sem restrições de frota), com visualização Pygame. Evoluído do arquivo base do desafio. |
| [`run.py`](run.py) | **Ponto de entrada principal**: executa o TSP base e o VRP hospitalar em sequência e apresenta um resumo comparativo dos dois. |
| [`benchmark_att48.py`](benchmark_att48.py), [`draw_functions.py`](draw_functions.py) | Referências do TSP clássico (benchmark att48 e demo Pygame original) mantidas do projeto base; [`draw_functions.py`](draw_functions.py) é reaproveitado por [`tsp.py`](tsp.py). |
| [`tests/test_vrp_pipeline.py`](tests/test_vrp_pipeline.py), [`tests/test_llm_integration.py`](tests/test_llm_integration.py) | Testes objetivos: integridade dos dados, restrições de capacidade/autonomia, convergência do GA, seleção/chamada dos clientes LLM. |

Componentes relacionados fora de `./tsp`:

- [`./servicos`](../servicos/): clientes de integração para OpenStreetMap e OpenRouteService.
- [`./tests`](../tests/): testes da camada de serviços de dados do repositório.

---

## Premissas assumidas (dados sintéticos documentados)

As bases fornecidas em [`tsp/bases/`](bases/) não contêm alguns atributos necessários
para um VRP realista. As premissas abaixo são aplicadas de forma
**determinística** (seed fixa `RANDOM_SEED = 42`), garantindo reprodutibilidade:

- **Demanda (kg) e prioridade de entrega por hospital**: sorteadas
  (`data_loader.gerar_demandas_hospitais`), pois a matriz de distâncias não
  traz volume de insumos nem criticidade. ~30% das entregas são marcadas
  como críticas (`DeliveryPriority.CRITICAL`).
- **Capacidade de carga do veículo**: estimada por segmento/modelo
  (`config.CAPACIDADE_KG_POR_SEGMENTO`), pois [`bases/veiculos.csv`](bases/veiculos.csv) traz apenas
  dados de consumo do PBE (Programa Brasileiro de Etiquetagem).
- **Tanque de combustível**: assumido constante (`TANQUE_LITROS_PADRAO = 50L`).
- **Autonomia do veículo**: calculada a partir do consumo urbano **real**
  (`consumo_cidade`, km/l) multiplicado pelo tanque assumido.
- **Centro de Distribuição (depósito)**: o hospital de `id = 1` é usado como
  CD (`config.DEPOT_HOSPITAL_ID`), pois a base não possui um depósito
  logístico separado dos hospitais.
- **Coordenadas dos mapas**: o mapa OpenStreetMap usa `origin_latitude` e
  `origin_longitude` da própria [`bases/matriz_distacias_hospitais.csv`](bases/matriz_distacias_hospitais.csv).
  O mapa MDS continua disponível como visualização alternativa, projetando os
  hospitais em 2D a partir da matriz real de distâncias.

---

## Modelagem do VRP

- **Representação genética**: cromossomo = permutação ("rota gigante") de
  todos os hospitais, exceto o depósito.
- **Decodificação (split)**: a rota gigante é percorrida em ordem, acumulando
  paradas no veículo atual enquanto a capacidade de carga e a autonomia
  forem respeitadas; ao violar uma restrição, a rota é fechada (retorno ao
  CD) e a próxima parada é atribuída ao próximo veículo da frota (com
  rotação, permitindo múltiplas viagens do mesmo veículo no dia).
- **Fitness** ([`vrp.calcular_fitness_vrp`](vrp.py), quanto menor melhor): soma de
  distância total percorrida + penalidade de atraso na entrega de itens
  críticos (posição na sequência global de despacho, com peso maior para
  críticos) + penalidade por entregas não atendidas (quando nenhum veículo
  comporta aquela demanda isoladamente).
- **Operadores genéticos**: geração de população, crossover de ordem (OX) e
  mutação reaproveitados de [`genetic_algorithm.py`](genetic_algorithm.py) (já existiam no projeto
  base); seleção por amostragem ponderada pelo inverso do fitness; elitismo.

### Sobre o resultado distância x priorização

O algoritmo genético otimiza o fitness combinado, não apenas a distância. Em
cenários com muitas entregas críticas, o GA pode aceitar uma distância total
levemente maior para garantir que os hospitais críticos sejam atendidos bem
mais cedo na sequência de despacho (métrica "posição média de entregas
críticas" no relatório operacional). Esse comparativo evidencia o ganho
operacional real do sistema para o contexto hospitalar, mesmo quando a
distância bruta não diminui.

---

## Requisitos entregues

1. **Algoritmo genético para TSP/VRP**: representação, seleção, crossover,
   mutação, elitismo e fitness com distância + prioridade + restrições.
2. **Restrições realistas**: prioridade de entrega, capacidade de carga,
   autonomia de veículos, múltiplos veículos (VRP).
3. **Visualização**: mapa interativo das rotas (Plotly) e gráfico de
   convergência do GA.
4. **Integração com LLM**: geração de instruções para motoristas, relatórios
   operacionais comparando com baseline, e resposta a perguntas em linguagem
   natural sobre as rotas ([`llm_integration.responder_pergunta`](llm_integration.py)).
