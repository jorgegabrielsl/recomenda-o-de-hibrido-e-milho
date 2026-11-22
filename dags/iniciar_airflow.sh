#!/bin/bash
# Sobe o Airflow no Ubuntu (WSL) usando a pasta dags/ do projeto.
# Rodar no terminal do Ubuntu:  bash /mnt/c/ETL/TCC/dags/iniciar_airflow.sh
# Depois abrir http://localhost:8080 (usuario admin; a senha aparece no terminal
# e fica salva em ~/airflow/simple_auth_manager_passwords.json.generated)

export AIRFLOW_HOME=~/airflow
export AIRFLOW__CORE__DAGS_FOLDER=/mnt/c/ETL/TCC/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False

source ~/airflow-venv/bin/activate
airflow standalone
