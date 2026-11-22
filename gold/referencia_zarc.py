import pandas as pd

from config.db.conexao import conexao_pgsql


# janela de plantio de cada ciclo: inicio, fim e quantos decendios em cada risco
def zarc_janela(risco, engine):
    chave = ["safra", "safra_ini", "id_municipio", "cod_solo", "classificacao_solo", "cod_ciclo"]

    df = risco.sort_values("ordem_na_safra")
    df["risco_20"] = (df["risco"] == 20).astype(int)
    df["risco_30"] = (df["risco"] == 30).astype(int)
    df["risco_40"] = (df["risco"] == 40).astype(int)

    janela = df.groupby(chave).agg(
        inicio_janela=("periodo", "first"),
        fim_janela=("periodo", "last"),
        decendios_indicados=("risco", "count"),
        decendios_risco_20=("risco_20", "sum"),
        decendios_risco_30=("risco_30", "sum"),
        decendios_risco_40=("risco_40", "sum"),
    )
    janela = janela.reset_index()
    janela["dt_processamento"] = pd.Timestamp.now()

    janela.to_sql("zarc_janela", engine, schema="gold", if_exists="replace", index=False)
    print("gold.zarc_janela:", len(janela), "linhas")
    return janela


# para cada decendio: qual o menor risco e quais ciclos tem esse menor risco
def zarc_recomendacao(risco, engine):
    chave = ["safra", "safra_ini", "id_municipio", "cod_solo", "classificacao_solo", "decendio", "periodo", "ordem_na_safra"]

    menor = risco.groupby(chave)["risco"].min().reset_index()
    menor = menor.rename(columns={"risco": "menor_risco"})

    df = risco.merge(menor, on=chave)

    total_ciclos = df.groupby(chave)["cod_ciclo"].count().reset_index()
    total_ciclos = total_ciclos.rename(columns={"cod_ciclo": "ciclos_indicados"})

    # so os ciclos que tem o menor risco
    melhores = df[df["risco"] == df["menor_risco"]]
    melhores = melhores.sort_values("cod_ciclo")
    melhores["cod_ciclo"] = melhores["cod_ciclo"].astype(str)

    lista = melhores.groupby(chave).agg(
        ciclos_menor_risco=("cod_ciclo", ",".join),
        qtd_ciclos_menor_risco=("cod_ciclo", "count"),
    )
    lista = lista.reset_index()

    rec = menor.merge(total_ciclos, on=chave)
    rec = rec.merge(lista, on=chave)

    # empate = mais de um ciclo indicado e todos com o mesmo risco
    # (se so um ciclo e indicado, nao e empate)
    rec["empate"] = (rec["qtd_ciclos_menor_risco"] > 1) & (rec["qtd_ciclos_menor_risco"] == rec["ciclos_indicados"])
    rec["dt_processamento"] = pd.Timestamp.now()

    rec.to_sql("zarc_recomendacao", engine, schema="gold", if_exists="replace", index=False, chunksize=10000)
    sem_empate = len(rec[rec["empate"] == False])
    print("gold.zarc_recomendacao:", len(rec), "linhas -", sem_empate, "sem empate")
    return rec


def referencia_zarc(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    risco = pd.read_sql("""
        SELECT safra, safra_ini, id_municipio, cod_solo, classificacao_solo, cod_ciclo,
               decendio, periodo, ordem_na_safra, risco
        FROM silver.zarc_risco
    """, engine)

    zarc_janela(risco, engine)
    zarc_recomendacao(risco, engine)


if __name__ == "__main__":
    referencia_zarc()
