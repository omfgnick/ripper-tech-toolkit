"""Captura um painel DEPOIS de a verificacao real terminar.

Diferente de previa_janela.py, que fotografa o estado parado, aqui o app
roda o diagnostico de rede e a varredura de disco de verdade e so entao
tira a foto - e assim que se ve se os rotulos e as cores respondem.

    python ferramentas/previa_viva.py [painel]
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import Qt, QThreadPool, QTimer  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tecnico.ui.janela import Janela  # noqa: E402

if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else "inicio"

    app = QApplication(sys.argv)
    janela = Janela()
    janela.resize(1080, 660)
    janela.show()
    janela.mostrar(alvo)
    QApplication.processEvents()

    janela.iniciar_verificacao()

    def capturar():
        # Drena o pool antes de fotografar: capturar no meio da varredura
        # registraria um estado intermediario, e fechar com tarefa viva
        # derruba o processo.
        QThreadPool.globalInstance().waitForDone(20000)
        janela.mostrar(alvo)
        QApplication.processEvents()

        pix = QPixmap(janela.size())
        pix.fill(Qt.transparent)
        janela.render(pix)
        destino = RAIZ / "_previa" / f"{alvo}.png"
        destino.parent.mkdir(parents=True, exist_ok=True)
        ok = pix.save(str(destino))
        print("salvo:" if ok else "FALHOU:", destino)
        janela.close()
        app.quit()

    QTimer.singleShot(25000, capturar)
    app.exec()
