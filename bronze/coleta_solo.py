from pathlib import Path
from datetime import datetime
import uuid

import geopandas as gpd

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def coleta_solo(engine=None, caminho=None):
    if engine is None:
        engine = conexao_pgsql()
    if caminho is None:
        caminho = Path(__file__).resolve().parents[1] / "data" / "externo" / "pedo_area.shp"

    gdf = gpd.read_file(caminho).to_crs(epsg=4326)
    gdf["ts_carga"] = datetime.now()
    gdf["id_carga"] = str(uuid.uuid4())
    gdf.to_postgis(
        "dados_solo", engine, schema="bronze", if_exists="append", chunksize=10000,
    )

    criar_view_carga_atual(engine, "dados_solo")
    print(f"Solo carregado: {len(gdf)} polígonos")
    return gdf


if __name__ == "__main__":
    coleta_solo()
