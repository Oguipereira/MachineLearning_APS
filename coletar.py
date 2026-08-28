"""
Grava a telemetria do Arduino em CSV. E a ponte entre o robo e o Python.

    python coletar.py --porta COM3 --saida logs/combate_01.csv
    python coletar.py --listar

Depois:
    import pandas as pd
    df = pd.read_csv("logs/combate_01.csv")
    df.plot(x="t", y="d_cen")

Use tambem para os TESTES DE BANCADA (robo parado):
    - passar a mao com papel branco/preto sobre o sensor de linha
    - aproximar uma caixa a distancias medidas com trena
Os numeros que sairem daqui substituem os parametros [MEDIR] do core.py.
"""

import argparse
import csv
import os
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("Falta o pyserial.  Rode:  pip install pyserial")

COLS_BASICO = ["t", "estado", "dist", "FE", "FD", "TE", "TD"]
COLS_AVANCADO = ["t", "estado", "d_esq", "d_cen", "d_dir", "d_sonar",
                 "ang", "valido", "FE", "FD", "TE", "TD"]

ESTADOS = {0: "PARADO", 1: "ABERTURA", 2: "BUSCA", 3: "ATAQUE",
           4: "EMPURRANDO", 5: "FUGA"}


def listar():
    print("Portas seriais disponiveis:")
    for p in list_ports.comports():
        print(f"  {p.device:12s}  {p.description}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--saida", default="logs/telemetria.csv")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()

    if a.listar or not a.porta:
        listar()
        return

    os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
    ser = serial.Serial(a.porta, a.baud, timeout=1)
    time.sleep(2)   # Arduino reseta ao abrir a serial
    ser.reset_input_buffer()

    print(f"Gravando em {a.saida}.  Ctrl+C para parar.\n")
    cabecalho = None
    n = 0

    with open(a.saida, "w", newline="") as f:
        w = csv.writer(f)
        try:
            while True:
                linha = ser.readline().decode(errors="ignore").strip()
                if not linha:
                    continue
                campos = linha.split(",")
                if cabecalho is None:
                    cabecalho = (COLS_AVANCADO if len(campos) == 12
                                 else COLS_BASICO)
                    w.writerow(cabecalho)
                    print("formato detectado:", " ".join(cabecalho))
                if len(campos) != len(cabecalho):
                    continue
                w.writerow(campos)
                n += 1
                if n % 20 == 0:
                    est = ESTADOS.get(int(campos[1]), "?")
                    print(f"\r{n:6d} amostras   estado={est:11s}", end="")
        except KeyboardInterrupt:
            print(f"\n\nParado. {n} amostras salvas em {a.saida}")
        finally:
            ser.close()


if __name__ == "__main__":
    main()