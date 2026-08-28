"""
Visualizador da arena em tempo real.

    python visualizar.py
    python visualizar.py --oponente Kamikaze --massa-a 1500 --tof

CONTROLES
    ESPACO   pausa / continua
    R        reinicia o round
    TAB      troca o oponente
    SETA DIR avanca um passo (com o jogo pausado)
    +  /  -  acelera / desacelera a simulacao
    ESC      sai

O que observar:
    - o robo azul (A) e o nosso
    - o circulo tracejado e a linha branca (raio 45 cm)
    - os pontinhos nos cantos ficam brancos quando o sensor ve a borda
    - o cone amarelo e o campo de visao frontal
"""

import argparse
import math
import sys

try:
    import pygame
except ImportError:
    sys.exit("Falta o pygame.  Rode:  pip install pygame")

from sim import core, estrategias

# ---------------------------------------------------------------
ESCALA = 5.0            # pixels por cm
LARG = ALT = int(2 * core.ARENA_RAIO * ESCALA) + 260
CX, CY = (LARG - 240) // 2, ALT // 2

PRETO = (18, 18, 20)
MDF = (38, 38, 42)
BRANCO = (240, 240, 240)
CINZA = (120, 120, 128)
AMARELO = (230, 200, 90)
VERDE = (110, 210, 130)
FUNDO = (12, 12, 14)


def para_tela(x, y):
    return int(CX + x * ESCALA), int(CY - y * ESCALA)


def desenhar_robo(tela, r, s, mostrar_cone):
    c, sn = math.cos(r.th), math.sin(r.th)
    hl, hw = core.ROBO_COMP / 2, core.ROBO_LARG / 2
    pts = []
    for lx, ly in [(hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw)]:
        pts.append(para_tela(r.x + lx * c - ly * sn, r.y + lx * sn + ly * c))
    pygame.draw.polygon(tela, r.cor, pts)
    pygame.draw.polygon(tela, BRANCO, pts, 1)

    # marca da frente (exigida pelo regulamento)
    fx, fy = para_tela(r.x + (hl + 2.5) * c, r.y + (hl + 2.5) * sn)
    pygame.draw.circle(tela, BRANCO, (fx, fy), 4)

    # sensores de linha nos 4 cantos
    for i, (cx_, cy_) in enumerate(r.cantos()):
        ativo = s.linha[i] if s else False
        pygame.draw.circle(tela, BRANCO if ativo else (70, 70, 78),
                           para_tela(cx_, cy_), 5 if ativo else 3)

    # cone de visao frontal
    if mostrar_cone and s:
        d = min(s.dist_alvo(), core.HCSR04_ALCANCE)
        for sinal in (-1, 1):
            a = r.th + sinal * core.HCSR04_CONE
            pygame.draw.line(tela, (*AMARELO, 90), para_tela(r.x, r.y),
                             para_tela(r.x + d * math.cos(a),
                                       r.y + d * math.sin(a)), 1)


def desenhar_arena(tela):
    pygame.draw.circle(tela, BRANCO, (CX, CY),
                       int(core.ARENA_RAIO * ESCALA))
    pygame.draw.circle(tela, MDF, (CX, CY),
                       int(core.RAIO_LINHA_BRANCA * ESCALA))
    # marcas dos pontos de partida
    for dx in (-15, 15):
        px, py = para_tela(dx, 0)
        pygame.draw.line(tela, CINZA, (px - 8, py), (px + 8, py), 1)
        pygame.draw.line(tela, CINZA, (px, py - 8), (px, py + 8), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oponente", default="Kamikaze",
                    choices=[c.__name__ for c in estrategias.TODOS_OPONENTES])
    ap.add_argument("--massa-a", type=float, default=core.MASSA_PADRAO,
                    help="massa do nosso robo em gramas (max 1500)")
    ap.add_argument("--massa-b", type=float, default=core.MASSA_PADRAO)
    ap.add_argument("--tof", action="store_true",
                    help="ativa os sensores ToF no nosso robo")
    args = ap.parse_args()

    pygame.init()
    tela = pygame.display.set_mode((LARG, ALT))
    pygame.display.set_caption("Sumo de Robos - APS UNIP")
    fonte = pygame.font.SysFont("consolas", 15)
    fonte_g = pygame.font.SysFont("consolas", 20, bold=True)
    relogio = pygame.time.Clock()

    idx_op = [c.__name__ for c in estrategias.TODOS_OPONENTES].index(args.oponente)
    placar = {"A": 0, "B": 0, "EMPATE": 0}

    def novo_round():
        ea = estrategias.Competidor(usa_tof=args.tof)
        eb = estrategias.TODOS_OPONENTES[idx_op]()
        ea.reiniciar()
        eb.reiniciar()
        a = core.Robo(-15, 0, math.pi / 2, args.massa_a, "A", (60, 130, 255))
        b = core.Robo(15, 0, -math.pi / 2, args.massa_b, "B", (235, 70, 70))
        sa = core.Sensores(ea.usa_tof)
        sb = core.Sensores(eb.usa_tof)
        return ea, eb, a, b, sa, sb, 0.0, None

    ea, eb, a, b, sa, sb, t, resultado = novo_round()
    pausado = False
    velocidade = 1.0

    while True:
        passo_manual = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); return
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit(); return
                if ev.key == pygame.K_SPACE:
                    pausado = not pausado
                if ev.key == pygame.K_r:
                    ea, eb, a, b, sa, sb, t, resultado = novo_round()
                if ev.key == pygame.K_TAB:
                    idx_op = (idx_op + 1) % len(estrategias.TODOS_OPONENTES)
                    ea, eb, a, b, sa, sb, t, resultado = novo_round()
                if ev.key == pygame.K_RIGHT:
                    passo_manual = True
                if ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    velocidade = min(8.0, velocidade * 1.5)
                if ev.key == pygame.K_MINUS:
                    velocidade = max(0.15, velocidade / 1.5)

        # ---- fisica ------------------------------------------------
        if resultado is None and (not pausado or passo_manual):
            n = 1 if passo_manual else max(1, int(velocidade))
            for _ in range(n):
                if resultado is not None or t >= core.TEMPO_ROUND:
                    break
                sa.atualizar(a, b, t)
                sb.atualizar(b, a, t)
                a.aplicar(*ea.decidir(sa, t))
                b.aplicar(*eb.decidir(sb, t))
                a.passo(core.DT)
                b.passo(core.DT)
                core.resolver_colisao(a, b)
                t += core.DT
                if a.caiu() and b.caiu():
                    resultado = "EMPATE"
                elif a.caiu():
                    resultado = "B"
                elif b.caiu():
                    resultado = "A"
            if resultado is None and t >= core.TEMPO_ROUND:
                resultado = "EMPATE"
            if resultado is not None:
                placar[resultado] += 1

        # ---- desenho -----------------------------------------------
        tela.fill(FUNDO)
        desenhar_arena(tela)
        desenhar_robo(tela, b, sb, False)
        desenhar_robo(tela, a, sa, True)

        px = LARG - 232
        linhas = [
            ("SUMO DE ROBOS", fonte_g, BRANCO),
            ("", fonte, BRANCO),
            (f"tempo    {t:5.1f} / 60 s", fonte, BRANCO),
            (f"estado   {ea.estado}", fonte, VERDE),
            (f"oponente {eb.nome}", fonte, (235, 70, 70)),
            ("", fonte, BRANCO),
            (f"massa A  {args.massa_a:.0f} g", fonte, CINZA),
            (f"massa B  {args.massa_b:.0f} g", fonte, CINZA),
            (f"ToF      {'ON' if args.tof else 'OFF'}", fonte, CINZA),
            (f"dist     {sa.dist_alvo():5.1f} cm", fonte, AMARELO),
            (f"linha    {''.join('X' if v else '.' for v in sa.linha)}",
             fonte, BRANCO),
            ("", fonte, BRANCO),
            (f"placar   A {placar['A']}  B {placar['B']}  E {placar['EMPATE']}",
             fonte, BRANCO),
            (f"veloc    {velocidade:.1f}x", fonte, CINZA),
            ("", fonte, BRANCO),
            ("ESPACO pausa   R reinicia", fonte, CINZA),
            ("TAB oponente   +/- veloc", fonte, CINZA),
        ]
        y = 24
        for txt, f, cor in linhas:
            if txt:
                tela.blit(f.render(txt, True, cor), (px, y))
            y += 22

        if resultado is not None:
            msg = {"A": "VITORIA (azul)", "B": "DERROTA (vermelho venceu)",
                   "EMPATE": "EMPATE"}[resultado]
            cor = {"A": VERDE, "B": (235, 70, 70), "EMPATE": AMARELO}[resultado]
            s = fonte_g.render(msg + "   -   R para novo round", True, cor)
            tela.blit(s, (CX - s.get_width() // 2, ALT - 34))
        elif pausado:
            s = fonte_g.render("PAUSADO", True, AMARELO)
            tela.blit(s, (CX - s.get_width() // 2, ALT - 34))

        pygame.display.flip()
        relogio.tick(50)


if __name__ == "__main__":
    main()