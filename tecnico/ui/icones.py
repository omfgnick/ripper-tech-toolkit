"""Icones angulares desenhados em codigo.

Substituem os renders 3D estilo argila: aquele material tem luz suave e
canto arredondado, o oposto da linguagem desta interface. Aqui tudo e
linha reta e corte de 45 graus, no mesmo vocabulario das molduras.

DESENHADOS E NAO ARQUIVOS
    Um SVG por icone seria mais convencional, mas estes precisam mudar de
    cor conforme o estado da verificacao - amarelo parado, ciano quando
    passou, vermelho quando falhou. Recolorir SVG em tempo de execucao no
    Qt exige reescrever o XML ou aplicar mascara; desenhar direto resolve
    numa linha e o icone nasce nitido em qualquer tamanho.

    O desenho e normalizado numa caixa de 100x100 e escalado pelo destino,
    entao a espessura do traco acompanha o tamanho.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

LADO = 100.0


def _p(*pontos: tuple[float, float]) -> QPainterPath:
    caminho = QPainterPath()
    caminho.moveTo(QPointF(*pontos[0]))
    for ponto in pontos[1:]:
        caminho.lineTo(QPointF(*ponto))
    return caminho


def _fechado(*pontos: tuple[float, float]) -> QPainterPath:
    caminho = _p(*pontos)
    caminho.closeSubpath()
    return caminho


def _monitor() -> list[QPainterPath]:
    return [
        _fechado((14, 22), (78, 22), (86, 30), (86, 66), (14, 66)),
        _p((44, 66), (44, 78)),
        _p((28, 78), (72, 78)),
        _p((26, 36), (40, 36)),
        _p((26, 46), (58, 46)),
        _p((26, 56), (48, 56)),
    ]


def _wifi() -> list[QPainterPath]:
    """Ondas de sinal sem curva.

    A primeira versao usava diagonais de 45 graus e o icone lia como
    telhado de casa. O que resolve e alongar o trecho horizontal: e o topo
    reto que faz o olho reconhecer arco, nao o angulo das pontas.
    """
    return [
        _p((12, 48), (26, 30), (74, 30), (88, 48)),
        _p((26, 60), (37, 46), (63, 46), (74, 60)),
        _p((39, 72), (45, 64), (55, 64), (61, 72)),
        _fechado((46, 80), (54, 80), (54, 88), (46, 88)),
    ]


def _lixeira() -> list[QPainterPath]:
    return [
        _p((22, 28), (78, 28)),
        _fechado((40, 20), (60, 20), (60, 28), (40, 28)),
        _fechado((28, 28), (72, 28), (66, 84), (34, 84)),
        _p((44, 40), (46, 72)),
        _p((56, 40), (54, 72)),
    ]


def _documento() -> list[QPainterPath]:
    return [
        _fechado((26, 14), (62, 14), (76, 28), (76, 86), (26, 86)),
        _p((62, 14), (62, 28), (76, 28)),
        _p((36, 42), (66, 42)),
        _p((36, 54), (66, 54)),
        _p((36, 66), (52, 66)),
    ]


def _pacote() -> list[QPainterPath]:
    return [
        _fechado((50, 14), (84, 32), (84, 68), (50, 86), (16, 68), (16, 32)),
        _p((16, 32), (50, 50), (84, 32)),
        _p((50, 50), (50, 86)),
    ]


def _seta_baixo() -> list[QPainterPath]:
    return [
        _p((50, 16), (50, 60)),
        _p((32, 44), (50, 62), (68, 44)),
        _p((20, 74), (20, 84), (80, 84), (80, 74)),
    ]


def _engrenagem() -> list[QPainterPath]:
    dentes = []
    for i in range(8):
        ang = i * 45
        import math
        r1, r2 = 30.0, 40.0
        rad = math.radians(ang)
        largura = math.radians(11)
        pontos = []
        for raio, delta in ((r1, -largura), (r2, -largura * 0.6),
                            (r2, largura * 0.6), (r1, largura)):
            pontos.append((50 + raio * math.cos(rad + delta),
                           50 + raio * math.sin(rad + delta)))
        dentes.append(_fechado(*pontos))
    anel = QPainterPath()
    anel.addEllipse(QRectF(20, 20, 60, 60))
    miolo = QPainterPath()
    miolo.addEllipse(QRectF(38, 38, 24, 24))
    return [anel, miolo, *dentes]


def _grafico() -> list[QPainterPath]:
    return [
        _p((18, 16), (18, 84), (86, 84)),
        _fechado((30, 60), (42, 60), (42, 84), (30, 84)),
        _fechado((48, 42), (60, 42), (60, 84), (48, 84)),
        _fechado((66, 26), (78, 26), (78, 84), (66, 84)),
    ]


FORMAS = {
    "monitor": _monitor,
    "wifi": _wifi,
    "lixeira": _lixeira,
    "documento": _documento,
    "pacote": _pacote,
    "seta_baixo": _seta_baixo,
    "engrenagem": _engrenagem,
    "grafico": _grafico,
}


def desenhar(nome: str, pintor: QPainter, destino: QRectF, cor: str,
             espessura: float = 2.6) -> bool:
    """Desenha o icone dentro de `destino`. Devolve False se nao existir."""
    fabrica = FORMAS.get(nome)
    if fabrica is None:
        return False

    escala = min(destino.width(), destino.height()) / LADO
    pintor.save()
    pintor.setRenderHint(QPainter.Antialiasing, True)
    pintor.translate(destino.center())
    pintor.scale(escala, escala)
    pintor.translate(-LADO / 2, -LADO / 2)

    caneta = QPen(QColor(cor), espessura)
    caneta.setJoinStyle(Qt.MiterJoin)
    caneta.setCapStyle(Qt.SquareCap)
    pintor.setPen(caneta)
    pintor.setBrush(Qt.NoBrush)
    for forma in fabrica():
        pintor.drawPath(forma)
    pintor.restore()
    return True
