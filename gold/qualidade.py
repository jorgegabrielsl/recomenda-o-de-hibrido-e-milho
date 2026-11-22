import pandas as pd

from config.db.conexao import conexao_pgsql


def qualidade(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # tabela, colunas da chave, coluna de periodo
    tabelas = [
        ("silver.municipio", ["id_municipio"], None),
        ("silver.clima_safra", ["id_municipio", "safra_ini"], "safra_ini"),
        ("silver.clima_decendio", ["id_municipio", "ano", "decendio"], "ano"),
        ("silver.producao_milho", ["id_municipio", "ano"], "ano"),
        ("silver.solo_municipio", ["id_municipio", "ordem"], None),
        ("silver.solo_textura_municipio", ["id_municipio", "textura"], None),
        ("silver.zarc_risco", ["safra_ini", "id_municipio", "cod_ciclo", "cod_solo", "decendio"], "safra_ini"),
        ("silver.siszarc_cultivares", ["safra", "cultivar"], "safra"),
        ("gold.dataset_municipio_safra", ["id_municipio", "safra_ini"], "safra_ini"),
        ("gold.zarc_janela", ["safra_ini", "id_municipio", "cod_solo", "cod_ciclo"], "safra_ini"),
        ("gold.zarc_recomendacao", ["safra_ini", "id_municipio", "cod_solo", "decendio"], "safra_ini"),
        ("gold.dataset_treino", ["id_municipio", "cod_solo", "decendio"], None),
    ]

    resultado = []

    for tabela, chave, periodo in tabelas:
        df = pd.read_sql("SELECT * FROM " + tabela, engine)

        linha = {}
        linha["tabela"] = tabela
        linha["linhas"] = len(df)
        linha["repetidas_na_chave"] = int(df.duplicated(chave).sum())

        if "id_municipio" in df.columns:
            linha["municipios"] = df["id_municipio"].nunique()
        else:
            linha["municipios"] = None

        if periodo is not None:
            linha["periodo_inicio"] = str(df[periodo].min())
            linha["periodo_fim"] = str(df[periodo].max())
        else:
            linha["periodo_inicio"] = None
            linha["periodo_fim"] = None

        # colunas que tem valor vazio
        vazios = []
        for coluna in df.columns:
            qtd = df[coluna].isna().sum()
            if qtd > 0:
                vazios.append(coluna + " (" + str(qtd) + ")")
        if len(vazios) == 0:
            linha["colunas_com_vazios"] = "nenhuma"
        else:
            linha["colunas_com_vazios"] = ", ".join(vazios)

        resultado.append(linha)

    relatorio = pd.DataFrame(resultado)
    relatorio["dt_processamento"] = pd.Timestamp.now()
    relatorio.to_sql("qualidade_dados", engine, schema="gold", if_exists="replace", index=False)

    for linha in resultado:
        print(linha["tabela"], "| linhas:", linha["linhas"], "| repetidas:", linha["repetidas_na_chave"],
              "| municipios:", linha["municipios"], "| vazios:", linha["colunas_com_vazios"])

    return relatorio


if __name__ == "__main__":
    qualidade()
