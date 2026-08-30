"""Icone na area de notificacao e o fechar que minimiza.

Numa bancada o Ripper fica aberto o dia inteiro entre uma maquina e
outra, e nao faz sentido reabri-lo a cada atendimento - o historico e a
ficha ja estao carregados. Fechar passa a recolher para a bandeja; sair
de verdade e uma escolha explicita no menu do icone.

POR QUE ISSO NAO E SO CONVENIENCIA
    Duas copias gravam historico e ficha uma por cima da outra. Se fechar
    encerra o processo, o tecnico reabre varias vezes ao dia e cada
    abertura e uma chance de rodar duas por engano. Recolher para a
    bandeja remove essa chance.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class Bandeja(QSystemTrayIcon):
    def __init__(self, janela, aplicativo: str):
        from .. import recursos

        caminho = recursos.icone_do_app()
        super().__init__(QIcon(str(caminho)) if caminho.is_file() else QIcon(),
                         janela)
        self.janela = janela
        self.aplicativo = aplicativo
        self._avisou = False

        self.setToolTip(f"{aplicativo} — atendimento técnico")

        menu = QMenu()
        abrir = QAction("Abrir", menu)
        abrir.triggered.connect(self.restaurar)
        menu.addAction(abrir)
        menu.addSeparator()
        sair = QAction("Sair do Ripper", menu)
        sair.triggered.connect(self.sair)
        menu.addAction(sair)
        self.setContextMenu(menu)
        self._menu = menu      # o QMenu precisa de referencia viva

        self.activated.connect(self._clicou)

    # ------------------------------------------------------------------
    def _clicou(self, motivo) -> None:
        if motivo in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restaurar()

    def restaurar(self) -> None:
        from PySide6.QtCore import Qt

        self.janela.showNormal()
        # Sem limpar o bit de minimizado, showNormal em janela recolhida
        # da bandeja restaura mas nao vem para a frente.
        self.janela.setWindowState(
            self.janela.windowState() & ~Qt.WindowMinimized)
        self.janela.raise_()
        self.janela.activateWindow()

    def recolher(self) -> None:
        self.janela.hide()
        if not self._avisou:
            # So na primeira vez: repetir o balao todo dia vira ruido.
            self.showMessage(
                self.aplicativo,
                "Continua rodando aqui. Clique no ícone para voltar, ou "
                "use 'Sair do Ripper' para encerrar.",
                QSystemTrayIcon.Information, 4000)
            self._avisou = True

    def sair(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.janela.encerrar_de_verdade = True
        self.hide()
        self.janela.close()
        aplicacao = QApplication.instance()
        if aplicacao is not None:
            aplicacao.quit()
