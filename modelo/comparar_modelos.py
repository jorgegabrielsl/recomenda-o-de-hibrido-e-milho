import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from config.db.conexao import conexao_pgsql
from modelo.treinar import VARIAVEIS, prever_vizinho

PASTA_RESULTADOS = "resultados"
CLASSES = ["ciclo_20", "ciclo_21", "empate", "nao_indicado"]

LOCALIZACAO = ["latitude", "longitude"]
CONTEXTO = ["cod_solo", "ordem_na_safra"]
CLIMA = [
    "temp_media_hist", "temp_min_media_hist", "temp_max_media_hist", "chuva_safra_hist",
    "gdd_safra_hist", "dias_acima_30_hist", "dias_acima_35_hist", "dias_secos_hist",
    "gdd_120d", "chuva_120d", "dias_acima_30_120d", "dias_acima_35_120d", "dias_secos_120d",
    "tmin_media_30d", "dias_frio_30d",
]
PRODUCAO = ["rendimento_medio_hist"]
CLIMA_140 = ["gdd_140d", "chuva_140d", "dias_acima_30_140d", "dias_acima_35_140d", "dias_secos_140d"]
VIZINHO = ["viz_ciclo_20", "viz_ciclo_21", "viz_empate", "viz_nao_indicado"]


def novos_modelos():
    # modelos com escala precisam do StandardScaler (distancia e gradiente dependem da escala)
    modelos = {
        "arvore_decisao": DecisionTreeClassifier(max_depth=8, class_weight="balanced", random_state=42),
        "random_forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        "extra_trees": ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        "gradient_boosting": HistGradientBoostingClassifier(class_weight="balanced", random_state=42),
        "regressao_logistica": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000)),
        "knn": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=15, weights="distance")),
        "svm": make_pipeline(StandardScaler(), SVC(class_weight="balanced", random_state=42)),
        "rede_neural_mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, early_stopping=True, random_state=42)),
    }
    return modelos


# clima nos 140 dias depois do plantio (ciclo medio do Grupo II), media dos anos
def clima_140_dias(engine):
    sql = """
    WITH inicio AS (
        SELECT
            id_municipio,
            dia AS data_plantio,
            (EXTRACT(MONTH FROM dia)::int - 1) * 3 +
            CASE
                WHEN EXTRACT(DAY FROM dia) = 1 THEN 1
                WHEN EXTRACT(DAY FROM dia) = 11 THEN 2
                ELSE 3
            END AS decendio
        FROM silver.clima_diario
        WHERE EXTRACT(DAY FROM dia) IN (1, 11, 21)
    ),
    janela AS (
        SELECT
            i.id_municipio,
            i.decendio,
            SUM(d.gdd) AS gdd_140d,
            SUM(d.chuva) AS chuva_140d,
            COUNT(*) FILTER (WHERE d.tmax > 30) AS dias_acima_30_140d,
            COUNT(*) FILTER (WHERE d.tmax > 35) AS dias_acima_35_140d,
            COUNT(*) FILTER (WHERE d.chuva < 1) AS dias_secos_140d
        FROM inicio i
        JOIN silver.clima_diario d
            ON d.id_municipio = i.id_municipio
           AND d.dia >= i.data_plantio
           AND d.dia < i.data_plantio + 140
        GROUP BY i.id_municipio, i.decendio, i.data_plantio
        HAVING COUNT(d.dia) = 140
    )
    SELECT
        id_municipio,
        decendio,
        AVG(gdd_140d) AS gdd_140d,
        AVG(chuva_140d) AS chuva_140d,
        AVG(dias_acima_30_140d) AS dias_acima_30_140d,
        AVG(dias_acima_35_140d) AS dias_acima_35_140d,
        AVG(dias_secos_140d) AS dias_secos_140d
    FROM janela
    GROUP BY id_municipio, decendio
    """
    return pd.read_sql(sql, engine)


# resposta do municipio mais proximo que esta no treino e fora da mesma microrregiao
# (no teste a microrregiao inteira fica de fora, entao o treino precisa da mesma regra)
def colunas_vizinho(treino, teste):
    mun_treino = treino[["id_municipio", "microrregiao", "latitude", "longitude"]].drop_duplicates()

    vizinho = {}
    for _, m in mun_treino.iterrows():
        outros = mun_treino[mun_treino["microrregiao"] != m["microrregiao"]]
        dist = (outros["latitude"] - m["latitude"]) ** 2 + (outros["longitude"] - m["longitude"]) ** 2
        vizinho[m["id_municipio"]] = outros.loc[dist.idxmin(), "id_municipio"]

    mun_teste = teste[["id_municipio", "latitude", "longitude"]].drop_duplicates()
    for _, m in mun_teste.iterrows():
        dist = (mun_treino["latitude"] - m["latitude"]) ** 2 + (mun_treino["longitude"] - m["longitude"]) ** 2
        vizinho[m["id_municipio"]] = mun_treino.loc[dist.idxmin(), "id_municipio"]

    alvo_vizinho = treino[["id_municipio", "cod_solo", "decendio", "alvo"]]
    alvo_vizinho = alvo_vizinho.rename(columns={"id_municipio": "id_vizinho", "alvo": "alvo_vizinho"})

    saida = []
    for parte in [treino, teste]:
        resposta = parte[["id_municipio", "cod_solo", "decendio"]].copy()
        resposta["id_vizinho"] = resposta["id_municipio"].map(vizinho)
        resposta = resposta.merge(alvo_vizinho, on=["id_vizinho", "cod_solo", "decendio"], how="left")
        for classe in CLASSES:
            resposta["viz_" + classe] = (resposta["alvo_vizinho"] == classe).astype(int).values
        resposta.index = parte.index
        saida.append(resposta[VIZINHO])

    return saida[0], saida[1]


# valida com GroupKFold por microrregiao e devolve a previsao de cada linha
def validar(df, variaveis, modelo, usar_vizinho=False):
    kfold = GroupKFold(n_splits=5)
    previsto = pd.Series(index=df.index, dtype=object)
    f1_folds = []

    for indices_treino, indices_teste in kfold.split(df, df["alvo"], df["microrregiao"]):
        treino = df.loc[indices_treino]
        teste = df.loc[indices_teste]

        X_treino = treino[variaveis]
        X_teste = teste[variaveis]
        if usar_vizinho:
            viz_treino, viz_teste = colunas_vizinho(treino, teste)
            X_treino = pd.concat([X_treino, viz_treino], axis=1)
            X_teste = pd.concat([X_teste, viz_teste], axis=1)

        modelo.fit(X_treino, treino["alvo"])
        previsto.loc[indices_teste] = modelo.predict(X_teste)
        f1_folds.append(f1_score(teste["alvo"], previsto.loc[indices_teste], average="macro"))

    return previsto, f1_folds


def metricas(nome, y, previsto, f1_folds, experimento):
    linha = {}
    linha["experimento"] = experimento
    linha["modelo"] = nome
    linha["acuracia"] = round(accuracy_score(y, previsto), 4)
    linha["f1_macro"] = round(f1_score(y, previsto, average="macro"), 4)
    linha["f1_macro_desvio_folds"] = round(float(np.std(f1_folds)), 4)
    linha["f1_ponderado"] = round(f1_score(y, previsto, average="weighted"), 4)

    f1_classes = f1_score(y, previsto, average=None, labels=CLASSES)
    for i in range(len(CLASSES)):
        linha["f1_" + CLASSES[i]] = round(f1_classes[i], 4)

    # parte 1 da recomendacao: janela (indicado x nao indicado)
    janela_real = np.where(y == "nao_indicado", "nao_indicado", "indicado")
    janela_prev = np.where(previsto == "nao_indicado", "nao_indicado", "indicado")
    linha["f1_macro_janela"] = round(f1_score(janela_real, janela_prev, average="macro"), 4)

    # parte 2: grupo, so nos decendios que o ZARC indica
    indicados = y != "nao_indicado"
    linha["f1_macro_grupo"] = round(f1_score(y[indicados], previsto[indicados], average="macro",
                                             labels=["ciclo_20", "ciclo_21", "empate"]), 4)

    print(experimento, "|", nome, "| macro-F1", linha["f1_macro"], "+-", linha["f1_macro_desvio_folds"])
    return linha


def comparar(engine=None):
    if engine is None:
        engine = conexao_pgsql()

    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    df = pd.read_sql("SELECT * FROM gold.dataset_treino", engine)
    df = df.merge(clima_140_dias(engine), on=["id_municipio", "decendio"], how="left")
    df = df.reset_index(drop=True)
    y = df["alvo"]

    resultados = []

    # 1) baselines
    print("== Baselines ==")
    previsto, f1_folds = validar(df, VARIAVEIS, DummyClassifier(strategy="most_frequent"))
    resultados.append(metricas("baseline_mais_frequente", y, previsto, f1_folds, "1_algoritmos"))

    kfold = GroupKFold(n_splits=5)
    previsto = pd.Series(index=df.index, dtype=object)
    f1_folds = []
    for indices_treino, indices_teste in kfold.split(df, y, df["microrregiao"]):
        previsto.loc[indices_teste] = prever_vizinho(df.loc[indices_treino], df.loc[indices_teste])
        f1_folds.append(f1_score(y.loc[indices_teste], previsto.loc[indices_teste], average="macro"))
    resultados.append(metricas("baseline_vizinho", y, previsto, f1_folds, "1_algoritmos"))

    # 2) varios algoritmos supervisionados com as 20 variaveis
    print("== Algoritmos ==")
    modelos = novos_modelos()
    for nome in modelos:
        previsto, f1_folds = validar(df, VARIAVEIS, modelos[nome])
        resultados.append(metricas(nome, y, previsto, f1_folds, "1_algoritmos"))

    # 3) ablacao: quanto cada grupo de variaveis acrescenta
    print("== Ablacao ==")
    conjuntos = {
        "A_contexto": CONTEXTO,
        "B_localizacao_contexto": LOCALIZACAO + CONTEXTO,
        "C_clima_contexto_sem_localizacao": CLIMA + CONTEXTO,
        "D_localizacao_contexto_clima": LOCALIZACAO + CONTEXTO + CLIMA,
        "E_completo_com_producao": LOCALIZACAO + CONTEXTO + CLIMA + PRODUCAO,
    }
    for nome_conjunto in conjuntos:
        for nome in ["random_forest", "gradient_boosting"]:
            previsto, f1_folds = validar(df, conjuntos[nome_conjunto], novos_modelos()[nome])
            resultados.append(metricas(nome + " | " + nome_conjunto, y, previsto, f1_folds, "2_ablacao"))

    # 4) janela de 120 x 140 dias
    print("== Janela 120 x 140 dias ==")
    sem_120 = []
    for v in VARIAVEIS:
        if not v.endswith("_120d"):
            sem_120.append(v)
    janelas = {
        "janela_120d": VARIAVEIS,
        "janela_140d": sem_120 + CLIMA_140,
        "janela_120d_e_140d": VARIAVEIS + CLIMA_140,
    }
    for nome_janela in janelas:
        previsto, f1_folds = validar(df, janelas[nome_janela], novos_modelos()["random_forest"])
        resultados.append(metricas("random_forest | " + nome_janela, y, previsto, f1_folds, "3_janela"))

    # 5) modelo hibrido: variaveis + resposta do municipio vizinho
    print("== Hibrido ==")
    previsoes_hibrido = None
    for nome in ["random_forest", "gradient_boosting"]:
        previsto, f1_folds = validar(df, VARIAVEIS, novos_modelos()[nome], usar_vizinho=True)
        resultados.append(metricas(nome + " + vizinho", y, previsto, f1_folds, "4_hibrido"))
        if nome == "random_forest":
            previsoes_hibrido = previsto

    resultados = pd.DataFrame(resultados)
    print()
    print(resultados[["experimento", "modelo", "acuracia", "f1_macro", "f1_macro_desvio_folds",
                      "f1_macro_janela", "f1_macro_grupo", "f1_ciclo_21"]].to_string(index=False))

    resultados.to_csv(os.path.join(PASTA_RESULTADOS, "comparacao_modelos.csv"), index=False, sep=";", decimal=",")
    resultados["dt_processamento"] = pd.Timestamp.now()
    resultados.to_sql("comparacao_modelos", engine, schema="gold", if_exists="replace", index=False)

    # grafico dos algoritmos
    algoritmos = resultados[resultados["experimento"] == "1_algoritmos"].sort_values("f1_macro")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(algoritmos["modelo"], algoritmos["f1_macro"], xerr=algoritmos["f1_macro_desvio_folds"], color="#4C78A8")
    ax.set_xlabel("Macro-F1 (validacao por microrregiao)")
    ax.set_title("Comparacao de algoritmos supervisionados")
    ax.set_xlim(0, 1)
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "comparacao_algoritmos.png"), dpi=120)
    plt.close()

    # grafico da ablacao
    ablacao = resultados[resultados["experimento"] == "2_ablacao"]
    ablacao = ablacao[ablacao["modelo"].str.startswith("random_forest")]
    fig, ax = plt.subplots(figsize=(8, 4))
    nomes = ablacao["modelo"].str.replace("random_forest | ", "", regex=False)
    ax.barh(nomes, ablacao["f1_macro"], xerr=ablacao["f1_macro_desvio_folds"], color="#F58518")
    ax.set_xlabel("Macro-F1 (Random Forest)")
    ax.set_title("Ablacao das variaveis")
    ax.set_xlim(0, 1)
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_RESULTADOS, "ablacao_variaveis.png"), dpi=120)
    plt.close()

    return resultados


if __name__ == "__main__":
    comparar()
