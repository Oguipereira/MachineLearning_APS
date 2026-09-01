"""
Analise da telemetria de combate. E aqui que o "machine learning" acontece.

    python analisar.py --logs logs/ --graficos

O QUE ESTE SCRIPT FAZ
---------------------
1. Junta todos os CSVs de combate gravados pelo coletar.py
2. Gera os graficos descritivos (distribuicao de estados, distancias)
3. Treina uma ARVORE DE DECISAO para responder:
   "quais condicoes de sensor precederam as derrotas?"
4. IMPRIME AS REGRAS APRENDIDAS em formato legivel

O QUE ELE NAO FAZ
-----------------
Nao gera codigo para o robo. Nao roda no Arduino. A arvore e um
DIAGNOSTICO: voce le as regras, entende o padrao, e ajusta os limiares
do .ino a mao. O robo continua deterministico.

Por que arvore de decisao e nao rede neural:
a arvore IMPRIME as regras que aprendeu. Uma rede neural nao.
Como o objetivo e voce entender o que esta errado, a arvore ganha.

CONVENCAO DE NOME DOS ARQUIVOS
------------------------------
    logs/combate_01_VITORIA.csv
    logs/combate_02_DERROTA.csv
    logs/combate_03_EMPATE.csv

O resultado precisa estar no nome. E assim que o script sabe rotular.
"""

import argparse
import glob
import os
import sys

try:
    import pandas as pd
    import numpy as np
except ImportError:
    sys.exit("Faltam bibliotecas.  Rode:  pip install pandas numpy scikit-learn matplotlib")

ESTADOS = {0: "PARADO", 1: "ABERTURA", 2: "BUSCA", 3: "ATAQUE",
           4: "EMPURRANDO", 5: "FUGA"}


def carregar(pasta):
    """Le todos os CSVs da pasta e rotula pelo nome do arquivo."""
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.csv")))
    if not arquivos:
        sys.exit(f"Nenhum CSV encontrado em {pasta}/")

    quadros = []
    for caminho in arquivos:
        nome = os.path.basename(caminho).upper()
        if "VITORIA" in nome:
            res = "VITORIA"
        elif "DERROTA" in nome:
            res = "DERROTA"
        elif "EMPATE" in nome:
            res = "EMPATE"
        else:
            print(f"  ignorado (sem resultado no nome): {nome}")
            continue

        df = pd.read_csv(caminho)
        df["resultado"] = res
        df["combate"] = os.path.basename(caminho)
        # tempo relativo ao inicio do round, em segundos
        df["t_s"] = (df["t"] - df["t"].iloc[0]) / 1000.0
        quadros.append(df)
        print(f"  {os.path.basename(caminho):32s} {res:8s} "
              f"{len(df):5d} amostras  {df['t_s'].iloc[-1]:5.1f} s")

    if not quadros:
        sys.exit("Nenhum arquivo valido. Renomeie incluindo VITORIA/DERROTA/EMPATE.")
    return pd.concat(quadros, ignore_index=True)


def resumo(df):
    print("\n" + "=" * 62)
    print("RESUMO DOS COMBATES")
    print("=" * 62)

    por_combate = df.groupby("combate")["resultado"].first()
    cont = por_combate.value_counts()
    total = len(por_combate)
    print(f"\nTotal de combates: {total}")
    for res in ("VITORIA", "EMPATE", "DERROTA"):
        n = cont.get(res, 0)
        print(f"  {res:8s} {n:3d}  ({100*n/total:5.1f}%)")

    pontos = 2 * cont.get("VITORIA", 0) + cont.get("EMPATE", 0)
    print(f"\nPontos na 1a fase (vitoria=2, empate=1): {pontos}")

    print("\n--- tempo gasto em cada estado (% das amostras) ---")
    dist = df["estado"].value_counts(normalize=True).sort_index()
    for e, p in dist.items():
        print(f"  {ESTADOS.get(e, e):11s} {100*p:5.1f}%")

    # sinal de alerta: muito tempo em FUGA quer dizer borda mal calibrada
    frac_fuga = dist.get(5, 0)
    if frac_fuga > 0.30:
        print("\n  [ALERTA] Mais de 30% do tempo em FUGA.")
        print("  Provaveis causas: sensor de linha muito sensivel, tempo de")
        print("  re longo demais, ou o robo esta lutando perto da borda.")

    frac_busca = dist.get(2, 0)
    if frac_busca > 0.40:
        print("\n  [ALERTA] Mais de 40% do tempo em BUSCA.")
        print("  O robo esta perdendo o alvo. Considere os sensores ToF")
        print("  ou aumente T_MEMORIA_ALVO.")


def comparar_vitoria_derrota(df):
    print("\n" + "=" * 62)
    print("O QUE DIFERENCIA VITORIA DE DERROTA")
    print("=" * 62)

    col_dist = "d_cen" if "d_cen" in df.columns else "dist"
    v = df[df.resultado == "VITORIA"]
    d = df[df.resultado == "DERROTA"]
    if len(d) == 0:
        print("\nNenhuma derrota registrada - nada a comparar (ainda).")
        return

    print(f"\n{'metrica':32s} {'VITORIA':>10s} {'DERROTA':>10s}")
    print("-" * 54)

    def linha(nome, fv, fd):
        print(f"{nome:32s} {fv:10.2f} {fd:10.2f}")

    linha("tempo medio em ATAQUE (%)",
          100 * (v.estado == 3).mean(), 100 * (d.estado == 3).mean())
    linha("tempo medio em FUGA (%)",
          100 * (v.estado == 5).mean(), 100 * (d.estado == 5).mean())
    linha("tempo medio em BUSCA (%)",
          100 * (v.estado == 2).mean(), 100 * (d.estado == 2).mean())
    linha("distancia mediana ao alvo (cm)",
          v[col_dist].median(), d[col_dist].median())
    linha("acionamentos de linha por s",
          v[["FE", "FD", "TE", "TD"]].sum(axis=1).mean() * 20,
          d[["FE", "FD", "TE", "TD"]].sum(axis=1).mean() * 20)
    linha("sensores traseiros acionados (%)",
          100 * ((v.TE + v.TD) > 0).mean(), 100 * ((d.TE + d.TD) > 0).mean())

    print("\nLeitura: se as derrotas tem MAIS acionamento traseiro, voces")
    print("estao sendo empurrados de re. Se tem MENOS acionamento total,")
    print("o robo pode estar saindo sem nem ver a borda - problema grave")
    print("de calibracao ou de altura dos sensores.")


def arvore(df, profundidade=3):
    try:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import confusion_matrix, accuracy_score
    except ImportError:
        print("\n[pular arvore] pip install scikit-learn")
        return

    print("\n" + "=" * 62)
    print("ARVORE DE DECISAO - REGRAS APRENDIDAS")
    print("=" * 62)

    dados = df[df.resultado.isin(["VITORIA", "DERROTA"])].copy()
    if dados.combate.nunique() < 4:
        print("\nPoucos combates para treinar (minimo ~10, ideal 20+).")
        print("Colete mais dados antes de confiar nas regras.")
        return

    col_dist = "d_cen" if "d_cen" in dados.columns else "dist"
    features = ["estado", col_dist, "FE", "FD", "TE", "TD", "t_s"]
    features = [f for f in features if f in dados.columns]

    X = dados[features].fillna(999)
    y = (dados.resultado == "DERROTA").astype(int)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3,
                                          random_state=42, stratify=y)

    # profundidade pequena de proposito: queremos regras LEGIVEIS,
    # nao o melhor classificador possivel
    clf = DecisionTreeClassifier(max_depth=profundidade,
                                 min_samples_leaf=50,
                                 random_state=42)
    clf.fit(Xtr, ytr)

    acc = accuracy_score(yte, clf.predict(Xte))
    print(f"\nAcuracia no conjunto de teste: {100*acc:.1f}%")
    print("(Uma acuracia alta aqui NAO significa robo bom. Significa que")
    print(" existe um padrao consistente nas derrotas - e voce quer saber qual.)")

    print("\nMatriz de confusao (linhas = real, colunas = previsto):")
    print(confusion_matrix(yte, clf.predict(Xte)))

    print("\n--- IMPORTANCIA DE CADA VARIAVEL ---")
    imp = sorted(zip(features, clf.feature_importances_),
                 key=lambda kv: -kv[1])
    for nome, v in imp:
        barra = "#" * int(v * 40)
        print(f"  {nome:10s} {v:5.3f} {barra}")

    print("\n--- REGRAS (leia e ajuste o .ino a mao) ---")
    print(export_text(clf, feature_names=features, decimals=1))

    print("COMO USAR ISTO:")
    print("  Procure os ramos que levam a 'class: 1' (DERROTA).")
    print("  Cada ramo e uma condicao de sensor que precede derrotas.")
    print("  Exemplo: se aparecer 'dist <= 38 e estado = 3', significa que")
    print("  atacar a menos de 38 cm esta causando derrotas - entao aumente")
    print("  DIST_ATAQUE ou reduza VEL_ATAQUE no Arduino.")


def graficos(df, saida="graficos"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[pular graficos] pip install matplotlib")
        return

    os.makedirs(saida, exist_ok=True)
    col_dist = "d_cen" if "d_cen" in df.columns else "dist"

    # 1. tempo em cada estado, por resultado
    fig, ax = plt.subplots(figsize=(8, 4.5))
    tab = (df.groupby(["resultado", "estado"]).size()
             .unstack(fill_value=0))
    tab = tab.div(tab.sum(axis=1), axis=0) * 100
    tab.columns = [ESTADOS.get(c, c) for c in tab.columns]
    tab.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylabel("% do tempo")
    ax.set_title("Distribuicao de estados por resultado do combate")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(f"{saida}/estados_por_resultado.png", dpi=150)
    plt.close()

    # 2. histograma de distancia
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for res, cor in [("VITORIA", "tab:green"), ("DERROTA", "tab:red")]:
        sub = df[df.resultado == res]
        if len(sub):
            ax.hist(sub[col_dist].clip(0, 120), bins=40, alpha=.55,
                    label=res, color=cor, density=True)
    ax.set_xlabel("distancia ao alvo (cm)")
    ax.set_ylabel("densidade")
    ax.set_title("Distancia ao adversario: vitorias x derrotas")
    ax.legend(); plt.tight_layout()
    plt.savefig(f"{saida}/distancia_por_resultado.png", dpi=150)
    plt.close()

    # 3. linha do tempo de um combate
    primeiro = df.combate.iloc[0]
    sub = df[df.combate == primeiro]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    a1.plot(sub.t_s, sub[col_dist].clip(0, 120), lw=1)
    a1.set_ylabel("distancia (cm)")
    a1.set_title(f"Linha do tempo - {primeiro}")
    a1.grid(alpha=.3)
    a2.step(sub.t_s, sub.estado, where="post", lw=1.2)
    a2.set_yticks(sorted(ESTADOS.keys()))
    a2.set_yticklabels([ESTADOS[k] for k in sorted(ESTADOS.keys())], fontsize=8)
    a2.set_xlabel("tempo (s)"); a2.grid(alpha=.3)
    plt.tight_layout()
    plt.savefig(f"{saida}/linha_do_tempo.png", dpi=150)
    plt.close()

    print(f"\nGraficos salvos em {saida}/ (prontos para o trabalho escrito)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--graficos", action="store_true")
    ap.add_argument("--profundidade", type=int, default=3)
    a = ap.parse_args()

    print("Carregando logs...")
    df = carregar(a.logs)
    resumo(df)
    comparar_vitoria_derrota(df)
    arvore(df, a.profundidade)
    if a.graficos:
        graficos(df)