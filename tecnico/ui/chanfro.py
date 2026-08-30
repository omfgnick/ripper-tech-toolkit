"""Formas chanfradas e molduras tecnicas do visual Cyberpunk 2077.

Canto cortado em 45 graus, nunca arredondado. E a assinatura da interface
do jogo e o QSS nao sabe fazer: `border-radius` so arredonda. Entao o
desenho vem daqui, por QPainter, e os widgets pintam a si mesmos.

MARCACAO DE CANTO
    Alem do corte, os paineis do jogo tem tracinhos curtos nos cantos -
    como mira de camera. Custam duas linhas por canto e sao o detalhe que
    faz a moldura parecer instrumento em vez de retangulo.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

# Tamanho do corte. Grande demais vira losango; pequeno demais some.
CHANFRO = 10.0
# Comprimento do tracinho de canto, em fracao do lado menor.
MARCA = 0.16


def caminho(rect: QRectF, chanfro: float = CHANFRO,
            cantos: str = "sd") -> QPainterPath:
    """Retangulo com cantos cortados.

    `cantos` diz quais cortar, por iniciais: s=superior esquerdo,
    d=inferior direito, e=inferior esquerdo, c=superior direito. O padrao
    corta a diagonal principal, que e o arranjo mais comum no jogo -
    cortar os quatro deixa a forma simetrica demais e perde o movimento.
    """
    c = min(chanfro, rect.width() / 2, rect.height() / 2)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    p = QPainterPath()
    p.moveTo(x + (c if "s" in cantos else 0), y)
    p.lineTo(x + w - (c if "c" in cantos else 0), y)
    if "c" in cantos:
        p.lineTo(x + w, y + c)
    p.lineTo(x + w, y + h - (c if "d" in cantos else 0))
    if "d" in cantos:
        p.lineTo(x + w - c, y + h)
    p.lineTo(x + (c if "e" in cantos else 0), y + h)
    if "e" in cantos:
        p.lineTo(x, y + h - c)
    p.lineTo(x, y + (c if "s" in cantos else 0))
    p.closeSubpath()
    return p


def pintar(pintor: QPainter, rect: QRectF, fundo: str | None,
           borda: str | None, espessura: float = 1.0,
           chanfro: float = CHANFRO, cantos: str = "sd") -> None:
    """Preenche e contorna uma forma chanfrada."""
    pintor.setRenderHint(QPainter.Antialiasing, True)
    forma = caminho(rect.adjusted(espessura / 2, espessura / 2,
                                  -espessura / 2, -espessura / 2),
                    chanfro, cantos)
    if fundo:
        pintor.fillPath(forma, QColor(fundo))
    if borda:
        caneta = QPen(QColor(borda), espessura)
        caneta.setJoinStyle(Qt.MiterJoin)
        pintor.strokePath(forma, caneta)


def marcar_cantos(pintor: QPainter, rect: QRectF, cor: str,
                  espessura: float = 2.0, fracao: float = MARCA) -> None:
    """Tracinhos de mira nos quatro cantos, por fora da moldura."""
    comprimento = min(rect.width(), rect.height()) * fracao
    caneta = QPen(QColor(cor), espessura)
    caneta.setCapStyle(Qt.FlatCap)
    pintor.setPen(caneta)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    for canto_x, canto_y, dx, dy in (
        (x, y, 1, 1), (x + w, y, -1, 1),
        (x, y + h, 1, -1), (x + w, y + h, -1, -1),
    ):
        pintor.drawLine(QPointF(canto_x, canto_y),
                        QPointF(canto_x + dx * comprimento, canto_y))
        pintor.drawLine(QPointF(canto_x, canto_y),
                        QPointF(canto_x, canto_y + dy * comprimento))
