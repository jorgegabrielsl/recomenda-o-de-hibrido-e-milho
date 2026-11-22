from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def municipio(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    sql = """
    SELECT
        m.id_municipio,
        m.municipio,
        m.microrregiao,
        m.mesorregiao,
        m.latitude,
        m.longitude,
        ROUND((ST_Area(g.geometry::geography) / 1000000)::numeric, 2) AS area_km2,
        NOW() AS dt_processamento
    FROM bronze.vw_municipio_atual m
    JOIN bronze.vw_malha_municipal_atual g ON g.id_municipio = m.id_municipio
    WHERE m.uf = 'SC'
    """

    return recriar_tabela(engine, "silver.municipio", sql)


if __name__ == "__main__":
    municipio()
