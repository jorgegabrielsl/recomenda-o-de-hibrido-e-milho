from datetime import datetime
from pathlib import Path
import uuid

import pandas as pd

from config.db.carga import criar_view_carga_atual
from config.db.conexao import conexao_pgsql


def coleta_zarc(engine=None, caminho=None):
    if engine is None:
        engine = conexao_pgsql()
    if caminho is None:
        caminho = Path(__file__).resolve().parents[1] / "data" / "externo" / "siszarc_cronograma.csv"

    id_carga = str(uuid.uuid4())
    ts_carga = datetime.now()
    total = 0

    # arquivo muito grande, por isso le em partes
    for lote in pd.read_csv(caminho, sep=";", encoding="utf-8-sig", chunksize=500000, dtype=str):
        lote = lote[lote["UF"] == "SC"]
        lote = lote[lote["Cultura"].str.contains("milho", case=False, na=False)]

        if len(lote) == 0:
            continue

        lote["ts_carga"] = ts_carga
        lote["id_carga"] = id_carga

        lote.to_sql("zarc", engine, schema="bronze", if_exists="append", index=False, chunksize=10000, method="multi")

        total = total + len(lote)
        print(total, "linhas gravadas")

    criar_view_carga_atual(engine, "zarc")
    print("SISZARC carregado:", total, "linhas")
    return total


if __name__ == "__main__":
    coleta_zarc()
