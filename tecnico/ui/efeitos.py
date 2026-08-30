"""Scanline e glitch: o tempero do visual, nao o prato.

A regra que toda analise do HUD repete e "um efeito de glitch por tela".
Aqui ela vai um passo alem, por causa do uso: isto e ferramenta de
bancada, aberta oito horas seguidas. Efeito que pisca sozinho o tempo
todo vira ruido e cansa - o oposto do que faz num jogo, onde a sessao
tem hora para acabar.

Entao:

    SCANLINE  estatica e permanente, alpha baixissimo. Da a textura de
              monitor CRT sem competir com o texto.

    VINHETA   escurecimento radial nas bordas. O HUD do jogo e curvado
              por um shader, para parecer projetado dentro dos olhos do
              personagem e nao colado na tela. Distorcer de verdade
              exigiria renderizar a janela numa textura a cada quadro;
              a vinheta compra 90% da leitura por quase nada, porque o
              que o olho registra como curvatura e a queda de luz nas
              quinas, nao a geometria.

    GLITCH    so na TROCA DE PAINEL, por 260 ms. E um evento com comeco e
              fim, ligado a uma acao do tecnico. Enquanto ele le, a tela
              fica parada.

O overlay ignora o mouse (WA_TransparentForMouseEvents): sem isso ele
engoliria todo clique da janela.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..tema import Cor

# Espacamento das linhas. Em 2px a tela vira grade e o texto sofre; em
# 4px o efeito some. 3px e o meio termo em telas 1080p e maiores.
PASSO_SCANLINE = 3
ALPHA_SCANLINE = 14
# Quina no maximo. Acima disso o canto vira mancha e some texto.
ALPHA_VINHETA = 92
DURACAO_GLITCH = 260          # ms
QUADRO = 33                   # ms entre repinturas durante o glitch
FATIAS = 7


class Sobreposicao(QWidget):
    """Camada de efeito por cima de tudo. Nao recebe eventos."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._restante = 0
        self._fatias: list[tuple[int, int, int]] = []
        self._relogio = QTimer(self)
        self._relogio.setInterval(QUADRO)
        self._relogio.timeout.connect(self._passo)

    # ------------------------------------------------------------------
    def disparar_glitch(self) -> None:
        self._restante = DURACAO_GLITCH
        self._sortear()
        if not self._relogio.isActive():
            self._relogio.start()
        self.update()

    def _sortear(self) -> None:
        altura = max(self.height(), 1)
        self._fatias = []
        for _ in range(FATIAS):
            topo = random.randint(0, altura - 1)
            espessura = random.randint(2, 14)
            # Deslocamento sempre pequeno: fatia jogada longe demais le
            # como falha de renderizacao, nao como estetica.
            desvio = random.randint(-18, 18)
            self._fatias.append((topo, espessura, desvio))

    def _passo(self) -> None:
        self._restante -= QUADRO
        if self._restante <= 0:
            self._relogio.stop()
            self._fatias = []
        elif random.random() < 0.5:
            self._sortear()
        self.update()

    # ------------------------------------------------------------------
    def _vinheta(self, pintor: QPainter) -> None:
        largura, altura = self.width(), self.height()
        if largura < 2 or altura < 2:
            return

        centro = QPointF(largura / 2, altura / 2)
        # Raio pela diagonal: assim as quinas ficam no fim do gradiente e
        # escurecem mais que o meio das bordas, que e justamente o que
        # uma tela curva faz.
        raio = ((largura / 2) ** 2 + (altura / 2) ** 2) ** 0.5

        gradiente = QRadialGradient(centro, raio)
        gradiente.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradiente.setColorAt(0.62, QColor(0, 0, 0, 0))
        gradiente.setColorAt(0.85, QColor(0, 0, 0, 38))
        gradiente.setColorAt(1.0, QColor(0, 0, 0, ALPHA_VINHETA))
        pintor.fillRect(self.rect(), gradiente)

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)

        self._vinheta(pintor)

        linha = QColor(0, 0, 0, ALPHA_SCANLINE)
        for y in range(0, self.height(), PASSO_SCANLINE):
            pintor.fillRect(0, y, self.width(), 1, linha)

        if not self._fatias:
            return

        # Fatias em amarelo e ciano com alpha baixo: imitam a aberracao
        # cromatica sem precisar recompor a imagem da janela por canal,
        # que custaria caro e piscaria a cada quadro.
        amarelo = QColor(Cor.DESTAQUE)
        amarelo.setAlpha(38)
        ciano = QColor(Cor.OK)
        ciano.setAlpha(30)

        for i, (topo, espessura, desvio) in enumerate(self._fatias):
            cor = amarelo if i % 2 else ciano
            pintor.fillRect(QRect(desvio, topo, self.width(), espessura), cor)
