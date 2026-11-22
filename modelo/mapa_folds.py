import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.model_selection import GroupKFold

from config.db.conexao import conexao_pgsql

PASTA_RESULTADOS = "resultados"


# mapa das 5 divisoes do GroupKFold (mesma divisao usada em treinar.py e comparar_modelos.py)
def mapa_folds(engine=None):
    if engine is None:
        engine = conexao_pgsql()
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    df = pd.read_sql("SELECT id_municipio, microrregiao, alvo FROM gold.dataset_treino", engine)

    # o GroupKFold so depende do nome e do tamanho de cada microrregiao
    kfold = GroupKFold(n_splits=5)
    df["divisao"] = 0
    for numero, (_, indices_teste) in enumerate(kfold.split(df, df["alvo"], df["microrregiao"]), start=1):
        df.loc[indices_teste, "divisao"] = numero

    municipios = df[["id_municipio", "microrregiao", "divisao"]].drop_duplicates()

    resumo = municipios.groupby("divisao").agg(
        microrregioes=("microrregiao", "nunique"),
        municipios=("id_municipio", "count"),
    )
    print(resumo.to_string())
    print()
    for numero in sorted(municipios["divisao"].unique()):
        nomes = sorted(municipios.loc[municipios["divisao"] == numero, "microrregiao"].unique())
        print("Divisão", numero, ":", ", ".join(nomes))

    malha = gpd.read_postgis("SELECT id_municipio, geometry FROM bronze.vw_malha_municipal_atual", engine, geom_col="geometry")
    malha = malha.merge(municipios, on="id_municipio")
    malha["divisao_texto"] = "Divisão " + malha["divisao"].astype(str)

    # contorno de cada microrregiao juntando os municipios
    contorno = malha.dissolve(by="microrregiao").reset_index()

    fig, ax = plt.subplots(figsize=(11, 7))
    malha.plot(column="divisao_texto", categorical=True, legend=True, cmap="Set2", edgecolor="white", linewidth=0.2, ax=ax,
               legend_kwds={"loc": "lower left", "title": "Teste em cada divisão"})
    contorno.boundary.plot(ax=ax, color="#333333", linewidth=0.8)
    for _, linha in contorno.iterrows():
        ponto = linha["geometry"].representative_point()
        ax.annotate(linha["microrregiao"], (ponto.x, ponto.y), ha="center", fontsize=6.5, color="#222222")
    ax.set_title("Divisões da validação cruzada por microrregião (GroupKFold, 5 divisões)")
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "mapa_folds_microrregiao.png"), dpi=200)
    plt.close()

    return municipios


if __name__ == "__main__":
    mapa_folds()
