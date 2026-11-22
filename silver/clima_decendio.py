from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def clima_decendio(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # para cada municipio, ano e decendio: como foi o clima depois daquela data de plantio
    # decendio comeca no dia 1, 11 ou 21 de cada mes (dec1 = 01/jan, dec2 = 11/jan ...)
    # 30 dias = inicio do ciclo (emergencia), 120 dias = ciclo ate perto da maturacao
    sql = """
    WITH inicio AS (
        SELECT
            id_municipio,
            dia AS data_plantio,
            EXTRACT(YEAR FROM dia)::int AS ano,
            (EXTRACT(MONTH FROM dia)::int - 1) * 3 +
            CASE
                WHEN EXTRACT(DAY FROM dia) = 1 THEN 1
                WHEN EXTRACT(DAY FROM dia) = 11 THEN 2
                ELSE 3
            END AS decendio
        FROM silver.clima_diario
        WHERE EXTRACT(DAY FROM dia) IN (1, 11, 21)
    )
    SELECT
        i.id_municipio,
        i.ano,
        i.decendio,
        i.data_plantio,
        COUNT(d.dia) AS dias_com_dado,
        ROUND(SUM(d.gdd)::numeric, 1) AS gdd_120d,
        ROUND(SUM(d.chuva)::numeric, 1) AS chuva_120d,
        COUNT(*) FILTER (WHERE d.tmax > 30) AS dias_acima_30_120d,
        COUNT(*) FILTER (WHERE d.tmax > 35) AS dias_acima_35_120d,
        COUNT(*) FILTER (WHERE d.chuva < 1) AS dias_secos_120d,
        ROUND(AVG(d.tmin) FILTER (WHERE d.dia < i.data_plantio + 30)::numeric, 2) AS tmin_media_30d,
        COUNT(*) FILTER (WHERE d.dia < i.data_plantio + 30 AND d.tmin < 3) AS dias_frio_30d,
        NOW() AS dt_processamento
    FROM inicio i
    JOIN silver.clima_diario d
        ON d.id_municipio = i.id_municipio
       AND d.dia >= i.data_plantio
       AND d.dia < i.data_plantio + 120
    GROUP BY i.id_municipio, i.ano, i.decendio, i.data_plantio
    HAVING COUNT(d.dia) = 120
    """

    return recriar_tabela(engine, "silver.clima_decendio", sql)


if __name__ == "__main__":
    clima_decendio()
