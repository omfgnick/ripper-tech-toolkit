"""Renderiza a janela principal para PNG, painel por painel."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tecnico.ui.janela import Janela  # noqa: E402


def capturar(janela: Janela, nome: str) -> Path:
    QApplication.processEvents()
    pix = QPixmap(janela.size())
    pix.fill(Qt.transparent)
    janela.render(pix)
    destino = RAIZ / "_previa" / f"{nome}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(destino))
    return destino


if __name__ == "__main__":
    app = QApplication(sys.argv)
    janela = Janela()
    janela.resize(1080, 660)
    # show() e necessario para o layout assentar; a janela e fechada
    # logo em seguida, entao nao fica nada na tela do operador.
    janela.show()
    for _ in range(3):
        QApplication.processEvents()

    quais = sys.argv[1:] or ["inicio", "diagnostico", "limpeza", "rede",
                             "programas", "reparo"]
    for chave in quais:
        janela.mostrar(chave)
        for _ in range(3):
            QApplication.processEvents()
        print("salvo:", capturar(janela, chave).name)

    janela.close()
