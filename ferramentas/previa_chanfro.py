"""Renderiza as formas chanfradas em PNG, para conferir sem abrir o app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication([])

from tecnico.tema import Cor
from tecnico.ui import chanfro

destino = sys.argv[1] if len(sys.argv) > 1 else "chanfro.png"
img = QImage(640, 270, QImage.Format_RGB32)
img.fill(QColor(Cor.FUNDO))
p = QPainter(img)

chanfro.pintar(p, QRectF(24, 24, 260, 92), Cor.PAINEL, Cor.DESTAQUE, 1.0)
chanfro.pintar(p, QRectF(320, 24, 260, 92), Cor.DESTAQUE, None, 1.0)
chanfro.pintar(p, QRectF(24, 152, 260, 92), Cor.PAINEL, Cor.DESTAQUE_FOSCO,
               1.0, cantos="sced")
chanfro.pintar(p, QRectF(320, 152, 260, 92), Cor.PAINEL, Cor.BORDA, 1.0)
chanfro.marcar_cantos(p, QRectF(320, 152, 260, 92), Cor.DESTAQUE, 2.0)
p.end()
img.save(destino)
print("gerado:", destino)
