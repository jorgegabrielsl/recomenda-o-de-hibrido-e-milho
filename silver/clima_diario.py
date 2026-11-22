from sqlalchemy import text

from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def clima_diario(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # clima de cada dia ja limpo, com a soma termica do dia (base 10 e teto 30)
    sql = """
    SELECT
        id_municipio,
        TO_DATE(data, 'YYYYMMDD') AS dia,
        NULLIF(temperatura_media, -999) AS tmed,
        NULLIF(temperatura_max, -999) AS tmax,
        NULLIF(temperatura_min, -999) AS tmin,
        NULLIF(precipitacao, -999) AS chuva,
        GREATEST(0, (LEAST(NULLIF(temperatura_max, -999), 30) + GREATEST(NULLIF(temperatura_min, -999), 10)) / 2 - 10) AS gdd
    FROM bronze.vw_clima_atual
    """

    total = recriar_tabela(engine, "silver.clima_diario", sql)

    # indice para as consultas por municipio e data ficarem rapidas
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX ix_clima_diario ON silver.clima_diario (id_municipio, dia)"))

    return total


if __name__ == "__main__":
    clima_diario()
