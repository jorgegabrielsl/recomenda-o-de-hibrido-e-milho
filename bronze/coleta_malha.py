import uuid
from datetime import datetime

import geopandas as gpd
import requests

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def coleta_malha(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # poligonos dos municipios de SC (codigo 42)
    url = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/42"
    params = {
        "formato": "application/vnd.geo+json",
        "intrarregiao": "municipio",
        "qualidade": "intermediaria",
    }

    resposta = requests.get(url, params=params, timeout=120)
    resposta.raise_for_status()
    dados = resposta.json()

    gdf = gpd.GeoDataFrame.from_features(dados["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"codarea": "id_municipio"})
    gdf["id_municipio"] = gdf["id_municipio"].astype(int)
    gdf["ts_carga"] = datetime.now()
    gdf["id_carga"] = str(uuid.uuid4())

    gdf.to_postgis("malha_municipal", engine, schema="bronze", if_exists="append")
    criar_view_carga_atual(engine, "malha_municipal")
    print("Malha carregada:", len(gdf), "municipios")
    return gdf


if __name__ == "__main__":
    coleta_malha()
