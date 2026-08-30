"""Painel de programas instalados e itens de inicializacao."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...nucleo import bloatware, persistencia, programas
from ...nucleo.win import SEM_JANELA, formatar_bytes
from ...tema import Cor
from ..widgets import Botao
from .base import PainelBase


class PainelProgramas(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Programas e inicialização",
            "Lê o registro do Windows. A desinstalação abre o próprio "
            "instalador do programa — nada é removido por fora.",
            parent,
        )
        self._programas: list[programas.Programa] = []
        self._inicio: list[programas.ItemInicializacao] = []
        self._fabrica: list[bloatware.Pacote] = []
        self._tarefas: list[persistencia.Tarefa] = []
        self._extensoes: list[persistencia.Extensao] = []

        self.btn_ler = Botao("Atualizar lista", "primario")
        self.btn_ler.clicked.connect(self.carregar)
        self.acoes.addWidget(self.btn_ler)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Filtrar por nome...")
        self.busca.textChanged.connect(self._filtrar)
        self.busca.setMaximumWidth(260)
        self.acoes.addWidget(self.busca)
        self.acoes.addStretch(1)

        self.abas = QTabWidget()
        self.abas.setStyleSheet(
            f"QTabBar::tab {{ background: {Cor.PAINEL}; color: {Cor.TEXTO_SUAVE};"
            f" padding: 7px 16px; border: none; }}"
            f"QTabBar::tab:selected {{ color: {Cor.TEXTO};"
            f" border-bottom: 2px solid {Cor.DESTAQUE}; }}"
            f"QTabWidget::pane {{ border: none; }}"
        )

        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(["Programa", "Versão", "Fabricante", "Tamanho"])
        self.lista.setColumnWidth(0, 300)
        self.lista.setColumnWidth(1, 100)
        self.lista.setColumnWidth(2, 180)
        self.abas.addTab(self.lista, "Instalados")

        self.inicializacao = QTreeWidget()
        self.inicializacao.setHeaderLabels(["Item", "Origem", "Comando"])
        self.inicializacao.setColumnWidth(0, 200)
        self.inicializacao.setColumnWidth(1, 130)
        self.abas.addTab(self.inicializacao, "Inicialização")

        self.fabrica = QTreeWidget()
        self.fabrica.setHeaderLabels(["Aplicativo", "Categoria", "Pacote"])
        self.fabrica.setColumnWidth(0, 240)
        self.fabrica.setColumnWidth(1, 130)
        self.abas.addTab(self.fabrica, "De fábrica")

        self.persistencia = QTreeWidget()
        self.persistencia.setHeaderLabels(["Item", "Onde", "Detalhe"])
        self.persistencia.setColumnWidth(0, 280)
        self.persistencia.setColumnWidth(1, 130)
        self.abas.addTab(self.persistencia, "Tarefas e extensões")

        self.conteudo.addWidget(self.abas)

        self.btn_desinstalar = Botao("Desinstalar selecionado", "perigo")
        self.btn_desinstalar.clicked.connect(self.desinstalar)
        self.conteudo.addWidget(self.btn_desinstalar)

        self.btn_remover_inicio = Botao("Remover da inicialização", "perigo")
        self.btn_remover_inicio.clicked.connect(self.remover_do_inicio)
        self.btn_remover_inicio.hide()
        self.conteudo.addWidget(self.btn_remover_inicio)

        self.btn_remover_fabrica = Botao("Remover marcados", "perigo")
        self.btn_remover_fabrica.clicked.connect(self.remover_fabrica)
        self.btn_remover_fabrica.hide()
        self.conteudo.addWidget(self.btn_remover_fabrica)

        self.abas.currentChanged.connect(self._aba_mudou)

    def _aba_mudou(self, indice: int) -> None:
        self.btn_desinstalar.setVisible(indice == 0)
        self.btn_remover_inicio.setVisible(indice == 1)
        self.btn_remover_fabrica.setVisible(indice == 2)

    def carregar(self) -> None:
        if self.ocupado:
            return
        self.lista.clear()
        self.inicializacao.clear()
        self.fabrica.clear()
        self.persistencia.clear()
        self.btn_ler.setEnabled(False)
        self.rodar(programas.listar, self._programas_prontos)

    def _programas_prontos(self, lista) -> None:
        self._programas = lista
        self.btn_ler.setEnabled(True)
        for p in lista:
            QTreeWidgetItem(self.lista, [
                p.nome, p.versao, p.fabricante,
                formatar_bytes(p.tamanho_kb * 1024) if p.tamanho_kb else "—"])
        self.rodar(programas.listar_inicializacao, self._inicio_pronto)

    def _inicio_pronto(self, itens) -> None:
        self._inicio = itens
        for i in itens:
            QTreeWidgetItem(self.inicializacao, [i.nome, i.origem, i.comando])
        self.rodar(bloatware.instalados, self._fabrica_pronta)

    def _fabrica_pronta(self, pacotes) -> None:
        self._fabrica = pacotes
        for pacote in pacotes:
            item = QTreeWidgetItem(
                self.fabrica,
                [pacote.nome, pacote.categoria, pacote.identificador])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked)
        self.rodar(persistencia.tarefas, self._tarefas_prontas)

    def _tarefas_prontas(self, lista) -> None:
        self._tarefas = lista
        raiz = QTreeWidgetItem(self.persistencia,
                               [f"Tarefas agendadas ({len(lista)})", "", ""])
        raiz.setForeground(0, QBrush(QColor(Cor.DESTAQUE)))
        for t in lista:
            filho = QTreeWidgetItem(
                raiz, [t.nome, t.estado, t.acao or "(sem programa)"])
            if t.suspeita:
                # So o que tem indicio ganha cor: pintar tudo apagaria o
                # sinal de quem realmente merece olhada.
                filho.setForeground(0, QBrush(QColor(Cor.ATENCAO)))
                filho.setToolTip(0, t.motivo)
                QTreeWidgetItem(filho, ["", "", t.motivo])
        raiz.setExpanded(True)
        self.rodar(persistencia.extensoes, self._extensoes_prontas)

    def _extensoes_prontas(self, lista) -> None:
        self._extensoes = lista
        raiz = QTreeWidgetItem(self.persistencia,
                               [f"Extensões de navegador ({len(lista)})", "", ""])
        raiz.setForeground(0, QBrush(QColor(Cor.DESTAQUE)))
        for e in lista:
            filho = QTreeWidgetItem(
                raiz, [e.nome or e.identificador, e.navegador, e.descricao])
            filho.setToolTip(0, f"{e.identificador} — v{e.versao}")
        raiz.setExpanded(True)

    def remover_fabrica(self) -> None:
        if self.ocupado:
            return
        marcados = []
        for i in range(self.fabrica.topLevelItemCount()):
            item = self.fabrica.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                marcados.append(self._fabrica[i])
        if not marcados:
            self.anotar("Nenhum aplicativo marcado.")
            return

        quebra = chr(10)
        nomes = quebra.join(f"  • {p.nome}" for p in marcados)
        resposta = QMessageBox.question(
            self, "Confirmar remoção",
            f"Remover {len(marcados)} aplicativo(s) do perfil atual?"
            f"{quebra}{quebra}{nomes}{quebra}{quebra}"
            "Comando por item:" + quebra +
            "Remove-AppxPackage -Package <nome completo do pacote>",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return

        for p in self._fabrica:
            p.marcado = p in marcados
        self.btn_remover_fabrica.setEnabled(False)
        self.rodar(bloatware.remover, self._remocao_pronta, self._fabrica)

    def _remocao_pronta(self, r) -> None:
        self.btn_remover_fabrica.setEnabled(True)
        for nome, motivo in r.falharam:
            self.anotar(f"  falhou: {nome} — {motivo}")
        self.carregar()

    def _filtrar(self, texto: str) -> None:
        alvo = texto.strip().lower()
        for i in range(self.lista.topLevelItemCount()):
            item = self.lista.topLevelItem(i)
            item.setHidden(bool(alvo) and alvo not in item.text(0).lower())

    def desinstalar(self) -> None:
        item = self.lista.currentItem()
        if item is None:
            self.anotar("Selecione um programa na lista.")
            return

        alvo = next((p for p in self._programas if p.nome == item.text(0)), None)
        if alvo is None or not alvo.comando_desinstalar:
            self.anotar(f"'{item.text(0)}' não informa comando de desinstalação.")
            return

        if QMessageBox.question(
            self, "Desinstalar",
            f"Iniciar a desinstalação de:\n\n  {alvo.nome}\n\n"
            f"Comando:\n  {alvo.comando_desinstalar}\n\n"
            "O instalador do próprio programa será aberto.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return

        import subprocess
        try:
            # shell=True porque a string do registro ja vem com argumentos
            # e aspas no formato que o proprio instalador espera.
            subprocess.Popen(alvo.comando_desinstalar, shell=True,
                             creationflags=SEM_JANELA)
            self.anotar(f"Desinstalador de '{alvo.nome}' iniciado.")
        except Exception as erro:  # noqa: BLE001
            self.anotar(f"ERRO ao iniciar desinstalador: {erro}")

    def remover_do_inicio(self) -> None:
        item = self.inicializacao.currentItem()
        if item is None:
            self.anotar("Selecione um item de inicialização.")
            return

        alvo = next((i for i in self._inicio if i.nome == item.text(0)), None)
        if alvo is None:
            return

        if QMessageBox.question(
            self, "Remover da inicialização",
            f"Impedir que '{alvo.nome}' inicie com o Windows?\n\n"
            "O programa continua instalado — apenas não abre sozinho.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return

        try:
            programas.remover_da_inicializacao(alvo)
            self.anotar(f"'{alvo.nome}' removido da inicialização.")
            item.setHidden(True)
        except PermissionError:
            self.anotar("ERRO: item da máquina exige executar como administrador.")
        except Exception as erro:  # noqa: BLE001
            self.anotar(f"ERRO: {erro}")
