from datetime import datetime
from pathlib import Path
import uuid

import pandas as pd

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def coleta_zarc_safras(engine=None, diretorio=None):
    if engine is None:
        engine = conexao_pgsql()
    if diretorio is None:
        diretorio = Path(__file__).resolve().parents[1] / "data" / "externo"

    arquivos = sorted(Path(diretorio).glob("dados-abertos-tabua-de-risco-safra-20*.csv"))
    if len(arquivos) == 0:
        raise FileNotFoundError("Nenhum CSV do ZARC encontrado em " + str(diretorio))

    id_carga = str(uuid.uuid4())
    ts_carga = datetime.now()
    total = 0

    for arquivo in arquivos:
        linhas_arquivo = 0

        for lote in pd.read_csv(arquivo, sep=";", encoding="utf-8-sig", chunksize=300000, dtype=str):
            lote = lote[lote["UF"] == "SC"]
            lote = lote[lote["Nome_cultura"].str.contains("milho", case=False, na=False)]

            if len(lote) == 0:
                continue

            lote["arquivo_origem"] = arquivo.name
            lote["ts_carga"] = ts_carga
            lote["id_carga"] = id_carga

            lote.to_sql("zarc_safras", engine, schema="bronze", if_exists="append", index=False, chunksize=10000, method="multi")

            linhas_arquivo = linhas_arquivo + len(lote)
            total = total + len(lote)

        print(arquivo.name, ":", linhas_arquivo, "linhas")

    criar_view_carga_atual(engine, "zarc_safras")
    print("Tabuas de risco carregadas:", total, "linhas")
    return total


if __name__ == "__main__":
    coleta_zarc_safras()
