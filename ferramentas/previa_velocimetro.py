"""Renderiza o velocimetro em varios valores, para conferir sem medir."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication([])

from tecnico.tema import Cor, registrar_fontes
registrar_fontes()
from tecnico.ui.velocimetro import Velocimetro

destino = sys.argv[1] if len(sys.argv) > 1 else "velocimetro.png"
valores = [(0.0, False, "parado"), (12.0, True, "baixando..."),
           (94.0, True, "baixando..."), (340.0, False, "concluído")]

largura, altura = 264, 244
folha = QPixmap(largura * len(valores), altura)
folha.fill(QColor(Cor.FUNDO))

from PySide6.QtGui import QPainter
pintor = QPainter(folha)
for i, (valor, ativo, rotulo) in enumerate(valores):
    v = Velocimetro()
    v.setFixedSize(largura, altura)
    v._ativo = ativo
    v._atual = valor
    v._alvo = valor
    v._rotulo = rotulo
    peca = QPixmap(largura, altura)
    peca.fill(Qt.transparent)
    v.render(peca)
    pintor.drawPixmap(i * largura, 0, peca)
pintor.end()
folha.save(destino)
print("gerado:", destino)
