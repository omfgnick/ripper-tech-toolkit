"""Painel de limpeza: varre, mostra o que sai, e so entao apaga."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...nucleo import limpeza, uso
from ...nucleo.win import formatar_bytes
from ...tema import Cor
from ..widgets import Botao, colunas_mono
from .base import PainelBase


class PainelLimpeza(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Limpeza de espaço",
            "Varre primeiro e mostra o que será removido. Documentos, área "
            "de trabalho e downloads nunca são tocados.",
            parent,
        )
        self._achados: list[limpeza.Achado] = []

        self.btn_varrer = Botao("Varrer", "primario")
        self.btn_varrer.clicked.connect(self.varrer)
        self.acoes.addWidget(self.btn_varrer)

        self.btn_limpar = Botao("Limpar selecionados", "perigo")
        self.btn_limpar.setEnabled(False)
        self.btn_limpar.clicked.connect(self.limpar)
        self.acoes.addWidget(self.btn_limpar)

        self.btn_lixeira = Botao("Esvaziar lixeira")
        self.btn_lixeira.clicked.connect(self.lixeira)
        self.acoes.addWidget(self.btn_lixeira)
        self.btn_pastas = Botao("Maiores pastas")
        self.btn_pastas.setToolTip(
            "Mede o tamanho real das pastas do disco. Não apaga nada.")
        self.btn_pastas.clicked.connect(self.medir_pastas)
        self.acoes.addWidget(self.btn_pastas)

        self.btn_processos = Botao("Processos")
        self.btn_processos.clicked.connect(self.ler_processos)
        self.acoes.addWidget(self.btn_processos)

        self.acoes.addStretch(1)

        self.total = QLabel("Nenhuma varredura executada.")
        self.total.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.conteudo.addWidget(self.total)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["Categoria", "Arquivos", "Tamanho"])
        self.arvore.setColumnWidth(0, 300)
        colunas_mono(self.arvore, 1, 2)
        self.arvore.itemChanged.connect(self._marcacao_mudou)
        self.abas = QTabWidget()
        self.abas.addTab(self.arvore, "Temporários")

        # A limpeza de temporarios acha dezenas de megabytes. A pergunta do
        # cliente e outra: "para onde foram os 400 GB". Estas duas abas
        # respondem isso - sem apagar nada, so mostrando onde esta.
        self.pastas = QTreeWidget()
        self.pastas.setHeaderLabels(["Pasta", "Arquivos", "Tamanho"])
        self.pastas.setColumnWidth(0, 420)
        colunas_mono(self.pastas, 1, 2)
        self.abas.addTab(self.pastas, "Maiores pastas")

        self.processos = QTreeWidget()
        self.processos.setHeaderLabels(
            ["Processo", "Memória", "CPU", "Usuário", "PID"])
        self.processos.setColumnWidth(0, 260)
        colunas_mono(self.processos, 1, 2, 4)
        self.abas.addTab(self.processos, "Processos")

        self.conteudo.addWidget(self.abas)

    def varrer(self) -> None:
        if self.ocupado:
            return
        self.arvore.clear()
        self.btn_varrer.setEnabled(False)
        self.btn_limpar.setEnabled(False)
        self.rodar(limpeza.varrer, self._varredura_pronta)

    def _varredura_pronta(self, achados) -> None:
        self._achados = achados
        self.btn_varrer.setEnabled(True)
        descricoes = {a.chave: a.descricao for a in limpeza.alvos()}

        self.arvore.blockSignals(True)
        for achado in achados:
            item = QTreeWidgetItem(self.arvore, [
                achado.titulo, str(achado.arquivos),
                formatar_bytes(achado.bytes_total)])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            marcar = achado.marcado and achado.arquivos > 0
            item.setCheckState(0, Qt.Checked if marcar else Qt.Unchecked)
            item.setToolTip(0, descricoes.get(achado.chave, ""))
            item.setData(0, Qt.UserRole, achado.chave)
            if achado.arquivos == 0:
                item.setDisabled(True)
        self.arvore.blockSignals(False)
        self._atualizar_total()

    def _marcacao_mudou(self, item, _coluna) -> None:
        chave = item.data(0, Qt.UserRole)
        for achado in self._achados:
            if achado.chave == chave:
                achado.marcado = item.checkState(0) == Qt.Checked
        self._atualizar_total()

    def _atualizar_total(self) -> None:
        selecionado = sum(a.bytes_total for a in self._achados if a.marcado)
        arquivos = sum(a.arquivos for a in self._achados if a.marcado)
        self.total.setText(
            f"Selecionado: {formatar_bytes(selecionado)} em {arquivos} arquivos.")
        self.btn_limpar.setEnabled(arquivos > 0)

    def limpar(self) -> None:
        if self.ocupado:
            return
        selecionados = [a for a in self._achados if a.marcado and a.arquivos]
        total = sum(a.bytes_total for a in selecionados)
        arquivos = sum(a.arquivos for a in selecionados)

        # Confirmacao com o numero na frente: apagar arquivo na maquina do
        # cliente nao pode acontecer por clique distraido.
        detalhe = "\n".join(f"  - {a.titulo}" for a in selecionados)
        resposta = QMessageBox.question(
            self, "Confirmar limpeza",
            f"Remover {arquivos} arquivos e liberar cerca de "
            f"{formatar_bytes(total)}?\n\n{detalhe}\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if resposta != QMessageBox.Yes:
            self.anotar("Limpeza cancelada pelo operador.")
            return

        self.btn_limpar.setEnabled(False)
        self.btn_varrer.setEnabled(False)
        self.rodar(limpeza.limpar, self._limpeza_pronta, self._achados)

    def _limpeza_pronta(self, resultado) -> None:
        self.btn_varrer.setEnabled(True)
        self.anotar(
            f"{resultado.removidos} removidos, "
            f"{formatar_bytes(resultado.bytes_liberados)} liberados, "
            f"{resultado.ignorados} ignorados (em uso).")
        self.varrer()

    def lixeira(self) -> None:
        if QMessageBox.question(
            self, "Esvaziar lixeira",
            "Esvaziar a lixeira de todas as unidades?\n\n"
            "O conteúdo não poderá mais ser recuperado.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        limpeza.esvaziar_lixeira()
        self.anotar("Lixeira esvaziada.")

    # ------------------------------------------------------------------
    def medir_pastas(self) -> None:
        if self.ocupado:
            return
        self.pastas.clear()
        self.btn_pastas.setEnabled(False)
        self.anotar("Medindo as maiores pastas. Leva alguns minutos...")
        self.rodar(uso.maiores_pastas, self._pastas_prontas)

    def _pastas_prontas(self, lista) -> None:
        self.btn_pastas.setEnabled(True)
        for pasta in lista:
            item = QTreeWidgetItem(self.pastas, [
                pasta.caminho,
                f"{pasta.arquivos:,}".replace(",", "."),
                formatar_bytes(pasta.bytes_total)])
            # Acima de 10 GB numa pasta so, vale a conversa com o cliente
            # antes de qualquer limpeza automatica.
            if pasta.bytes_total > 10 * 1024 ** 3:
                item.setForeground(2, QBrush(QColor(Cor.ATENCAO)))
        self.abas.setCurrentWidget(self.pastas)

    def ler_processos(self) -> None:
        if self.ocupado:
            return
        self.processos.clear()
        self.btn_processos.setEnabled(False)
        self.rodar(uso.processos, self._processos_prontos)

    def _processos_prontos(self, lista) -> None:
        self.btn_processos.setEnabled(True)
        for p in lista:
            item = QTreeWidgetItem(self.processos, [
                p.nome, formatar_bytes(p.memoria), f"{p.cpu:.1f}%",
                p.usuario, str(p.pid)])
            if p.memoria > 1024 ** 3:
                item.setForeground(1, QBrush(QColor(Cor.ATENCAO)))
        self.abas.setCurrentWidget(self.processos)
