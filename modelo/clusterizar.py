import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from config.db.conexao import conexao_pgsql

PASTA_RESULTADOS = "resultados"


def montar_dados(engine):
    # uma linha por municipio, so com clima, solo e producao (sem nada do ZARC)
    clima = pd.read_sql("""
        SELECT
            id_municipio,
            AVG(temp_media) AS temp_media,
            AVG(temp_min_media) AS temp_min_media,
            AVG(temp_max_media) AS temp_max_media,
            AVG(chuva_total_mm) AS chuva_safra,
            AVG(gdd) AS gdd_safra,
            AVG(dias_acima_30) AS dias_acima_30,
            AVG(dias_acima_35) AS dias_acima_35,
            AVG(dias_secos) AS dias_secos
        FROM silver.clima_safra
        WHERE janela_completa
        GROUP BY id_municipio
    """, engine)

    # frio no inicio da primavera (plantios de agosto e setembro)
    frio = pd.read_sql("""
        SELECT id_municipio, AVG(dias_frio_30d) AS dias_frio_inicio
        FROM silver.clima_decendio
        WHERE decendio BETWEEN 22 AND 27
        GROUP BY id_municipio
    """, engine)

    pam = pd.read_sql("""
        SELECT id_municipio, AVG(rendimento_kg_ha) AS rendimento_medio
        FROM silver.producao_milho
        WHERE rendimento_kg_ha > 0
        GROUP BY id_municipio
    """, engine)

    solo = pd.read_sql("SELECT id_municipio, ordem, proporcao FROM silver.solo_municipio", engine)
    solo["ordem"] = "solo_" + solo["ordem"].str.lower().str.replace(" ", "_")
    solo = solo.pivot_table(index="id_municipio", columns="ordem", values="proporcao", fill_value=0)
    solo = solo.reset_index()
    solo.columns.name = None

    municipio = pd.read_sql("SELECT id_municipio, municipio, mesorregiao FROM silver.municipio", engine)

    df = municipio.merge(clima, on="id_municipio", how="left")
    df = df.merge(frio, on="id_municipio", how="left")
    df = df.merge(pam, on="id_municipio", how="left")
    df = df.merge(solo, on="id_municipio", how="left")
    df["rendimento_medio"] = df["rendimento_medio"].fillna(0)
    return df


def montar_zarc(engine):
    # resumo do ZARC por municipio (solo tipo 2, safra 2025/26) para comparar depois
    # quase todos os municipios comecam a janela em 01/ago (com risco 40%),
    # entao o que diferencia e quando comeca o risco baixo (20%)
    zarc = pd.read_sql("""
        SELECT
            id_municipio,
            MIN(ordem_na_safra) AS inicio_janela,
            MIN(ordem_na_safra) FILTER (WHERE menor_risco = 20) AS inicio_risco_20,
            COUNT(*) AS decendios_indicados,
            SUM(CASE WHEN menor_risco = 20 THEN 1 ELSE 0 END) AS decendios_risco_20,
            SUM(CASE WHEN menor_risco = 40 THEN 1 ELSE 0 END) AS decendios_risco_40
        FROM gold.zarc_recomendacao
        WHERE safra_ini = 2025 AND cod_solo = 2
        GROUP BY id_municipio
    """, engine)

    # ordem na safra: 4 = 01/ago, 5 = 11/ago, 6 = 21/ago, 7 = 01/set ... 10 = 01/out
    zarc["inicio_risco_20_texto"] = "4 - outubro"
    zarc.loc[zarc["inicio_risco_20"] <= 9, "inicio_risco_20_texto"] = "3 - setembro"
    zarc.loc[zarc["inicio_risco_20"] <= 6, "inicio_risco_20_texto"] = "2 - 11 a 21/ago"
    zarc.loc[zarc["inicio_risco_20"] <= 4, "inicio_risco_20_texto"] = "1 - 01/ago"
    return zarc


def clusterizar(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    df = montar_dados(engine)
    variaveis = []
    for coluna in df.columns:
        if coluna not in ["id_municipio", "municipio", "mesorregiao"]:
            variaveis.append(coluna)

    # padroniza para todas as variaveis terem o mesmo peso
    X = StandardScaler().fit_transform(df[variaveis])

    # testa varios k
    metricas = []
    for k in range(2, 9):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        rotulos = kmeans.fit_predict(X)

        linha = {}
        linha["k"] = k
        linha["silhouette"] = round(silhouette_score(X, rotulos), 4)
        linha["davies_bouldin"] = round(davies_bouldin_score(X, rotulos), 4)
        linha["calinski_harabasz"] = round(calinski_harabasz_score(X, rotulos), 1)
        linha["inercia"] = round(kmeans.inertia_, 1)
        metricas.append(linha)

    metricas = pd.DataFrame(metricas)
    print(metricas.to_string(index=False))

    # grafico das metricas por k
    fig, eixos = plt.subplots(1, 4, figsize=(16, 3.5))
    eixos[0].plot(metricas["k"], metricas["inercia"], marker="o")
    eixos[0].set_title("Cotovelo (inercia)")
    eixos[1].plot(metricas["k"], metricas["silhouette"], marker="o")
    eixos[1].set_title("Silhouette (maior melhor)")
    eixos[2].plot(metricas["k"], metricas["davies_bouldin"], marker="o")
    eixos[2].set_title("Davies-Bouldin (menor melhor)")
    eixos[3].plot(metricas["k"], metricas["calinski_harabasz"], marker="o")
    eixos[3].set_title("Calinski-Harabasz (maior melhor)")
    for eixo in eixos:
        eixo.set_xlabel("k")
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "kmeans_escolha_k.png"), dpi=120)
    plt.close()

    # escolhe o k com maior silhouette
    melhor_k = int(metricas.loc[metricas["silhouette"].idxmax(), "k"])
    print("k escolhido (maior silhouette):", melhor_k)

    kmeans = KMeans(n_clusters=melhor_k, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(X) + 1

    # perfil de cada cluster (media das variaveis principais)
    perfil = df.groupby("cluster")[["temp_media", "temp_min_media", "gdd_safra", "chuva_safra",
                                     "dias_acima_30", "dias_frio_inicio", "rendimento_medio"]].mean().round(1)
    perfil["municipios"] = df.groupby("cluster")["id_municipio"].count()
    print()
    print("Perfil dos clusters:")
    print(perfil.to_string())

    # compara com o ZARC
    zarc = montar_zarc(engine)
    df = df.merge(zarc, on="id_municipio", how="left")

    print()
    print("Cluster x inicio do risco 20% no ZARC (quantidade de municipios):")
    tabela = pd.crosstab(df["cluster"], df["inicio_risco_20_texto"])
    print(tabela.to_string())

    print()
    print("Media do ZARC em cada cluster:")
    print(df.groupby("cluster")[["inicio_risco_20", "decendios_indicados", "decendios_risco_20", "decendios_risco_40"]].mean().round(1).to_string())

    # ARI: 0 = clusters nao tem relacao com o ZARC, 1 = iguais
    ari = adjusted_rand_score(df["inicio_risco_20_texto"], df["cluster"])
    print()
    print("Adjusted Rand Index (cluster x inicio do risco 20%):", round(ari, 4))

    # mapa lado a lado: clusters e inicio da janela do ZARC
    malha = gpd.read_postgis("SELECT id_municipio, geometry FROM bronze.vw_malha_municipal_atual", engine, geom_col="geometry")
    malha = malha.merge(df[["id_municipio", "cluster", "inicio_risco_20_texto"]], on="id_municipio")
    malha["cluster"] = malha["cluster"].astype(str)

    fig, eixos = plt.subplots(1, 2, figsize=(14, 6))
    malha.plot(column="cluster", categorical=True, legend=True, cmap="tab10", edgecolor="white", linewidth=0.2, ax=eixos[0])
    eixos[0].set_title("K-Means (so clima, solo e producao)")
    malha.plot(column="inicio_risco_20_texto", categorical=True, legend=True, cmap="viridis", edgecolor="white", linewidth=0.2, ax=eixos[1])
    eixos[1].set_title("ZARC: inicio do risco 20% (solo tipo 2)")
    for eixo in eixos:
        eixo.set_axis_off()
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "mapa_clusters_zarc.png"), dpi=120)
    plt.close()

    metricas["dt_processamento"] = pd.Timestamp.now()
    metricas.to_sql("kmeans_metricas", engine, schema="gold", if_exists="replace", index=False)

    saida = df[["id_municipio", "municipio", "mesorregiao", "cluster", "inicio_janela", "inicio_risco_20", "inicio_risco_20_texto",
                "decendios_indicados", "decendios_risco_20", "decendios_risco_40"]].copy()
    saida["dt_processamento"] = pd.Timestamp.now()
    saida.to_sql("clusters_municipio", engine, schema="gold", if_exists="replace", index=False)

    return df


if __name__ == "__main__":
    clusterizar()
