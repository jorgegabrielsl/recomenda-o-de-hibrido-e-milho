from sqlalchemy import text


# cria a view com a ultima carga da tabela do bronze
def criar_view_carga_atual(engine, tabela, schema="bronze"):
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_" + tabela + "_ts_carga ON " + schema + "." + tabela + " (ts_carga)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_" + tabela + "_id_carga ON " + schema + "." + tabela + " (id_carga)"))
        conn.execute(text("DROP VIEW IF EXISTS " + schema + ".vw_" + tabela + "_atual"))

        sql = """
            CREATE VIEW {schema}.vw_{tabela}_atual AS
            SELECT *
            FROM {schema}.{tabela}
            WHERE id_carga = (
                SELECT id_carga
                FROM {schema}.{tabela}
                ORDER BY ts_carga DESC
                LIMIT 1
            )
        """.format(schema=schema, tabela=tabela)
        conn.execute(text(sql))

    print("View " + schema + ".vw_" + tabela + "_atual criada")


# apaga a tabela e cria de novo com o resultado do select (silver e gold)
def recriar_tabela(engine, tabela, select_sql):
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS " + tabela))
        conn.execute(text("CREATE TABLE " + tabela + " AS " + select_sql))
        total = conn.execute(text("SELECT COUNT(*) FROM " + tabela)).scalar()

    print(tabela + ": " + str(total) + " linhas")
    return total
