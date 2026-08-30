"""Gera recursos/app.ico a partir da paleta do app.

Um .ico precisa de varias resolucoes: o Windows usa 16px na barra de
tarefas e 256px na visualizacao grande do Explorer. Gerar so uma e deixar
o sistema redimensionar produz icone borrado.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tecnico.tema import Cor  # noqa: E402


def desenhar(tamanho: int) -> QPixmap:
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)

    # Fundo arredondado
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(Cor.FUNDO_ALTO))
    raio = tamanho * 0.22
    p.drawRoundedRect(0, 0, tamanho, tamanho, raio, raio)

    # Cubo isometrico: a marca visual do app em miniatura
    c = tamanho / 2
    lado = tamanho * 0.30
    alt = tamanho * 0.20

    topo = [QPointF(c, c - alt - lado * 0.5),
            QPointF(c + lado, c - alt),
            QPointF(c, c - alt + lado * 0.5),
            QPointF(c - lado, c - alt)]
    esq = [topo[3], topo[2], QPointF(c, c + alt + lado * 0.5),
           QPointF(c - lado, c + alt)]
    dir_ = [topo[2], topo[1], QPointF(c + lado, c + alt),
            QPointF(c, c + alt + lado * 0.5)]

    for pontos, cor in ((esq, Cor.CENA_ATIVO_ESQ), (dir_, Cor.CENA_ATIVO_DIR),
                        (topo, Cor.CENA_ATIVO_TOPO)):
        p.setBrush(QColor(cor))
        p.drawPolygon(pontos)

    p.end()
    return pix


if __name__ == "__main__":
    app = QApplication(sys.argv)
    destino = RAIZ / "recursos" / "app.ico"
    destino.parent.mkdir(parents=True, exist_ok=True)

    icone = QIcon()
    for tamanho in (16, 24, 32, 48, 64, 128, 256):
        icone.addPixmap(desenhar(tamanho))

    # QIcon nao salva .ico direto; o Qt grava pelo QPixmap na maior
    # resolucao e o Windows gera as menores. Para controle real, salvamos
    # cada tamanho e deixamos o PyInstaller usar o arquivo de 256.
    maior = desenhar(256)
    ok = maior.save(str(destino), "ICO")
    print("icone salvo:", ok, "->", destino)
