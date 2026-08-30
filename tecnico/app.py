"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from .nucleo import falhas
from .tema import registrar_fontes
from .ui.janela import APLICATIVO, Janela


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APLICATIVO)
    app.setStyle("Fusion")

    # Antes de qualquer janela: duas instancias gravam historico e ficha
    # uma por cima da outra, e nenhuma das duas percebe.
    if not falhas.instancia_unica():
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            None, APLICATIVO,
            f"O {APLICATIVO} já está aberto." + chr(10) + chr(10)
            + "Duas cópias gravariam o histórico e a ficha desta máquina "
            "uma por cima da outra. Use a janela que já está aberta.")
        return 0

    # Antes de qualquer widget: a folha de estilo consulta a familia
    # carregada, e widget criado antes ficaria com a fonte errada.
    if not registrar_fontes():
        print("aviso: Rajdhani nao encontrada, usando fonte do sistema",
              file=sys.stderr)

    janela = Janela()
    janela.show()

    def avisar_falha(caminho, resumo: str) -> None:
        """Mostra onde o traceback foi parar, em vez de fechar calado."""
        from PySide6.QtWidgets import QMessageBox

        onde = (f"O relatório foi salvo em:{chr(10)}{caminho}"
                if caminho else "Não foi possível salvar o relatório.")
        QMessageBox.critical(
            janela, f"{APLICATIVO} — falha inesperada",
            f"{resumo}{chr(10)}{chr(10)}{onde}")

    falhas.instalar_excecoes(avisar_falha)

    from .ui.abertura import Abertura

    abertura = Abertura(janela)
    # A verificacao so comeca quando a abertura sai. Rodar por baixo faria
    # o ping competir com a animacao e a tela apareceria ja mexendo.
    abertura.concluida.connect(
        lambda: QTimer.singleShot(80, janela.iniciar_verificacao))
    abertura.comecar()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
