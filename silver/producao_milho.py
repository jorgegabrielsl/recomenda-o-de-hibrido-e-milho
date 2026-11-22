import pandas as pd

from config.db.conexao import conexao_pgsql


def converter_valor(valor):
    # codigos do IBGE: "-" = zero, "..." ou "X" = sem dado
    if valor == "-":
        return 0.0
    if valor == "..." or valor == "X" or valor == ".." or valor is None:
        return None
    return float(valor)


def producao_milho(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    df = pd.read_sql("SELECT id_municipio, ano, codigo_variavel, valor FROM bronze.vw_producao_atual", engine)
    df["valor"] = df["valor"].apply(converter_valor)

    # uma coluna para cada variavel
    tabela = df.pivot_table(index=["id_municipio", "ano"], columns="codigo_variavel", values="valor", aggfunc="first")
    tabela = tabela.reset_index()
    tabela = tabela.rename(columns={
        109: "area_plantada_ha",
        216: "area_colhida_ha",
        214: "producao_t",
        112: "rendimento_kg_ha",
    })
    tabela.columns.name = None
    tabela["dt_processamento"] = pd.Timestamp.now()

    tabela.to_sql("producao_milho", engine, schema="silver", if_exists="replace", index=False)
    print("silver.producao_milho:", len(tabela), "linhas")
    return tabela


if __name__ == "__main__":
    producao_milho()
