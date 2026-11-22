import pandas as pd

from config.db.conexao import conexao_pgsql


def dataset_treino(engine=None, safra_zarc=2025):
    if engine is None:
        engine = conexao_pgsql()

    # o ZARC de SC e igual de 2020/21 ate 2025/26, entao usamos uma safra como referencia
    rec = pd.read_sql("""
        SELECT id_municipio, cod_solo, decendio, menor_risco, ciclos_menor_risco
        FROM gold.zarc_recomendacao
        WHERE safra_ini = """ + str(safra_zarc) + """
          AND classificacao_solo = 'tipos 1-3'
    """, engine)

    municipio = pd.read_sql("SELECT id_municipio, municipio, microrregiao, mesorregiao, latitude, longitude FROM silver.municipio", engine)

    # decendios que aparecem em pelo menos um municipio (a janela do estado)
    decendios = rec[["decendio"]].drop_duplicates()
    solos = pd.DataFrame({"cod_solo": [1, 2, 3]})

    # todas as combinacoes municipio x solo x decendio
    df = municipio.merge(solos, how="cross")
    df = df.merge(decendios, how="cross")

    df = df.merge(rec, on=["id_municipio", "cod_solo", "decendio"], how="left")

    # alvo: qual ciclo tem o menor risco, ou nao indicado
    df["alvo"] = "nao_indicado"
    df.loc[df["ciclos_menor_risco"] == "20", "alvo"] = "ciclo_20"
    df.loc[df["ciclos_menor_risco"] == "21", "alvo"] = "ciclo_21"
    df.loc[df["ciclos_menor_risco"] == "20,21", "alvo"] = "empate"
    df["menor_risco"] = df["menor_risco"].fillna(0)
    df = df.drop(columns=["ciclos_menor_risco"])

    df["ordem_na_safra"] = df["decendio"]
    df.loc[df["decendio"] >= 19, "ordem_na_safra"] = df["decendio"] - 18
    df.loc[df["decendio"] < 19, "ordem_na_safra"] = df["decendio"] + 18

    # clima medio historico de cada municipio (agosto a marco)
    clima = pd.read_sql("""
        SELECT
            id_municipio,
            AVG(temp_media) AS temp_media_hist,
            AVG(temp_min_media) AS temp_min_media_hist,
            AVG(temp_max_media) AS temp_max_media_hist,
            AVG(chuva_total_mm) AS chuva_safra_hist,
            AVG(gdd) AS gdd_safra_hist,
            AVG(dias_acima_30) AS dias_acima_30_hist,
            AVG(dias_acima_35) AS dias_acima_35_hist,
            AVG(dias_secos) AS dias_secos_hist
        FROM silver.clima_safra
        WHERE janela_completa
        GROUP BY id_municipio
    """, engine)
    df = df.merge(clima, on="id_municipio", how="left")

    # clima medio depois de cada data de plantio
    clima_dec = pd.read_sql("""
        SELECT
            id_municipio,
            decendio,
            AVG(gdd_120d) AS gdd_120d,
            AVG(chuva_120d) AS chuva_120d,
            AVG(dias_acima_30_120d) AS dias_acima_30_120d,
            AVG(dias_acima_35_120d) AS dias_acima_35_120d,
            AVG(dias_secos_120d) AS dias_secos_120d,
            AVG(tmin_media_30d) AS tmin_media_30d,
            AVG(dias_frio_30d) AS dias_frio_30d
        FROM silver.clima_decendio
        GROUP BY id_municipio, decendio
    """, engine)
    df = df.merge(clima_dec, on=["id_municipio", "decendio"], how="left")

    # rendimento medio historico da PAM
    pam = pd.read_sql("""
        SELECT id_municipio, AVG(rendimento_kg_ha) AS rendimento_medio_hist
        FROM silver.producao_milho
        WHERE rendimento_kg_ha > 0
        GROUP BY id_municipio
    """, engine)
    df = df.merge(pam, on="id_municipio", how="left")
    # municipio sem rendimento = nao produz milho
    df["rendimento_medio_hist"] = df["rendimento_medio_hist"].fillna(0)

    # proporcao de cada ordem de solo
    solo = pd.read_sql("SELECT id_municipio, ordem, proporcao FROM silver.solo_municipio", engine)
    solo["ordem"] = "solo_" + solo["ordem"].str.lower().str.replace(" ", "_")
    solo = solo.pivot_table(index="id_municipio", columns="ordem", values="proporcao", fill_value=0)
    solo = solo.reset_index()
    solo.columns.name = None
    df = df.merge(solo, on="id_municipio", how="left")

    df["safra_referencia_zarc"] = str(safra_zarc) + "/" + str(safra_zarc + 1)
    df["dt_processamento"] = pd.Timestamp.now()

    df = df.sort_values(["id_municipio", "cod_solo", "ordem_na_safra"])
    df.to_sql("dataset_treino", engine, schema="gold", if_exists="replace", index=False)

    print("gold.dataset_treino:", len(df), "linhas,", len(df.columns), "colunas")
    print(df["alvo"].value_counts())
    return df


if __name__ == "__main__":
    dataset_treino()
