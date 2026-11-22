import pandas as pd

from config.db.conexao import conexao_pgsql


def nome_decendio(decendio):
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    partes = ["01-10", "11-20", "21-fim"]
    mes = meses[(decendio - 1) // 3]
    parte = partes[(decendio - 1) % 3]
    return parte + "/" + mes


# posicao do decendio contando a partir de julho, para ordenar a janela da safra
def ordem_na_safra(decendio):
    if decendio >= 19:
        return decendio - 18
    else:
        return decendio + 18


def zarc_risco(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    sql = """
        SELECT "SafraIni", "SafraFin", "Nome_cultura", "Cod_Ciclo", "Cod_Solo", "geocodigo", "Portaria",
               "dec1", "dec2", "dec3", "dec4", "dec5", "dec6", "dec7", "dec8", "dec9", "dec10", "dec11", "dec12",
               "dec13", "dec14", "dec15", "dec16", "dec17", "dec18", "dec19", "dec20", "dec21", "dec22", "dec23", "dec24",
               "dec25", "dec26", "dec27", "dec28", "dec29", "dec30", "dec31", "dec32", "dec33", "dec34", "dec35", "dec36"
        FROM bronze.vw_zarc_safras_atual
    """
    df = pd.read_sql(sql, engine)

    colunas_dec = []
    for i in range(1, 37):
        colunas_dec.append("dec" + str(i))

    # transforma as 36 colunas de decendio em linhas
    df = df.melt(
        id_vars=["SafraIni", "SafraFin", "Nome_cultura", "Cod_Ciclo", "Cod_Solo", "geocodigo", "Portaria"],
        value_vars=colunas_dec,
        var_name="decendio",
        value_name="risco",
    )

    df = df.rename(columns={
        "SafraIni": "safra_ini",
        "SafraFin": "safra_fim",
        "Nome_cultura": "cultura",
        "Cod_Ciclo": "cod_ciclo",
        "Cod_Solo": "cod_solo",
        "geocodigo": "id_municipio",
        "Portaria": "portaria",
    })

    df["safra_ini"] = df["safra_ini"].astype(int)
    df["safra_fim"] = df["safra_fim"].astype(int)
    df["cod_ciclo"] = df["cod_ciclo"].astype(int)
    df["cod_solo"] = df["cod_solo"].astype(int)
    df["id_municipio"] = df["id_municipio"].astype(int)
    df["risco"] = df["risco"].astype(int)
    df["decendio"] = df["decendio"].str.replace("dec", "").astype(int)

    # risco 0 = nao indicado
    df = df[df["risco"] > 0]

    df["safra"] = df["safra_ini"].astype(str) + "/" + df["safra_fim"].astype(str)
    df["periodo"] = df["decendio"].apply(nome_decendio)
    df["ordem_na_safra"] = df["decendio"].apply(ordem_na_safra)

    # a partir de 2026/2027 o ZARC usa solo 11 a 16 (AD1 a AD6) em vez de 1, 2 e 3
    df["classificacao_solo"] = "tipos 1-3"
    df.loc[df["cod_solo"] > 3, "classificacao_solo"] = "AD1-AD6"

    df["dt_processamento"] = pd.Timestamp.now()

    df = df[["safra", "safra_ini", "safra_fim", "id_municipio", "cultura", "cod_ciclo", "cod_solo",
             "classificacao_solo", "decendio", "periodo", "ordem_na_safra", "risco", "portaria", "dt_processamento"]]
    df = df.sort_values(["safra_ini", "id_municipio", "cod_solo", "cod_ciclo", "ordem_na_safra"])

    df.to_sql("zarc_risco", engine, schema="silver", if_exists="replace", index=False, chunksize=10000)
    print("silver.zarc_risco:", len(df), "linhas")
    return df


if __name__ == "__main__":
    zarc_risco()
