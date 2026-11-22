import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, ConfusionMatrixDisplay, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier

from config.db.conexao import conexao_pgsql

PASTA_RESULTADOS = "resultados"

VARIAVEIS = [
    "latitude", "longitude", "cod_solo", "ordem_na_safra",
    "temp_media_hist", "temp_min_media_hist", "temp_max_media_hist", "chuva_safra_hist",
    "gdd_safra_hist", "dias_acima_30_hist", "dias_acima_35_hist", "dias_secos_hist",
    "gdd_120d", "chuva_120d", "dias_acima_30_120d", "dias_acima_35_120d", "dias_secos_120d",
    "tmin_media_30d", "dias_frio_30d", "rendimento_medio_hist",
]


# baseline: copia a resposta do municipio de treino mais perto
def prever_vizinho(treino, teste):
    mun_treino = treino[["id_municipio", "latitude", "longitude"]].drop_duplicates()
    mun_teste = teste[["id_municipio", "latitude", "longitude"]].drop_duplicates()

    vizinho = {}
    for _, m in mun_teste.iterrows():
        dist = (mun_treino["latitude"] - m["latitude"]) ** 2 + (mun_treino["longitude"] - m["longitude"]) ** 2
        mais_perto = mun_treino.loc[dist.idxmin(), "id_municipio"]
        vizinho[m["id_municipio"]] = mais_perto

    resposta = teste[["id_municipio", "cod_solo", "decendio"]].copy()
    resposta["id_vizinho"] = resposta["id_municipio"].map(vizinho)

    alvo_vizinho = treino[["id_municipio", "cod_solo", "decendio", "alvo"]]
    alvo_vizinho = alvo_vizinho.rename(columns={"id_municipio": "id_vizinho"})

    resposta = resposta.merge(alvo_vizinho, on=["id_vizinho", "cod_solo", "decendio"], how="left")
    return resposta["alvo"].values


def salvar_matriz(y_real, y_previsto, nome):
    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_predictions(y_real, y_previsto, ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Matriz de confusao - " + nome)
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "matriz_confusao_" + nome + ".png"), dpi=120)
    plt.close()


def treinar(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    df = pd.read_sql("SELECT * FROM gold.dataset_treino", engine)
    df = df.reset_index(drop=True)

    X = df[VARIAVEIS]
    y = df["alvo"]

    # validacao por municipios: separa por microrregiao para o modelo testar
    # em municipios que ele nunca viu (e sem vizinhos colados no treino)
    grupos = df["microrregiao"]
    kfold = GroupKFold(n_splits=5)

    modelos = {
        "baseline_mais_frequente": DummyClassifier(strategy="most_frequent"),
        "arvore_decisao": DecisionTreeClassifier(max_depth=8, class_weight="balanced", random_state=42),
        "random_forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
    }

    previsoes = df[["id_municipio", "municipio", "microrregiao", "cod_solo", "decendio", "alvo"]].copy()
    previsoes["baseline_vizinho"] = None
    for nome in modelos:
        previsoes[nome] = None

    fold = 1
    for indices_treino, indices_teste in kfold.split(X, y, grupos):
        print("Fold", fold)

        treino = df.loc[indices_treino]
        teste = df.loc[indices_teste]
        previsoes.loc[indices_teste, "baseline_vizinho"] = prever_vizinho(treino, teste)

        for nome in modelos:
            modelo = modelos[nome]
            modelo.fit(X.loc[indices_treino], y.loc[indices_treino])
            previsoes.loc[indices_teste, nome] = modelo.predict(X.loc[indices_teste])

        fold = fold + 1

    # metricas
    resultados = []
    for nome in ["baseline_mais_frequente", "baseline_vizinho", "arvore_decisao", "random_forest"]:
        y_previsto = previsoes[nome]

        linha = {}
        linha["modelo"] = nome
        linha["acuracia"] = round(accuracy_score(y, y_previsto), 4)
        linha["f1_macro"] = round(f1_score(y, y_previsto, average="macro"), 4)
        linha["f1_ponderado"] = round(f1_score(y, y_previsto, average="weighted"), 4)
        resultados.append(linha)

        print()
        print("=====", nome, "=====")
        print(classification_report(y, y_previsto, zero_division=0))
        salvar_matriz(y, y_previsto, nome)

    resultados = pd.DataFrame(resultados)
    print(resultados.to_string(index=False))

    resultados["dt_processamento"] = pd.Timestamp.now()
    resultados.to_sql("resultado_modelos", engine, schema="gold", if_exists="replace", index=False)
    previsoes.to_sql("previsoes_validacao", engine, schema="gold", if_exists="replace", index=False)

    # modelo final: random forest treinado com todos os dados (vai ser usado na API)
    final = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
    final.fit(X, y)
    joblib.dump(final, os.path.join("modelo", "modelo_random_forest.joblib"))

    importancia = pd.DataFrame({"variavel": VARIAVEIS, "importancia": final.feature_importances_})
    importancia = importancia.sort_values("importancia", ascending=True)

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.barh(importancia["variavel"], importancia["importancia"])
    ax.set_title("Importancia das variaveis - Random Forest")
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "importancia_variaveis.png"), dpi=120)
    plt.close()

    print()
    print(importancia.sort_values("importancia", ascending=False).to_string(index=False))
    return resultados


if __name__ == "__main__":
    treinar()
