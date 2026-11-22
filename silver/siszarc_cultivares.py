from config.db.carga import recriar_tabela
from config.db.conexao import conexao_pgsql


def siszarc_cultivares(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    # o arquivo do SISZARC repete cada cultivar com todos os obtentores e todos os grupos
    # entao so a lista de cultivares por safra e confiavel
    sql = """
    SELECT
        "Safra" AS safra,
        "Cultivar" AS cultivar,
        COUNT(DISTINCT "Obtentor_Mantenedor") AS qtd_obtentores,
        COUNT(DISTINCT "Grupo") AS qtd_grupos,
        COUNT(*) AS linhas_no_arquivo,
        NOW() AS dt_processamento
    FROM bronze.vw_zarc_atual
    GROUP BY 1, 2
    """

    return recriar_tabela(engine, "silver.siszarc_cultivares", sql)


if __name__ == "__main__":
    siszarc_cultivares()
