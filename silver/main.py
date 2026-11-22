from config.db.conexao import conexao_pgsql
from silver.clima_decendio import clima_decendio
from silver.clima_diario import clima_diario
from silver.clima_safra import clima_safra
from silver.municipio import municipio
from silver.producao_milho import producao_milho
from silver.siszarc_cultivares import siszarc_cultivares
from silver.solo_municipio import solo_municipio
from silver.zarc_risco import zarc_risco


def main():
    engine = conexao_pgsql()
    try:
        municipio(engine)
        clima_safra(engine)
        clima_diario(engine)
        clima_decendio(engine)
        producao_milho(engine)
        solo_municipio(engine)
        zarc_risco(engine)
        siszarc_cultivares(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
