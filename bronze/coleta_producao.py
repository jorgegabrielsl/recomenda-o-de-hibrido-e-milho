import time
import uuid
from datetime import datetime

import pandas as pd
import requests

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def buscar_producao(ano):
    url = "https://servicodados.ibge.gov.br/api/v3/agregados/1612/periodos/" + str(ano) + "/variaveis/109|216|214|112"
    params = {
        "localidades": "N6[N3[42]]",
        "classificacao": "81[2711]",
    }

    resposta = None
    for tentativa in range(3):
        try:
            resposta = requests.get(url, params=params, timeout=120)
            resposta.raise_for_status()
            break
        except requests.RequestException as erro:
            print("Erro no ano", ano, "tentativa", tentativa + 1, ":", erro)
            resposta = None
            time.sleep(5)

    if resposta is None:
        raise RuntimeError("Nao foi possivel coletar o ano " + str(ano))

    dados = resposta.json()
    linhas = []

    for variavel in dados:
        series = variavel["resultados"][0]["series"]
        for serie in series:
            linha = {}
            linha["id_municipio"] = int(serie["localidade"]["id"])
            linha["municipio"] = serie["localidade"]["nome"]
            linha["ano"] = ano
            linha["codigo_variavel"] = int(variavel["id"])
            linha["variavel"] = variavel["variavel"]
            linha["unidade"] = variavel["unidade"]
            linha["valor"] = serie["serie"][str(ano)]
            linhas.append(linha)

    return linhas


def coleta_producao(engine=None, anos=range(2015, 2026)):
    if engine is None:
        engine = conexao_pgsql()

    todas_linhas = []
    for ano in anos:
        linhas = buscar_producao(ano)
        print("Ano", ano, ":", len(linhas), "linhas")
        todas_linhas = todas_linhas + linhas
        time.sleep(2)

    df = pd.DataFrame(todas_linhas)
    df["fonte"] = "IBGE API Agregados v3 - tabela 1612"
    df["ts_carga"] = datetime.now()
    df["id_carga"] = str(uuid.uuid4())

    df.to_sql("producao", engine, schema="bronze", if_exists="append", index=False, chunksize=10000)
    criar_view_carga_atual(engine, "producao")
    print("Producao carregada:", len(df), "linhas")
    return df


if __name__ == "__main__":
    coleta_producao()
