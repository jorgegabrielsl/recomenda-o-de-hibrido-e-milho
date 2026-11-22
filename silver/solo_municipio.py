from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def solo_municipio(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # cruza o poligono do municipio com o mapa de solos e calcula quanto de area tem cada classe
    sql_ordem = """
    WITH intersecao AS (
        SELECT
            m.id_municipio,
            COALESCE(s.ordem, 'SEM CLASSE') AS classe,
            ST_Area(ST_Intersection(m.geometry, ST_MakeValid(s.geometry))::geography) / 1000000 AS area_km2
        FROM bronze.vw_malha_municipal_atual m
        JOIN bronze.vw_dados_solo_atual s ON ST_Intersects(m.geometry, s.geometry)
    ),
    por_classe AS (
        SELECT id_municipio, classe, SUM(area_km2) AS area_km2
        FROM intersecao
        GROUP BY id_municipio, classe
    )
    SELECT
        id_municipio,
        classe AS ordem,
        ROUND(area_km2::numeric, 3) AS area_km2,
        ROUND((area_km2 / SUM(area_km2) OVER (PARTITION BY id_municipio))::numeric, 4) AS proporcao,
        NOW() AS dt_processamento
    FROM por_classe
    """

    # mesma coisa mas pela textura (para comparar com os tipos de solo do ZARC)
    sql_textura = """
    WITH intersecao AS (
        SELECT
            m.id_municipio,
            COALESCE(s.textura, 'SEM CLASSE') AS classe,
            ST_Area(ST_Intersection(m.geometry, ST_MakeValid(s.geometry))::geography) / 1000000 AS area_km2
        FROM bronze.vw_malha_municipal_atual m
        JOIN bronze.vw_dados_solo_atual s ON ST_Intersects(m.geometry, s.geometry)
    ),
    por_classe AS (
        SELECT id_municipio, classe, SUM(area_km2) AS area_km2
        FROM intersecao
        GROUP BY id_municipio, classe
    )
    SELECT
        id_municipio,
        classe AS textura,
        ROUND(area_km2::numeric, 3) AS area_km2,
        ROUND((area_km2 / SUM(area_km2) OVER (PARTITION BY id_municipio))::numeric, 4) AS proporcao,
        NOW() AS dt_processamento
    FROM por_classe
    """

    recriar_tabela(engine, "silver.solo_municipio", sql_ordem)
    recriar_tabela(engine, "silver.solo_textura_municipio", sql_textura)


if __name__ == "__main__":
    solo_municipio()
