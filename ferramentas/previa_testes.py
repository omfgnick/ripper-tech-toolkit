"""Renderiza os testes de tela e teclado em PNG, sem abrir tela cheia."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication([])

from tecnico.tema import registrar_fontes
registrar_fontes()
from tecnico.ui.testes import TesteDeTeclado, TesteDeTela

destino = sys.argv[1] if len(sys.argv) > 1 else "."

t = TesteDeTeclado()
t.resize(1280, 720)
t._testadas = {"Q", "W", "E", "A", "S", "Espaço", "Enter", "Esc", "F5"}
px = QPixmap(1280, 720)
px.fill(Qt.transparent)
t.render(px)
px.save(f"{destino}/teste_teclado.png")

v = TesteDeTela()
v.resize(1280, 400)
v._indice = 3
px2 = QPixmap(1280, 400)
px2.fill(Qt.transparent)
v.render(px2)
px2.save(f"{destino}/teste_tela.png")
print("gerados")
