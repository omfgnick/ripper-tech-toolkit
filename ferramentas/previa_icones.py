"""Renderiza a folha de icones em PNG, para conferir sem abrir o app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication([])

from tecnico.tema import Cor
from tecnico.ui import icones

destino = sys.argv[1] if len(sys.argv) > 1 else "icones.png"
lado, por_linha = 130, 4
nomes = list(icones.FORMAS)
linhas = (len(nomes) + por_linha - 1) // por_linha

img = QImage(lado * por_linha, lado * linhas, QImage.Format_RGB32)
img.fill(QColor(Cor.FUNDO))
p = QPainter(img)
for i, nome in enumerate(nomes):
    x, y = (i % por_linha) * lado, (i // por_linha) * lado
    icones.desenhar(nome, p, QRectF(x + 20, y + 20, lado - 40, lado - 40),
                    Cor.DESTAQUE)
p.end()
img.save(destino)
print("gerado:", destino, "|", len(nomes), "icones")
