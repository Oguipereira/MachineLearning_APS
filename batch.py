"""
Roda milhares de combates sem interface e reporta taxa de vitoria.
E aqui que a estrategia e realmente otimizada - o visualizador serve
para voce ENTENDER, o batch serve para voce DECIDIR.

    python batch.py                 # placar contra todos os oponentes
    python batch.py --varrer massa  # efeito da massa na taxa de vitoria
    python batch.py --varrer freio  # efeito da contencao perto da borda
    python batch.py --varrer tof    # ganho real dos sensores ToF

Os graficos gerados vao direto para o trabalho escrito.
"""

import argparse
import random

from sim import core, estrategias


def duelo(fabrica_a, massa_a=core.MASSA_PADRAO,
          massa_b=core.MASSA_PADRAO, n=200, oponentes=None):
    """Roda n rounds contra cada oponente. Retorna dict de resultados."""
    oponentes = oponentes or estrategias.TODOS_OPONENTES
    total = {"vit": 0, "der": 0, "emp": 0}
    por_op = {}

    for Op in oponentes:
        r = {"vit": 0, "der": 0, "emp": 0}
        for i in range(n):
            random.seed(i)
            res, _ = core.rodar_round(
                fabrica_a(), Op(), massa_a, massa_b,
                semente_pos=random.uniform(-2.0, 2.0))
            if res == "A":
                r["vit"] += 1
            elif res == "B":
                r["der"] += 1
            else:
                r["emp"] += 1
        por_op[Op.nome] = r
        for k in total:
            total[k] += r[k]
    return total, por_op


def pontos(r):
    """Pontuacao da primeira fase: vitoria 2, empate 1, derrota 0."""
    return r["vit"] * 2 + r["emp"]


def relatorio(n=200):
    print("\n=== PLACAR CONTRA TODOS OS OPONENTES ===")
    print(f"{n} rounds contra cada perfil\n")
    for tof in (False, True):
        for massa in (560, 1000, 1500):
            total, por_op = duelo(
                lambda: estrategias.Competidor(usa_tof=tof),
                massa_a=massa, n=n)
            tot = sum(total.values())
            print(f"ToF {'ON ' if tof else 'OFF'} | massa {massa:4d} g | "
                  f"vit {100*total['vit']/tot:5.1f}%  "
                  f"emp {100*total['emp']/tot:5.1f}%  "
                  f"der {100*total['der']/tot:5.1f}%  "
                  f"| pontos {pontos(total):4d}")
        print()

    print("--- detalhe por oponente (1500 g, ToF ON) ---")
    _, por_op = duelo(lambda: estrategias.Competidor(usa_tof=True),
                      massa_a=1500, n=n)
    for nome, r in por_op.items():
        tot = sum(r.values())
        print(f"  {nome:10s}  vit {100*r['vit']/tot:5.1f}%  "
              f"emp {100*r['emp']/tot:5.1f}%  der {100*r['der']/tot:5.1f}%")


def varrer(qual, n=120):
    import matplotlib.pyplot as plt

    if qual == "massa":
        xs = [560, 700, 850, 1000, 1150, 1300, 1500]
        ys = []
        for m in xs:
            total, _ = duelo(lambda: estrategias.Competidor(usa_tof=False),
                             massa_a=m, n=n)
            tot = sum(total.values())
            ys.append(100 * total["vit"] / tot)
        rot = "massa do robo (g)"
        titulo = "Taxa de vitoria x massa\n(forca de empurrao = mu*m*g)"

    elif qual == "freio":
        xs = [0.0, 0.2, 0.4, 0.55, 0.7, 0.85, 1.0]
        ys = []
        for f in xs:
            total, _ = duelo(
                lambda: estrategias.Competidor(usa_tof=False, freio_borda=f),
                massa_a=1200, n=n)
            tot = sum(total.values())
            ys.append(100 * total["vit"] / tot)
        rot = "limiar de contencao perto da borda"
        titulo = "Taxa de vitoria x agressividade na borda"

    elif qual == "tof":
        xs = [560, 900, 1200, 1500]
        s_off, s_on = [], []
        for m in xs:
            for tof, alvo in ((False, s_off), (True, s_on)):
                total, _ = duelo(
                    lambda: estrategias.Competidor(usa_tof=tof),
                    massa_a=m, n=n)
                tot = sum(total.values())
                alvo.append(100 * total["vit"] / tot)
        plt.figure(figsize=(7, 4.5))
        plt.plot(xs, s_off, "o-", label="so HC-SR04 (kit)")
        plt.plot(xs, s_on, "s-", label="HC-SR04 + ToF VL53L0X")
        plt.xlabel("massa do robo (g)")
        plt.ylabel("taxa de vitoria (%)")
        plt.title("Ganho real dos sensores ToF")
        plt.grid(alpha=.3); plt.legend(); plt.tight_layout()
        plt.savefig("varredura_tof.png", dpi=150)
        print("salvo: varredura_tof.png")
        plt.show()
        return
    else:
        raise SystemExit("use --varrer massa|freio|tof")

    plt.figure(figsize=(7, 4.5))
    plt.plot(xs, ys, "o-")
    plt.xlabel(rot); plt.ylabel("taxa de vitoria (%)")
    plt.title(titulo); plt.grid(alpha=.3); plt.tight_layout()
    nome = f"varredura_{qual}.png"
    plt.savefig(nome, dpi=150)
    print("salvo:", nome)
    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--varrer", choices=["massa", "freio", "tof"])
    ap.add_argument("-n", type=int, default=200)
    a = ap.parse_args()
    if a.varrer:
        varrer(a.varrer, a.n)
    else:
        relatorio(a.n)
