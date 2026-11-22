from config.db.conexao import conexao_pgsql
from gold.dataset_municipio_safra import dataset_municipio_safra
from gold.dataset_treino import dataset_treino
from gold.qualidade import qualidade
from gold.referencia_zarc import referencia_zarc


def main():
    engine = conexao_pgsql()
    try:
        dataset_municipio_safra(engine)
        referencia_zarc(engine)
        dataset_treino(engine)
        qualidade(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
