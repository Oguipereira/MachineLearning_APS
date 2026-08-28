"""
Nucleo da simulacao de sumo de robos - APS UNIP.

Todas as unidades: centimetros, segundos, radianos, gramas.
A arena e o robo seguem o regulamento e as specs do kit RS100 V2.

AVISO DE HONESTIDADE DE MODELAGEM
---------------------------------
Este simulador e cinematico com um modelo de empurrao simplificado.
Ele NAO reproduz: inercia rotacional real, escorregamento lateral,
deformacao de pneu, folga de engrenagem, atraso do driver.

Serve para: comparar ESTRATEGIAS entre si.
Nao serve para: prever velocidade/forca absoluta do robo real.

Os parametros marcados com [MEDIR] devem ser substituidos pelos
valores medidos em bancada antes de confiar nos resultados.
"""

import math

# ---------------------------------------------------------------
# CONSTANTES DA ARENA (regulamento APS - nao alterar)
# ---------------------------------------------------------------
ARENA_RAIO = 50.0          # cm - diametro 100 cm
BORDA_LARGURA = 5.0        # cm - faixa branca
RAIO_LINHA_BRANCA = ARENA_RAIO - BORDA_LARGURA   # 45.0 cm
TEMPO_ROUND = 60.0         # s
DT = 0.02                  # s - passo de 50 Hz

# ---------------------------------------------------------------
# PARAMETROS DO ROBO (kit RS100 V2)
# ---------------------------------------------------------------
ROBO_COMP = 19.5           # cm
ROBO_LARG = 17.0           # cm
ENTRE_EIXOS = 12.0         # cm - distancia entre rodas motrizes
MASSA_PADRAO = 560.0       # g - kit de fabrica
MASSA_MAX = 1500.0         # g - limite do regulamento

VEL_MAX = 60.0             # cm/s  [MEDIR] motor 200 RPM, roda ~65mm
MU_PNEU = 0.60             # coef. atrito pneu/MDF  [MEDIR] teste da rampa
G = 981.0                  # cm/s^2

# ---------------------------------------------------------------
# PARAMETROS DOS SENSORES
# ---------------------------------------------------------------
HCSR04_ALCANCE = 100.0     # cm
HCSR04_CONE = math.radians(15)   # meio-angulo do cone
HCSR04_PERIODO = 0.060     # s - uma leitura a cada 60 ms (limitacao real)

TOF_ALCANCE = 120.0        # cm
TOF_CONE = math.radians(13)
TOF_PERIODO = 0.025        # s
TOF_ANGULOS = [-60, -30, 0, 30, 60]   # graus, montagem em leque

LINHA_PERIODO = 0.002      # s - leitura praticamente instantanea


def _norm(a):
    """Normaliza angulo para [-pi, pi]."""
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class Robo:
    """Um robo de sumo. Traccao diferencial, chassi retangular."""

    def __init__(self, x, y, th, massa=MASSA_PADRAO, nome="robo", cor=(60, 130, 255)):
        self.x = x
        self.y = y
        self.th = th              # rad, 0 = eixo +x
        self.massa = massa
        self.nome = nome
        self.cor = cor

        self.cmd_esq = 0.0        # comando de motor em [-1, 1]
        self.cmd_dir = 0.0
        self.vivo = True

        # raio efetivo para colisao (aproximacao circular do chassi)
        self.raio = math.hypot(ROBO_COMP, ROBO_LARG) / 2.0 * 0.80

        # telemetria acumulada no round
        self.log = []

    # -- geometria -------------------------------------------------
    def raio_centro(self):
        """Distancia do centro do robo ao centro da arena."""
        return math.hypot(self.x, self.y)

    def cantos(self):
        """Posicoes globais dos 4 cantos (onde ficam os sensores de linha).
        Ordem: FE, FD, TE, TD (frente-esq, frente-dir, tras-esq, tras-dir)."""
        c, s = math.cos(self.th), math.sin(self.th)
        hl, hw = ROBO_COMP / 2.0, ROBO_LARG / 2.0
        locais = [(hl, hw), (hl, -hw), (-hl, hw), (-hl, -hw)]
        return [(self.x + lx * c - ly * s, self.y + lx * s + ly * c)
                for lx, ly in locais]

    def forca_tracao(self):
        """Forca maxima de empurrao = mu * m * g.
        E ESTE o numero que decide quem empurra quem, nao a potencia."""
        return MU_PNEU * (self.massa / 1000.0) * (G / 100.0)   # em N aprox

    # -- atuacao ---------------------------------------------------
    def aplicar(self, esq, dir_):
        self.cmd_esq = max(-1.0, min(1.0, esq))
        self.cmd_dir = max(-1.0, min(1.0, dir_))

    def passo(self, dt):
        v_e = self.cmd_esq * VEL_MAX
        v_d = self.cmd_dir * VEL_MAX
        v = (v_e + v_d) / 2.0
        w = (v_d - v_e) / ENTRE_EIXOS

        self.th = _norm(self.th + w * dt)
        self.x += v * math.cos(self.th) * dt
        self.y += v * math.sin(self.th) * dt

    def caiu(self):
        return self.raio_centro() > ARENA_RAIO


class Sensores:
    """Leituras dos sensores de UM robo em relacao ao mundo.

    Modela a latencia real de cada sensor: uma leitura so e atualizada
    quando o periodo do sensor expira. E por isso que o HC-SR04
    atrapalha - 60 ms de cegueira por leitura.
    """

    def __init__(self, usar_tof=False):
        self.usar_tof = usar_tof
        self.linha = [False, False, False, False]   # FE, FD, TE, TD
        self.dist_frente = HCSR04_ALCANCE
        self.tof = {a: TOF_ALCANCE for a in TOF_ANGULOS}
        self._t_hc = 0.0
        self._t_tof = 0.0

    def atualizar(self, eu, inimigo, t):
        # sensores de linha: sempre atualizados (rapidos)
        self.linha = [math.hypot(cx, cy) > RAIO_LINHA_BRANCA
                      for cx, cy in eu.cantos()]

        # ultrassonico: respeita o periodo de 60 ms
        if t - self._t_hc >= HCSR04_PERIODO:
            self._t_hc = t
            self.dist_frente = self._raio_para(eu, inimigo, 0.0,
                                               HCSR04_CONE, HCSR04_ALCANCE)

        # ToF: opcional, mais rapido e com angulo
        if self.usar_tof and t - self._t_tof >= TOF_PERIODO:
            self._t_tof = t
            for ang in TOF_ANGULOS:
                self.tof[ang] = self._raio_para(eu, inimigo,
                                                math.radians(ang),
                                                TOF_CONE, TOF_ALCANCE)

    @staticmethod
    def _raio_para(eu, inimigo, offset, cone, alcance):
        """Distancia ao inimigo se ele estiver dentro do cone, senao alcance."""
        dx, dy = inimigo.x - eu.x, inimigo.y - eu.y
        dist = math.hypot(dx, dy)
        if dist > alcance:
            return alcance
        ang_rel = _norm(math.atan2(dy, dx) - eu.th - offset)
        # inimigo tem largura: amplia o cone conforme fica perto
        meia_largura = math.atan2(inimigo.raio, max(dist, 1.0))
        if abs(ang_rel) <= cone + meia_largura:
            return max(0.0, dist - inimigo.raio)
        return alcance

    # -- atalhos usados pelas estrategias -------------------------
    @property
    def borda_frente(self):
        return self.linha[0] or self.linha[1]

    @property
    def borda_tras(self):
        return self.linha[2] or self.linha[3]

    @property
    def borda_qualquer(self):
        return any(self.linha)

    def angulo_alvo(self):
        """Retorna o angulo (graus) do ToF com a menor leitura, ou None."""
        if not self.usar_tof:
            return None
        ang, d = min(self.tof.items(), key=lambda kv: kv[1])
        return ang if d < TOF_ALCANCE * 0.95 else None

    def dist_alvo(self):
        if self.usar_tof:
            d = min(self.tof.values())
            return d
        return self.dist_frente


def resolver_colisao(a, b):
    """Modelo de empurrao simplificado.

    Quem empurra e definido pela componente da forca de tracao ao longo
    da normal de contato. Forca de tracao = mu * m * g -> MASSA MANDA.
    A diferenca liquida desloca os dois ao longo da normal.
    """
    dx, dy = b.x - a.x, b.y - a.y
    dist = math.hypot(dx, dy)
    minima = a.raio + b.raio
    if dist >= minima or dist < 1e-6:
        return False

    nx, ny = dx / dist, dy / dist   # normal de a -> b

    # separa a sobreposicao geometrica
    sobrepos = minima - dist
    a.x -= nx * sobrepos * 0.5
    a.y -= ny * sobrepos * 0.5
    b.x += nx * sobrepos * 0.5
    b.y += ny * sobrepos * 0.5

    # componente de empurrao de cada um ao longo da normal
    push_a = a.forca_tracao() * ((a.cmd_esq + a.cmd_dir) / 2.0) * \
        (math.cos(a.th) * nx + math.sin(a.th) * ny)
    push_b = b.forca_tracao() * ((b.cmd_esq + b.cmd_dir) / 2.0) * \
        (math.cos(b.th) * (-nx) + math.sin(b.th) * (-ny))

    liquido = push_a - push_b          # > 0 => a empurra b
    desloc = liquido * 0.9 * DT        # ganho empirico  [MEDIR]

    a.x += nx * desloc * 0.35
    a.y += ny * desloc * 0.35
    b.x += nx * desloc
    b.y += ny * desloc
    return True


def rodar_round(estrat_a, estrat_b, massa_a=MASSA_PADRAO, massa_b=MASSA_PADRAO,
                gravar=False, semente_pos=0.0):
    """Roda um round completo. Retorna (resultado, historico).

    resultado: 'A', 'B' ou 'EMPATE'
    historico: lista de frames para o visualizador (se gravar=True)

    Posicao inicial conforme Figura 1 do regulamento: lado a lado,
    sentidos opostos.
    """
    offset = 15.0 + semente_pos
    a = Robo(-offset, 0, math.pi / 2, massa_a, "A", (60, 130, 255))
    b = Robo(offset, 0, -math.pi / 2, massa_b, "B", (235, 70, 70))

    sa = Sensores(getattr(estrat_a, "usa_tof", False))
    sb = Sensores(getattr(estrat_b, "usa_tof", False))

    estrat_a.reiniciar()
    estrat_b.reiniciar()

    hist = []
    t = 0.0
    while t < TEMPO_ROUND:
        sa.atualizar(a, b, t)
        sb.atualizar(b, a, t)

        a.aplicar(*estrat_a.decidir(sa, t))
        b.aplicar(*estrat_b.decidir(sb, t))

        a.passo(DT)
        b.passo(DT)
        resolver_colisao(a, b)

        if gravar:
            hist.append((a.x, a.y, a.th, b.x, b.y, b.th, t))

        fora_a, fora_b = a.caiu(), b.caiu()
        if fora_a and fora_b:
            return "EMPATE", hist
        if fora_a:
            return "B", hist
        if fora_b:
            return "A", hist

        t += DT

    return "EMPATE", hist