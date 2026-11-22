from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param

# o Airflow roda no Ubuntu (WSL), mas o projeto e o PostgreSQL ficam no Windows.
# o WSL consegue executar o python.exe do venv do Windows, entao cada tarefa
# so chama "python -m modulo", do mesmo jeito que e feito no terminal.
PASTA_PROJETO = "/mnt/c/ETL/TCC"
PYTHON = "./venv/Scripts/python.exe -X utf8"


def tarefa(dag, modulo):
    return BashOperator(
        task_id=modulo.replace(".", "_"),
        bash_command="cd " + PASTA_PROJETO + " && " + PYTHON + " -m " + modulo,
        dag=dag,
    )


argumentos = {
    "owner": "jorge",
    # as fontes externas podem ficar fora do ar (ex.: apisidra com HTTP 403),
    # entao cada tarefa tenta de novo antes de falhar
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="pipeline_milho_sc",
    description="Bronze, Silver, Gold e modelos do TCC (recomendacao de grupos de milho em SC)",
    default_args=argumentos,
    start_date=datetime(2026, 11, 1),
    schedule="@monthly",
    catchup=False,
    # no maximo 3 tarefas ao mesmo tempo (SISZARC e solo usam muita memoria)
    max_active_tasks=3,
    # uma execucao por vez: duas ao mesmo tempo gravam nas mesmas tabelas
    max_active_runs=1,
    params={"atualizar_clima": Param(False, type="boolean", description="Coletar de novo o clima da NASA POWER (15 a 25 min)")},
    tags=["tcc", "milho"],
)

# ---------- Bronze ----------
b_municipios = tarefa(dag, "bronze.coleta_municipios")
b_malha = tarefa(dag, "bronze.coleta_malha")
b_producao = tarefa(dag, "bronze.coleta_producao")
b_solo = tarefa(dag, "bronze.coleta_solo")
b_zarc_safras = tarefa(dag, "bronze.coleta_zarc_safras")
b_zarc = tarefa(dag, "bronze.coleta_zarc")

# o clima so e coletado quando o parametro atualizar_clima for marcado
b_clima = BashOperator(
    task_id="bronze_coleta_clima",
    bash_command="""
    if [ "{{ params.atualizar_clima }}" = "True" ]; then
        cd """ + PASTA_PROJETO + " && " + PYTHON + """ -m bronze.coleta_clima
    else
        echo "Clima nao atualizado (atualizar_clima = False)"
    fi
    """,
    dag=dag,
)

# ---------- Silver ----------
s_municipio = tarefa(dag, "silver.municipio")
s_clima_safra = tarefa(dag, "silver.clima_safra")
s_clima_diario = tarefa(dag, "silver.clima_diario")
s_clima_decendio = tarefa(dag, "silver.clima_decendio")
s_producao = tarefa(dag, "silver.producao_milho")
s_solo = tarefa(dag, "silver.solo_municipio")
s_zarc_risco = tarefa(dag, "silver.zarc_risco")
s_siszarc = tarefa(dag, "silver.siszarc_cultivares")

# ---------- Gold ----------
g_municipio_safra = tarefa(dag, "gold.dataset_municipio_safra")
g_referencia_zarc = tarefa(dag, "gold.referencia_zarc")
g_dataset_treino = tarefa(dag, "gold.dataset_treino")
g_qualidade = tarefa(dag, "gold.qualidade")

# ---------- Modelos ----------
m_treinar = tarefa(dag, "modelo.treinar")
m_clusterizar = tarefa(dag, "modelo.clusterizar")
m_comparar = tarefa(dag, "modelo.comparar_modelos")

# dependencias
b_municipios >> [b_malha, b_clima, b_producao, b_solo, b_zarc_safras, b_zarc]

[b_municipios, b_malha] >> s_municipio
s_municipio >> [s_clima_safra, s_clima_diario, s_producao, s_solo, s_zarc_risco, s_siszarc]
b_clima >> [s_clima_safra, s_clima_diario]
s_clima_diario >> s_clima_decendio
b_producao >> s_producao
b_solo >> s_solo
b_zarc_safras >> s_zarc_risco
b_zarc >> s_siszarc

[s_clima_safra, s_producao, s_solo] >> g_municipio_safra
s_zarc_risco >> g_referencia_zarc
[g_referencia_zarc, s_clima_safra, s_clima_decendio, s_producao, s_solo] >> g_dataset_treino
[g_municipio_safra, g_dataset_treino, s_siszarc] >> g_qualidade

g_dataset_treino >> [m_treinar, m_comparar]
[s_clima_safra, s_clima_decendio, s_producao, s_solo, g_referencia_zarc] >> m_clusterizar
