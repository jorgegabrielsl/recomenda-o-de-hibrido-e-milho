from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def clima_safra(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # safra = agosto ate marco do ano seguinte (ex: 2023/2024 = 01/08/2023 a 31/03/2024)
    # -999 na NASA POWER significa sem dado
    # soma termica (graus-dia): base 10 e teto 30, minima abaixo de 10 conta como 10
    sql = """
    WITH diario AS (
        SELECT
            id_municipio,
            TO_DATE(data, 'YYYYMMDD') AS dia,
            NULLIF(temperatura_media, -999) AS tmed,
            NULLIF(temperatura_max, -999) AS tmax,
            NULLIF(temperatura_min, -999) AS tmin,
            NULLIF(precipitacao, -999) AS chuva
        FROM bronze.vw_clima_atual
    ),
    janela AS (
        SELECT
            *,
            CASE
                WHEN EXTRACT(MONTH FROM dia) >= 8 THEN EXTRACT(YEAR FROM dia)::int
                ELSE EXTRACT(YEAR FROM dia)::int - 1
            END AS safra_ini
        FROM diario
        WHERE EXTRACT(MONTH FROM dia) >= 8
           OR EXTRACT(MONTH FROM dia) <= 3
    ),
    agregado AS (
        SELECT
            id_municipio,
            safra_ini,
            safra_ini + 1 AS safra_fim,
            safra_ini || '/' || (safra_ini + 1) AS safra,
            COUNT(*) AS dias_com_dado,
            MAKE_DATE(safra_ini + 1, 4, 1) - MAKE_DATE(safra_ini, 8, 1) AS dias_esperados,
            ROUND(AVG(tmed)::numeric, 2) AS temp_media,
            ROUND(AVG(tmax)::numeric, 2) AS temp_max_media,
            ROUND(AVG(tmin)::numeric, 2) AS temp_min_media,
            ROUND(MAX(tmax)::numeric, 2) AS temp_max_absoluta,
            ROUND(MIN(tmin)::numeric, 2) AS temp_min_absoluta,
            ROUND(SUM(chuva)::numeric, 1) AS chuva_total_mm,
            COUNT(*) FILTER (WHERE chuva < 1) AS dias_secos,
            COUNT(*) FILTER (WHERE tmax > 30) AS dias_acima_30,
            COUNT(*) FILTER (WHERE tmax > 35) AS dias_acima_35,
            ROUND(SUM(GREATEST(0, (LEAST(tmax, 30) + GREATEST(tmin, 10)) / 2 - 10))::numeric, 1) AS gdd,
            NOW() AS dt_processamento
        FROM janela
        GROUP BY id_municipio, safra_ini
    )
    SELECT
        *,
        (dias_com_dado = dias_esperados) AS janela_completa
    FROM agregado
    """

    return recriar_tabela(engine, "silver.clima_safra", sql)


if __name__ == "__main__":
    clima_safra()
