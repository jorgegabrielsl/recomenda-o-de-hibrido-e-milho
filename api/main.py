import os

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from config.db.conexao import conexao_pgsql
from modelo.treinar import VARIAVEIS
from silver.zarc_risco import nome_decendio

app = FastAPI(title="Recomendacao de grupos de hibridos de milho - SC")

# carrega tudo uma vez quando a API sobe
engine = conexao_pgsql()
modelo = joblib.load(os.path.join("modelo", "modelo_random_forest.joblib"))
dados = pd.read_sql("SELECT * FROM gold.dataset_treino", engine)
validacao = pd.read_sql("SELECT id_municipio, cod_solo, decendio, random_forest FROM gold.previsoes_validacao", engine)
clusters = pd.read_sql("SELECT id_municipio, cluster FROM gold.clusters_municipio", engine)

dados = dados.merge(validacao, on=["id_municipio", "cod_solo", "decendio"], how="left")
dados = dados.merge(clusters, on="id_municipio", how="left")

# codigos internos continuam ciclo_20 e ciclo_21 (Cod_Ciclo do ZARC)
# nomes oficiais: dicionario da Tabua de Risco e Portaria SPA/MAPA n 193/2025
# 20 = Grupo I (ciclo medio 120 dias), 21 = Grupo II (ciclo medio 140 dias)
TEXTOS = {
    "ciclo_20": "Grupo I (120 dias) tem o menor risco",
    "ciclo_21": "Grupo II (140 dias) tem o menor risco",
    "empate": "Grupos I e II com o mesmo risco",
    "nao_indicado": "Plantio não indicado neste período",
}

NOMES = {
    "ciclo_20": "Grupo I (120 dias)",
    "ciclo_21": "Grupo II (140 dias)",
    "empate": "Grupos I e II (empate)",
    "nao_indicado": "Não indicado",
}

SOLOS = {
    1: "Arenoso",
    2: "Textura média",
    3: "Argiloso",
}

REGIOES = {
    1: "Litoral norte e leste",
    2: "Oeste",
    3: "Planalto e serra",
    4: "Litoral sul",
}


@app.get("/")
def pagina():
    # no-cache: o navegador sempre busca a versao mais nova da pagina
    return FileResponse(os.path.join("api", "static", "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/status")
def status():
    return {"status": "ok", "linhas_carregadas": len(dados)}


@app.get("/municipios")
def municipios():
    lista = dados[["id_municipio", "municipio"]].drop_duplicates()
    lista = lista.sort_values("municipio")

    resposta = []
    for _, linha in lista.iterrows():
        resposta.append({"id_municipio": int(linha["id_municipio"]), "municipio": linha["municipio"]})
    return resposta


@app.get("/recomendacao")
def recomendacao(id_municipio: int, solo: int, decendio: int = None):
    if solo not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="solo deve ser 1 (arenoso), 2 (textura media) ou 3 (argiloso)")

    filtro = dados[(dados["id_municipio"] == id_municipio) & (dados["cod_solo"] == solo)]
    if len(filtro) == 0:
        raise HTTPException(status_code=404, detail="municipio nao encontrado")

    if decendio is not None:
        filtro = filtro[filtro["decendio"] == decendio]
        if len(filtro) == 0:
            raise HTTPException(status_code=404, detail="decendio fora da janela do estado (agosto a janeiro)")

    filtro = filtro.sort_values("ordem_na_safra")

    previsao = modelo.predict(filtro[VARIAVEIS])
    probabilidades = modelo.predict_proba(filtro[VARIAVEIS])
    classes = list(modelo.classes_)

    primeira = filtro.iloc[0]
    cluster = int(primeira["cluster"])

    resposta = {}
    resposta["id_municipio"] = id_municipio
    resposta["municipio"] = primeira["municipio"]
    resposta["solo"] = solo
    resposta["solo_nome"] = SOLOS[solo]
    resposta["regiao_climatica"] = "Cluster " + str(cluster) + " - " + REGIOES[cluster]

    # clima medio historico do municipio (agosto a marco)
    resposta["clima_municipio"] = {
        "temp_media": round(float(primeira["temp_media_hist"]), 1),
        "chuva_safra_mm": round(float(primeira["chuva_safra_hist"]), 0),
        "soma_termica_safra": round(float(primeira["gdd_safra_hist"]), 0),
    }

    resposta["decendios"] = []

    posicao = 0
    for _, linha in filtro.iterrows():
        classe = previsao[posicao]
        probabilidade = probabilidades[posicao][classes.index(classe)]

        item = {}
        item["decendio"] = int(linha["decendio"])
        item["periodo"] = nome_decendio(int(linha["decendio"]))
        item["recomendacao"] = classe
        item["recomendacao_nome"] = NOMES[classe]
        item["texto"] = TEXTOS[classe]
        item["confianca"] = round(float(probabilidade), 2)

        # referencia oficial e previsao feita quando o municipio estava fora do treino
        item["zarc_oficial"] = linha["alvo"]
        item["zarc_menor_risco"] = int(linha["menor_risco"])
        item["zarc_oficial_nome"] = NOMES[linha["alvo"]]
        item["previsao_validacao"] = linha["random_forest"]
        item["previsao_validacao_nome"] = NOMES[linha["random_forest"]]

        # variaveis que explicam a recomendacao
        item["indicadores"] = {
            "soma_termica_120d": round(float(linha["gdd_120d"]), 1),
            "chuva_120d_mm": round(float(linha["chuva_120d"]), 1),
            "dias_acima_30_120d": round(float(linha["dias_acima_30_120d"]), 1),
            "dias_secos_120d": round(float(linha["dias_secos_120d"]), 1),
            "tmin_media_30d": round(float(linha["tmin_media_30d"]), 1),
            "dias_frio_30d": round(float(linha["dias_frio_30d"]), 1),
        }

        resposta["decendios"].append(item)
        posicao = posicao + 1

    return resposta


# importancia das variaveis do random forest, somada por tipo de fator
@app.get("/importancia")
def importancia():
    fatores = {
        "Temperatura": ["temp_media_hist", "temp_min_media_hist", "temp_max_media_hist", "gdd_safra_hist",
                        "dias_acima_30_hist", "dias_acima_35_hist", "gdd_120d", "dias_acima_30_120d",
                        "dias_acima_35_120d", "tmin_media_30d", "dias_frio_30d"],
        "Precipitação": ["chuva_safra_hist", "dias_secos_hist", "chuva_120d", "dias_secos_120d"],
        "Data de plantio": ["ordem_na_safra"],
        "Tipo de solo": ["cod_solo"],
        "Localização": ["latitude", "longitude"],
        "Histórico produtivo": ["rendimento_medio_hist"],
    }

    resposta = []
    for fator in fatores:
        total = 0
        for variavel in fatores[fator]:
            total = total + modelo.feature_importances_[VARIAVEIS.index(variavel)]
        resposta.append({"fator": fator, "importancia": round(float(total) * 100, 1)})

    resposta = sorted(resposta, key=lambda item: item["importancia"], reverse=True)
    return resposta
