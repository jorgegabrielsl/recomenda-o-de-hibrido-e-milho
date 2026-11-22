from bronze.coleta_clima import coleta_clima
from bronze.coleta_malha import coleta_malha
from bronze.coleta_municipios import coleta_municipios
from bronze.coleta_producao import coleta_producao
from bronze.coleta_solo import coleta_solo
from bronze.coleta_zarc import coleta_zarc
from bronze.coleta_zarc_safras import coleta_zarc_safras
from config.db.conexao import conexao_pgsql


def main():
    engine = conexao_pgsql()
    try:
        coleta_municipios(engine)
        coleta_malha(engine)
        # clima demora bastante (1 requisicao por municipio), descomentar quando precisar atualizar
        # coleta_clima(engine)
        coleta_producao(engine)
        coleta_solo(engine)
        coleta_zarc_safras(engine)
        coleta_zarc(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
