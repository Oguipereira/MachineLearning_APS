"""
Estrategias de combate.

Cada estrategia e uma classe com:
    reiniciar()             -> zera estado no inicio do round
    decidir(sensores, t)    -> retorna (motor_esq, motor_dir) em [-1, 1]

A estrutura e IDENTICA a maquina de estados do codigo Arduino.
Isso e proposital: o que voce validar aqui, voce transcreve para o .ino
quase linha a linha.

REGRA DE OURO (vale aqui e no robo real):
    Se qualquer sensor de linha ver branco, TUDO o mais e cancelado.
    A borda tem prioridade absoluta sobre o ataque.
"""

import math
import random

from . import core


class Base:
    """Classe base. Herde daqui."""
    nome = "base"
    usa_tof = False

    def reiniciar(self):
        pass

    def decidir(self, s, t):
        return 0.0, 0.0


#  NOSSA ESTRATEGIA

class Competidor(Base):
    """Estrategia principal do nosso robo.

    Maquina de estados:
        ABERTURA  -> giro de 180 graus cronometrado (sabemos onde ele esta)
        BUSCA     -> varredura se perdeu o alvo
        ATAQUE    -> avanca com velocidade em funcao da posicao na arena
        FUGA      -> reacao de borda, prioridade maxima

    Parametros no __init__ sao os "genes" que o batch.py otimiza.
    """
    nome = "Competidor"

    def __init__(self, usa_tof=False, t_abertura=0.45, vel_busca=0.55,
                 dist_ataque=45.0, freio_borda=0.75, t_fuga=0.30,
                 t_giro_fuga=0.28):
        self.usa_tof = usa_tof
        self.t_abertura = t_abertura      # s de giro inicial
        self.vel_busca = vel_busca
        self.dist_ataque = dist_ataque    # cm - abaixo disso, ataca
        self.freio_borda = freio_borda    # raio relativo onde comeca a conter
        self.t_fuga = t_fuga              # s de re
        self.t_giro_fuga = t_giro_fuga    # s de giro apos a re

    def reiniciar(self):
        self.estado = "ABERTURA"
        self.t_estado = 0.0
        self.t_ant = 0.0
        self.lado_busca = 1
        self.borda_era_frente = True

    def decidir(self, s, t):
        dt = t - self.t_ant
        self.t_ant = t
        self.t_estado += dt

        # ---- PRIORIDADE 1: BORDA -----------------------------------
        # Interrompe qualquer estado. No Arduino isso vira interrupcao.
        if s.borda_qualquer and self.estado != "FUGA":
            self.borda_era_frente = s.borda_frente
            self._ir("FUGA")

        if self.estado == "FUGA":
            return self._fuga()

        if self.estado == "ABERTURA":
            return self._abertura()

        if self.estado == "ATAQUE":
            return self._ataque(s)

        return self._busca(s)

    # -- estados ---------------------------------------------------
    def _ir(self, novo):
        self.estado = novo
        self.t_estado = 0.0

    def _abertura(self):
        """Regulamento garante a posicao inicial: giramos 180 e ele esta la.
        Nao ha nada a procurar no instante zero."""
        if self.t_estado >= self.t_abertura:
            self._ir("BUSCA")
        return 1.0, -1.0

    def _fuga(self):
        """Re + giro. Sai da borda antes de voltar a pensar."""
        if self.t_estado < self.t_fuga:
            # re na direcao oposta a borda detectada
            return (-1.0, -1.0) if self.borda_era_frente else (1.0, 1.0)
        if self.t_estado < self.t_fuga + self.t_giro_fuga:
            return 1.0, -1.0
        self._ir("BUSCA")
        return 0.0, 0.0

    def _busca(self, s):
        if s.dist_alvo() < core.HCSR04_ALCANCE * 0.9:
            self._ir("ATAQUE")
            return self._ataque(s)
        # varredura: gira no proprio eixo, alternando o lado
        if self.t_estado > 1.2:
            self.lado_busca *= -1
            self.t_estado = 0.0
        v = self.vel_busca
        return (v * self.lado_busca, -v * self.lado_busca)

    def _ataque(self, s):
        d = s.dist_alvo()
        if d > core.HCSR04_ALCANCE * 0.9:
            self._ir("BUSCA")
            return self._busca(s)

        # correcao de rumo: so possivel com ToF (o HC-SR04 nao da angulo)
        corr = 0.0
        if self.usa_tof:
            ang = s.angulo_alvo()
            if ang is not None:
                corr = max(-0.6, min(0.6, ang / 90.0))

        # velocidade em funcao da distancia
        vel = 1.0 if d < self.dist_ataque else 0.75

        # PRIORIDADE 2: contencao perto da borda.
        # Longe do centro, empurra com torque - nao com velocidade.
        # Sem isso o robo se auto-elimina perseguindo o adversario.
        raio_rel = self._raio_estimado(s)
        if raio_rel > self.freio_borda:
            vel *= 0.55

        return (vel - corr, vel + corr)

    @staticmethod
    def _raio_estimado(s):
        """No simulador teriamos a posicao exata, mas o robo real nao tem.
        Usamos so o que o robo consegue saber: se algum sensor viu branco
        recentemente. Mantido conservador de proposito."""
        return 0.0 if not s.borda_qualquer else 1.0


#  OPONENTES SINTETICOS
#  O ponto do simulador: testar contra varios perfis, nao contra si mesmo.
class Kamikaze(Base):
    """Acelera sempre. Perigoso e burro - sai sozinho com frequencia.
    Representa o grupo que so pensou em atacar."""
    nome = "Kamikaze"

    def reiniciar(self):
        self.t_ant = 0.0
        self.fugindo = 0.0

    def decidir(self, s, t):
        dt = t - self.t_ant
        self.t_ant = t
        if self.fugindo > 0:
            self.fugindo -= dt
            return -1.0, -0.6
        if s.borda_frente:
            self.fugindo = 0.35
            return -1.0, -1.0
        return 1.0, 1.0


class Tanque(Base):
    """Fica no centro girando devagar e so avanca se ver alguem.
    Dificil de tirar: quase nunca se auto-elimina."""
    nome = "Tanque"

    def reiniciar(self):
        self.t_ant = 0.0
        self.fugindo = 0.0

    def decidir(self, s, t):
        dt = t - self.t_ant
        self.t_ant = t
        if self.fugindo > 0:
            self.fugindo -= dt
            return -0.9, -0.5
        if s.borda_qualquer:
            self.fugindo = 0.4
            return -0.9, -0.9
        if s.dist_frente < 35:
            return 0.9, 0.9
        return 0.3, -0.3


class Fujao(Base):
    """Evita contato e joga pelo empate. Estrategia legitima:
    o regulamento da 1 ponto por empate na primeira fase."""
    nome = "Fujao"

    def reiniciar(self):
        self.t_ant = 0.0
        self.fugindo = 0.0

    def decidir(self, s, t):
        dt = t - self.t_ant
        self.t_ant = t
        if self.fugindo > 0:
            self.fugindo -= dt
            return 0.8, -0.8
        if s.borda_qualquer:
            self.fugindo = 0.5
            return -0.8, -0.8
        if s.dist_frente < 40:
            return -0.7, 0.7
        return 0.45, 0.45


class Aleatorio(Base):
    """Comportamento erratico. Serve de teste de robustez -
    se voce ganha do aleatorio menos que 70%, algo esta errado."""
    nome = "Aleatorio"

    def reiniciar(self):
        self.t_ant = 0.0
        self.prox = 0.0
        self.cmd = (0.5, 0.5)

    def decidir(self, s, t):
        self.t_ant = t
        if s.borda_qualquer:
            return -1.0, -0.4
        if t > self.prox:
            self.prox = t + random.uniform(0.3, 1.0)
            self.cmd = (random.uniform(-1, 1), random.uniform(-1, 1))
        return self.cmd


TODOS_OPONENTES = [Kamikaze, Tanque, Fujao, Aleatorio]