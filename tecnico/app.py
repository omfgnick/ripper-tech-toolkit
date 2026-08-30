"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from . import recursos
from .nucleo import falhas
from .tema import aplicar_tema, registrar_fontes, tema_gravado
from .ui.janela import APLICATIVO, Janela


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APLICATIVO)
    app.setStyle("Fusion")

    # Sem isto a janela e a barra de tarefas ficam com o icone generico do
    # Qt: --icon do PyInstaller decora so o arquivo .exe.
    caminho_icone = recursos.icone_do_app()
    if caminho_icone.is_file():
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(caminho_icone)))

    # Antes de qualquer janela: duas instancias gravam historico e ficha
    # uma por cima da outra, e nenhuma das duas percebe.
    if not falhas.instancia_unica():
        # Trazer a existente para a frente e sair calado: o tecnico clicou
        # duas vezes no icone querendo o app, nao um aviso. So avisa se
        # nao achar a janela - ai o silencio pareceria que nada aconteceu.
        from .ui.janela import VERSAO

        if falhas.focar_instancia_existente(f"{APLICATIVO} {VERSAO}"):
            return 0

        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            None, APLICATIVO,
            f"O {APLICATIVO} já está aberto." + chr(10) + chr(10)
            + "Duas cópias gravariam o histórico e a ficha desta máquina "
            "uma por cima da outra. Procure a janela ou o ícone na área "
            "de notificação.")
        return 0

    # Antes de qualquer widget: a folha de estilo consulta a familia
    # carregada, e widget criado antes ficaria com a fonte errada.
    aplicar_tema(tema_gravado())

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
