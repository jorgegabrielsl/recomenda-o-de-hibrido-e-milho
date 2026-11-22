-- Estrutura inicial do banco. Rode uma vez, antes da primeira carga.
-- As tabelas são criadas pelos próprios scripts Python.
-- As views bronze.vw_*_atual são criadas automaticamente por cada coletor
-- (função criar_view_carga_atual em config/db/carga.py).

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS bronze;  -- dado bruto, com histórico de cargas (append + id_carga)
CREATE SCHEMA IF NOT EXISTS silver;  -- dado limpo e padronizado (recriado a cada execução)
CREATE SCHEMA IF NOT EXISTS gold;    -- dataset final e referência do ZARC (recriado a cada execução)
