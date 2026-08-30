"""Painel do roteiro: a sequencia inteira de atendimento num clique."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...nucleo import roteiro
from ...nucleo.win import formatar_bytes
from ...tema import Cor, Fonte
from ..widgets import Botao, colunas_mono
from .base import PainelBase

CORES_SITUACAO = {"melhorou": Cor.OK, "piorou": Cor.ERRO,
                  "neutro": Cor.TEXTO_SUAVE}


class PainelRoteiro(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Roteiro de atendimento",
            "Executa a sequência inteira na ordem certa e termina no PDF. "
            "As etapas que alteram a máquina vêm desmarcadas.",
            parent,
        )
        self._etapas = roteiro.etapas()
        self._destino = ""

        self.btn_rodar = Botao("Executar roteiro", "primario")
        self.btn_rodar.clicked.connect(self.executar)
        self.acoes.addWidget(self.btn_rodar)

        self.btn_destino = Botao("Onde salvar o PDF")
        self.btn_destino.clicked.connect(self.escolher_destino)
        self.acoes.addWidget(self.btn_destino)
        self.acoes.addStretch(1)

        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(["Etapa", "O que faz"])
        self.lista.setColumnWidth(0, 320)
        self.lista.setFixedHeight(210)
        self._montar_lista()
        self.conteudo.addWidget(self.lista)

        self.resultado = QTreeWidget()
        self.resultado.setHeaderLabels(
            ["Indicador", "Antes", "Depois", "Variação"])
        self.resultado.setColumnWidth(0, 260)
        colunas_mono(self.resultado, 1, 2, 3)
        self.resultado.hide()
        self.conteudo.addWidget(self.resultado)

        self.rodape = QLabel("Nenhum roteiro executado.")
        self.rodape.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.rodape.setWordWrap(True)
        self.conteudo.addWidget(self.rodape)

    # ------------------------------------------------------------------
    def _montar_lista(self) -> None:
        for etapa in self._etapas:
            item = QTreeWidgetItem(self.lista, [etapa.titulo, etapa.descricao])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.Checked if etapa.marcada else Qt.Unchecked)
            item.setData(0, Qt.UserRole, etapa.chave)
            if etapa.altera:
                # Cor so nas que mexem na maquina: e o unico aviso visivel
                # antes de o tecnico marcar a caixa.
                item.setForeground(0, QBrush(QColor(Cor.ATENCAO)))
                item.setToolTip(0, "Esta etapa altera a máquina.")

    def _marcadas(self) -> set[str]:
        escolhidas = set()
        for i in range(self.lista.topLevelItemCount()):
            item = self.lista.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                escolhidas.add(item.data(0, Qt.UserRole))
        return escolhidas

    def escolher_destino(self) -> None:
        caminho, _f = QFileDialog.getSaveFileName(
            self, "Onde salvar o PDF do roteiro", self._destino,
            "Documento PDF (*.pdf)")
        if caminho:
            self._destino = caminho
            self.anotar(f"PDF será salvo em {caminho}")

    # ------------------------------------------------------------------
    def executar(self) -> None:
        if self.ocupado:
            return
        marcadas = self._marcadas()
        if not marcadas:
            self.anotar("Nenhuma etapa marcada.")
            return

        alteram = [e.titulo for e in self._etapas
                   if e.chave in marcadas and e.altera]
        if alteram and not self._confirmar(alteram):
            return

        self.resultado.hide()
        self.resultado.clear()
        self.btn_rodar.setEnabled(False)
        self.rodape.setText("Executando...")
        self.rodar(roteiro.executar, self._pronto, marcadas, self._destino)

    def _confirmar(self, alteram: list[str]) -> bool:
        from PySide6.QtWidgets import QMessageBox

        quebra = chr(10)
        itens = quebra.join(f"  • {t}" for t in alteram)
        resposta = QMessageBox.question(
            self, "Confirmar roteiro",
            "Estas etapas alteram a máquina:" + quebra + quebra + itens
            + quebra + quebra
            + "As demais são somente leitura. Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return resposta == QMessageBox.Yes

    def _pronto(self, r: roteiro.Resultado) -> None:
        self.btn_rodar.setEnabled(True)

        for titulo, motivo in r.puladas:
            self.anotar(f"pulada: {titulo} — {motivo}")

        if r.mudancas:
            negrito = QFont(Fonte.FAMILIA, 9)
            negrito.setWeight(QFont.DemiBold)
            for m in r.mudancas:
                item = QTreeWidgetItem(
                    self.resultado,
                    [m.rotulo, m.antes, m.depois, m.variacao or "sem mudança"])
                item.setFont(2, negrito)
                item.setForeground(
                    3, QBrush(QColor(CORES_SITUACAO[m.situacao])))
            self.resultado.show()

        partes = [f"{len(r.concluidas)} etapa(s) concluída(s)"]
        if r.liberado:
            partes.append(f"{formatar_bytes(r.liberado)} liberados")
        if r.medida_disco and not r.medida_disco.erro:
            partes.append(
                f"disco: {r.medida_disco.leitura_aleatoria:.1f} MB/s "
                "em leitura aleatória")
        if r.caminho_pdf:
            partes.append(f"PDF em {r.caminho_pdf}")
        self.rodape.setText(" · ".join(partes))

        if r.varredura and r.varredura.sugestoes:
            graves = sum(1 for s in r.varredura.sugestoes
                         if s.gravidade == "alta")
            self.anotar(f"{len(r.varredura.sugestoes)} apontamento(s), "
                        f"{graves} de prioridade. Veja em Relatórios.")
