# Protótipo de recomendação de grupos de híbridos de milho

Projeto do Trabalho de Conclusão de Curso em Sistemas de Informação da Unochapecó.

**Título:** Protótipo de Sistema de Recomendação de Grupos de Híbridos de Milho Baseado em Dados Climáticos e Zoneamento Agrícola  
**Autor:** Jorge Gabriel Silva Lima  
**Orientador:** Prof. Dr. Sandro Silva de Oliveira

O protótipo recomenda o grupo de híbrido de milho (Grupo I ou Grupo II) para os 295 municípios de Santa Catarina, considerando o tipo de solo e o decêndio de plantio. As recomendações são feitas a partir de dados públicos de clima, localização e produção, utilizando as indicações do Zoneamento Agrícola de Risco Climático (ZARC) como referência. O protótipo não substitui as indicações oficiais do ZARC.

## Fontes de dados

- NASA POWER: dados climáticos diários de 2015 a 2026
- IBGE: municípios, microrregiões, malha municipal e Produção Agrícola Municipal (PAM)
- ZARC: tábuas de risco do milho de primeira safra
- Mapa pedológico: tipos de solo por município

## Estrutura

```text
bronze/      coleta dos dados de cada fonte
silver/      tratamento e padronização dos dados
gold/        datasets finais usados no modelo
modelo/      treinamento, comparação dos modelos e K-Means
api/         API (FastAPI) e página de consulta
dags/        pipeline no Apache Airflow
sql/         criação dos schemas no PostgreSQL
config/      conexão com o banco de dados
resultados/  gráficos, mapas e métricas
```

## Tecnologias

- Python 3.11
- PostgreSQL 18 com PostGIS
- pandas, GeoPandas, scikit-learn e matplotlib
- FastAPI e Uvicorn
- Apache Airflow 3.1 (WSL)

## Como executar

1. Criar o banco no PostgreSQL e rodar o arquivo `sql/criar_estrutura.sql`.
2. Criar o arquivo `.env` na raiz com `HOST`, `USER`, `PASSWORD`, `PORT` e `SID`.
3. Colocar os arquivos do ZARC e do mapa de solos em `data/externo/`.
4. Ativar o ambiente virtual e rodar as etapas na ordem:

```bash
python -m bronze.main
python -m silver.main
python -m gold.main
python -m modelo.treinar
python -m modelo.comparar_modelos
python -m modelo.clusterizar
```

5. Iniciar a API:

```bash
python -m uvicorn api.main:app --port 8000
```

A página de consulta fica em http://localhost:8000.

## Modelos

Foram comparados os algoritmos Random Forest, Extra Trees e Gradient Boosting com o método do município mais próximo. A validação foi feita com GroupKFold, separando os municípios pelas 20 microrregiões do IBGE. O Random Forest foi utilizado no protótipo. O K-Means foi utilizado para agrupar os municípios pelas características climáticas e comparar os grupos com o ZARC.
