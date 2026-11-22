import time
import uuid
from datetime import datetime

import pandas as pd
import requests

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def buscar_clima(id_municipio, latitude, longitude, inicio, fim):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR",
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": inicio,
        "end": fim,
        "format": "JSON",
    }

    # tenta ate 3 vezes
    for tentativa in range(3):
        try:
            resposta = requests.get(url, params=params, timeout=60)
        except requests.RequestException as erro:
            print("Erro no municipio", id_municipio, "tentativa", tentativa + 1, ":", erro)
            time.sleep(5)
            continue

        # 429 = muitas requisicoes, espera um pouco e tenta de novo
        if resposta.status_code == 429:
            print("Limite de requisicoes, esperando 30 segundos...")
            time.sleep(30)
            continue

        if resposta.status_code != 200:
            print("Status", resposta.status_code, "no municipio", id_municipio)
            return []

        dados = resposta.json()["properties"]["parameter"]

        registros = []
        for data in dados["T2M"]:
            temperatura = dados["T2M"][data]

            # -999 = sem dado na NASA POWER
            if temperatura == -999:
                continue

            registro = {}
            registro["id_municipio"] = id_municipio
            registro["data"] = data
            registro["temperatura_media"] = temperatura
            registro["temperatura_max"] = dados["T2M_MAX"][data]
            registro["temperatura_min"] = dados["T2M_MIN"][data]
            registro["precipitacao"] = dados["PRECTOTCORR"][data]
            registros.append(registro)

        return registros

    print("Falha na coleta do municipio", id_municipio)
    return []


def salvar_clima(registros, engine, id_carga, ts_carga):
    if len(registros) == 0:
        return

    df = pd.DataFrame(registros)
    df["ts_carga"] = ts_carga
    df["id_carga"] = id_carga
    df.to_sql("clima", engine, schema="bronze", if_exists="append", index=False, chunksize=10000)


def coleta_clima(engine=None, inicio="20150101", fim="20261231"):
    if engine is None:
        engine = conexao_pgsql()

    municipios = pd.read_sql("""
        SELECT DISTINCT
            id_municipio,
            ROUND(latitude::numeric, 2) AS latitude,
            ROUND(longitude::numeric, 2) AS longitude
        FROM bronze.vw_municipio_atual
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND uf = 'SC'
    """, engine)

    id_carga = str(uuid.uuid4())
    ts_carga = datetime.now()
    registros = []
    quantidade = 0

    print("Total de municipios:", len(municipios))

    # um municipio por vez
    for _, municipio in municipios.iterrows():
        dados = buscar_clima(municipio["id_municipio"], municipio["latitude"], municipio["longitude"], inicio, fim)
        registros = registros + dados
        quantidade = quantidade + 1
        print("Municipio", municipio["id_municipio"], ":", len(dados), "dias (", quantidade, "de", len(municipios), ")")

        # salva no banco a cada 50 municipios para nao acumular tudo na memoria
        if quantidade % 50 == 0:
            salvar_clima(registros, engine, id_carga, ts_carga)
            registros = []
            print("Lote salvo:", quantidade, "municipios")

    # salva o que sobrou
    salvar_clima(registros, engine, id_carga, ts_carga)

    criar_view_carga_atual(engine, "clima")
    print("Coleta de clima encerrada. id_carga:", id_carga)
    return id_carga


if __name__ == "__main__":
    coleta_clima()
