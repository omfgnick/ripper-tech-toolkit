"""Velocimetro do teste de velocidade.

ESCALA NAO LINEAR
Conexoes reais vao de 2 Mbps num rural a 1 Gbps numa fibra. Numa escala
linear de 0 a 1000, uma conexao de 20 Mbps ficaria colada no zero e o
ponteiro nao diria nada. As marcas abaixo sao distribuidas em passos
IGUAIS ao longo do arco, como fazem os medidores de velocidade de
internet - assim a faixa util aparece com resolucao em qualquer plano.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..tema import Cor, Fonte, familia
from . import chanfro

MARCAS = [0, 1, 5, 10, 25, 50, 100, 250, 500, 1000]

# Arco de 250 graus com a folga centrada embaixo. Para uma varredura S,
# o inicio precisa ser 90 + S/2 - qualquer outro valor deixa a abertura
# torta e o medidor parece tombado.
VARREDURA = 250.0
# Blocos do arco. Poucos viram degrau grosseiro; muitos viram arco
# continuo de novo e perdem o efeito de instrumento.
SEGMENTOS = 36
ANGULO_INICIAL = 90.0 + VARREDURA / 2


def _fracao(mbps: float) -> float:
    """Posicao de um valor no arco, de 0 a 1, pela escala em passos."""
    if mbps <= MARCAS[0]:
        return 0.0
    if mbps >= MARCAS[-1]:
        return 1.0

    for i in range(len(MARCAS) - 1):
        a, b = MARCAS[i], MARCAS[i + 1]
        if a <= mbps <= b:
            # Interpola dentro do segmento; cada segmento ocupa a mesma
            # fatia do arco, independente da diferenca numerica.
            dentro = (mbps - a) / (b - a) if b > a else 0.0
            return (i + dentro) / (len(MARCAS) - 1)
    return 1.0


class Velocimetro(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(260, 210)

        self._alvo = 0.0        # valor recebido da medicao
        self._atual = 0.0       # valor desenhado, que persegue o alvo
        self._rotulo = "pronto"
        self._ativo = False

        # O ponteiro persegue o valor em vez de saltar. Medicao de rede
        # oscila muito entre leituras; sem amortecer, o ponteiro tremeria
        # e o numero ficaria ilegivel.
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._passo)

    # ------------------------------------------------------------------
    def definir_valor(self, mbps: float) -> None:
        self._alvo = max(0.0, float(mbps))
        if not self._timer.isActive():
            self._timer.start()

    def definir_rotulo(self, texto: str) -> None:
        self._rotulo = texto
        self.update()

    def iniciar(self, rotulo: str = "medindo...") -> None:
        self._ativo = True
        self._alvo = 0.0
        self._atual = 0.0
        self._rotulo = rotulo
        self._timer.start()
        self.update()

    def encerrar(self, rotulo: str = "concluído") -> None:
        self._ativo = False
        self._rotulo = rotulo
        self.update()

    def zerar(self) -> None:
        self._ativo = False
        self._alvo = self._atual = 0.0
        self._rotulo = "pronto"
        self._timer.stop()
        self.update()

    def _passo(self) -> None:
        delta = self._alvo - self._atual
        if abs(delta) < 0.05:
            self._atual = self._alvo
            if not self._ativo:
                self._timer.stop()
        else:
            # 0.18 da distancia por quadro: alcanca rapido sem estourar.
            self._atual += delta * 0.18
        self.update()

    # ------------------------------------------------------------------
    def _brilho(self, p, desenhar, cor: str, camadas=((3.4, 26), (2.0, 44))):
        """Repinta a mesma forma mais grossa e translucida, por baixo.

        E bloom de pobre, e e o suficiente: o Qt nao tem blur barato em
        QPainter, e um QGraphicsEffect por widget custa uma textura
        inteira a cada quadro num mostrador que redesenha a 60 Hz.
        """
        base = QColor(cor)
        for fator, alfa in camadas:
            c = QColor(base)
            c.setAlpha(alfa)
            desenhar(c, fator)

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        lado = min(self.width(), self.height() * 1.22)
        cx = self.width() / 2
        cy = self.height() * 0.52
        raio = lado * 0.345
        caixa = QRectF(cx - raio, cy - raio, raio * 2, raio * 2)
        fracao = _fracao(self._atual)
        cor_ativa = Cor.DESTAQUE if self._ativo else Cor.OK

        # ---- moldura tecnica ----
        chanfro.marcar_cantos(p, QRectF(self.rect()).adjusted(3, 3, -3, -3),
                              Cor.DESTAQUE_FOSCO, 2.0, 0.10)

        # ---- arco segmentado ----
        # Medidor do jogo e feito de blocos, nao de arco continuo. Cada
        # bloco acende inteiro, o que torna a leitura discreta e faz o
        # mostrador parecer instrumento em vez de barra de progresso.
        espessura = raio * 0.15
        passo = VARREDURA / SEGMENTOS
        vao = passo * 0.22
        acesos = fracao * SEGMENTOS

        for n in range(SEGMENTOS):
            inicio = ANGULO_INICIAL - n * passo
            aceso = n < acesos
            cor = QColor(cor_ativa if aceso else Cor.BORDA)
            if not aceso:
                cor.setAlpha(150)

            def bloco(c, largura=1.0, inicio=inicio, extensao=passo - vao):
                caneta = QPen(c, espessura * largura)
                caneta.setCapStyle(Qt.FlatCap)
                p.setPen(caneta)
                p.drawArc(caixa, int(inicio * 16), int(-extensao * 16))

            if aceso:
                self._brilho(p, bloco, cor_ativa)
            bloco(cor)

        # ---- marcas e numeros ----
        p.setFont(QFont(Fonte.MONO, max(6, int(raio * 0.085))))
        for i, valor in enumerate(MARCAS):
            f = i / (len(MARCAS) - 1)
            ang = math.radians(ANGULO_INICIAL - VARREDURA * f)
            dx, dy = math.cos(ang), -math.sin(ang)

            p.setPen(QPen(QColor(Cor.DESTAQUE_FOSCO), 1.6))
            p.drawLine(QPointF(cx + dx * raio * 1.02, cy + dy * raio * 1.02),
                       QPointF(cx + dx * raio * 1.10, cy + dy * raio * 1.10))

            # Numeros FORA do arco: dentro, eles caiam em cima da leitura
            # central e das pontas do proprio arco.
            p.setPen(QColor(Cor.TEXTO_FRACO))
            largura = raio * 0.44
            p.drawText(
                QRectF(cx + dx * raio * 1.19 - largura / 2,
                       cy + dy * raio * 1.19 - raio * 0.11,
                       largura, raio * 0.22),
                Qt.AlignCenter, str(valor))

        # ---- ponteiro ----
        ang = math.radians(ANGULO_INICIAL - VARREDURA * fracao)
        dx, dy = math.cos(ang), -math.sin(ang)
        ponta = QPointF(cx + dx * raio * 0.70, cy + dy * raio * 0.70)
        cauda = QPointF(cx - dx * raio * 0.10, cy - dy * raio * 0.10)

        def agulha(c, largura=1.0):
            caneta = QPen(c, max(1.6, raio * 0.022) * largura)
            caneta.setCapStyle(Qt.FlatCap)
            p.setPen(caneta)
            p.drawLine(cauda, ponta)

        self._brilho(p, agulha, cor_ativa)
        agulha(QColor(Cor.TEXTO))

        # Losango no eixo, em vez de circulo: mantem a regra de nao ter
        # curva fechada em lugar nenhum da interface.
        eixo = raio * 0.06
        losango = QPainterPath()
        losango.moveTo(cx, cy - eixo)
        losango.lineTo(cx + eixo, cy)
        losango.lineTo(cx, cy + eixo)
        losango.lineTo(cx - eixo, cy)
        losango.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(cor_ativa))
        p.drawPath(losango)

        # ---- leitura ----
        texto = f"{self._atual:.1f}"
        caixa_leitura = QRectF(cx - raio, cy + raio * 0.20,
                               raio * 2, raio * 0.42)
        f = QFont(familia(), max(11, int(raio * 0.28)))
        f.setWeight(QFont.Bold)
        p.setFont(f)

        def leitura(c, _largura=1.0):
            p.setPen(c)
            p.drawText(caixa_leitura, Qt.AlignCenter, texto)

        if self._ativo:
            self._brilho(p, leitura, cor_ativa, camadas=((1, 30),))
        p.setPen(QColor(Cor.TEXTO))
        p.drawText(caixa_leitura, Qt.AlignCenter, texto)

        p.setFont(QFont(Fonte.MONO, max(7, int(raio * 0.095))))
        p.setPen(QColor(Cor.TEXTO_SUAVE))
        p.drawText(QRectF(cx - raio, cy + raio * 0.64, raio * 2, raio * 0.20),
                   Qt.AlignCenter, "Mbps")

        # Rotulo de situacao na base do widget, fora do arco
        f = QFont(Fonte.MONO, max(7, int(raio * 0.10)))
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
        p.setFont(f)
        p.setPen(QColor(cor_ativa if self._ativo else Cor.TEXTO_FRACO))
        p.drawText(QRectF(0, self.height() - raio * 0.34, self.width(),
                          raio * 0.30),
                   Qt.AlignCenter, self._rotulo.upper())

        p.end()
