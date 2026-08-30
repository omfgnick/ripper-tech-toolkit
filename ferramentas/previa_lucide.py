"""Renderiza os icones Lucide recoloridos, para conferir o estilo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication([])

from tecnico.tema import Cor
from tecnico.ui import icones

NOMES = ["route", "activity", "trash-2", "wifi", "package",
         "wrench", "hard-drive-download", "chart-column",
         "clipboard-check", "file-clock"]
CORES = [Cor.DESTAQUE, Cor.OK, Cor.ERRO]

destino = sys.argv[1] if len(sys.argv) > 1 else "lucide.png"
lado, por_linha = 130, 5
linhas = (len(NOMES) + por_linha - 1) // por_linha
img = QImage(lado * por_linha, lado * linhas * len(CORES), QImage.Format_RGB32)
img.fill(QColor(Cor.FUNDO))
p = QPainter(img)
for c, cor in enumerate(CORES):
    for i, nome in enumerate(NOMES):
        x = (i % por_linha) * lado
        y = (c * linhas + i // por_linha) * lado
        icones.desenhar_svg(nome, p, QRectF(x + 26, y + 26, lado - 52,
                                            lado - 52), cor)
p.end()
img.save(destino)
print("gerado:", destino)
