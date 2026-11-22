from datetime import datetime
import uuid

import pandas as pd
import requests

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def coleta_municipios(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()
    data = resposta.json()

    df = pd.json_normalize(data)

    df = df[[
        "id",
        "nome",
        "microrregiao.nome",
        "microrregiao.mesorregiao.nome",
        "microrregiao.mesorregiao.UF.sigla",
        "microrregiao.mesorregiao.UF.regiao.nome"
    ]]

    df.columns = [
        "id_municipio",
        "municipio",
        "microrregiao",
        "mesorregiao",
        "uf",
        "regiao"
    ]

    coord = pd.read_csv("https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/master/csv/municipios.csv")

    coord = coord[["codigo_ibge", "latitude", "longitude"]]

    coord.columns = ["id_municipio", "latitude", "longitude"]

    df = df.merge(coord, on="id_municipio", how="left")

    df["ts_carga"] = datetime.now()
    df["id_carga"] = str(uuid.uuid4())

    df.to_sql(
        "municipio", engine, schema="bronze", if_exists="append",
        index=False, chunksize=10000,
    )

    criar_view_carga_atual(engine, "municipio")
    print(f"Municípios carregados: {len(df)} linhas")
    return df


if __name__ == "__main__":
    coleta_municipios()
