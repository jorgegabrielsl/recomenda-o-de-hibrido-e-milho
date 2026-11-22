import pandas as pd

from config.db.conexao import conexao_pgsql


def dataset_municipio_safra(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    municipio = pd.read_sql("SELECT id_municipio, municipio, mesorregiao, latitude, longitude, area_km2 FROM silver.municipio", engine)

    # so as safras com todos os dias de agosto a marco
    clima = pd.read_sql("""
        SELECT id_municipio, safra, safra_ini, safra_fim, temp_media, temp_max_media,
               temp_min_media, temp_max_absoluta, temp_min_absoluta, chuva_total_mm,
               dias_secos, dias_acima_30, dias_acima_35, gdd
        FROM silver.clima_safra
        WHERE janela_completa
    """, engine)

    producao = pd.read_sql("SELECT id_municipio, ano, area_plantada_ha, area_colhida_ha, producao_t, rendimento_kg_ha FROM silver.producao_milho", engine)

    # solo: uma coluna para cada ordem de solo com a proporcao da area
    solo = pd.read_sql("SELECT id_municipio, ordem, proporcao FROM silver.solo_municipio", engine)
    solo["ordem"] = "solo_" + solo["ordem"].str.lower().str.replace(" ", "_")
    solo = solo.pivot_table(index="id_municipio", columns="ordem", values="proporcao", fill_value=0)
    solo = solo.reset_index()
    solo.columns.name = None

    df = clima.merge(municipio, on="id_municipio", how="left")

    # PAM do ano que a safra termina (safra 2023/2024 -> PAM 2024)
    df = df.merge(producao, left_on=["id_municipio", "safra_fim"], right_on=["id_municipio", "ano"], how="left")
    df = df.drop(columns=["ano"])

    # PAM do ano anterior (ja se sabe antes de plantar)
    anterior = producao.rename(columns={
        "area_plantada_ha": "area_plantada_ha_ano_anterior",
        "area_colhida_ha": "area_colhida_ha_ano_anterior",
        "producao_t": "producao_t_ano_anterior",
        "rendimento_kg_ha": "rendimento_kg_ha_ano_anterior",
    })
    df = df.merge(anterior, left_on=["id_municipio", "safra_ini"], right_on=["id_municipio", "ano"], how="left")
    df = df.drop(columns=["ano"])

    df = df.merge(solo, on="id_municipio", how="left")
    df["dt_processamento"] = pd.Timestamp.now()

    # conferencia: o join nao pode ter duplicado linhas
    if len(df) != len(clima):
        print("ATENCAO: o join duplicou linhas!", len(clima), "->", len(df))

    df = df.sort_values(["safra_ini", "id_municipio"])
    df.to_sql("dataset_municipio_safra", engine, schema="gold", if_exists="replace", index=False)
    print("gold.dataset_municipio_safra:", len(df), "linhas,", len(df.columns), "colunas")
    return df


if __name__ == "__main__":
    dataset_municipio_safra()
