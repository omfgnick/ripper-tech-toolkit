"""Painel de entrega: conferir, testar e empacotar antes de devolver."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...nucleo import entrega
from ...tema import Cor
from ..testes import TesteDeTeclado, TesteDeTela
from ..widgets import Botao
from .base import PainelBase

# Funcao e nao constante: dicionario no topo do modulo congela as
# cores da paleta ativa na IMPORTACAO, e a troca de tema depois
# nao chega ate ele. Foi assim que o texto do botao sumiu no tema
# claro - continuava branco.
def cores() -> dict[str, str]:
    return {"ok": Cor.OK, "atencao": Cor.ATENCAO, "erro": Cor.ERRO}


class PainelEntrega(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Entrega",
            "Confere o que costuma ser verificado de cabeça, testa tela e "
            "teclado, e junta tudo numa pasta para o cliente.",
            parent,
        )
        # Recupera o checklist da mesma maquina, como a ficha faz.
        self._itens = entrega.carregar()
        self._janelas = []      # mantem referencia das telas cheias abertas

        self.btn_verificar = Botao("Verificar", "primario")
        self.btn_verificar.setToolTip(
            "Preenche os itens que dá para conferir por software.")
        self.btn_verificar.clicked.connect(self.verificar)
        self.acoes.addWidget(self.btn_verificar)

        self.btn_tela = Botao("Testar tela")
        self.btn_tela.clicked.connect(self.testar_tela)
        self.acoes.addWidget(self.btn_tela)

        self.btn_teclado = Botao("Testar teclado")
        self.btn_teclado.clicked.connect(self.testar_teclado)
        self.acoes.addWidget(self.btn_teclado)

        self.btn_exportar = Botao("Exportar pasta do cliente")
        self.btn_exportar.clicked.connect(self.exportar)
        self.acoes.addWidget(self.btn_exportar)
        self.acoes.addStretch(1)

        self.resumo = QLabel("Nada verificado ainda.")
        self.resumo.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.resumo.setWordWrap(True)
        self.conteudo.addWidget(self.resumo)

        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(["Item", "Verificação"])
        self.lista.setColumnWidth(0, 340)
        self.lista.itemChanged.connect(self._marcacao_mudou)
        self.conteudo.addWidget(self.lista)

        self._desenhar()

    # ------------------------------------------------------------------
    def _desenhar(self) -> None:
        self.lista.blockSignals(True)
        self.lista.clear()
        for item in self._itens:
            linha = QTreeWidgetItem(
                self.lista,
                [item.titulo,
                 item.resultado or ("aguardando verificação"
                                    if item.automatico else "confira à mão")])
            linha.setFlags(linha.flags() | Qt.ItemIsUserCheckable)
            linha.setCheckState(0, Qt.Checked if item.marcado else Qt.Unchecked)
            linha.setData(0, Qt.UserRole, item.chave)
            if item.situacao in cores():
                linha.setForeground(1, QBrush(QColor(cores()[item.situacao])))
            elif not item.automatico:
                linha.setForeground(1, QBrush(QColor(Cor.TEXTO_FRACO)))
        self.lista.blockSignals(False)
        self._atualizar_resumo()

    def _marcacao_mudou(self, linha, _coluna) -> None:
        chave = linha.data(0, Qt.UserRole)
        for item in self._itens:
            if item.chave == chave:
                item.marcado = linha.checkState(0) == Qt.Checked
        entrega.salvar(self._itens)
        self._atualizar_resumo()

    def _atualizar_resumo(self) -> None:
        feitos = sum(1 for i in self._itens if i.marcado)
        pendentes = [i.titulo for i in self._itens if not i.marcado]
        texto = f"{feitos} de {len(self._itens)} itens conferidos."
        if pendentes:
            texto += "  Falta: " + ", ".join(pendentes[:3])
            if len(pendentes) > 3:
                texto += f" e mais {len(pendentes) - 3}."
        self.resumo.setText(texto)
        self.resumo.setStyleSheet(
            f"color: {Cor.OK if not pendentes else Cor.TEXTO_SUAVE};")

    # ------------------------------------------------------------------
    def verificar(self) -> None:
        if self.ocupado:
            return
        self.btn_verificar.setEnabled(False)
        self.rodar(entrega.verificar, self._verificado, self._itens)

    def _verificado(self, itens) -> None:
        self.btn_verificar.setEnabled(True)
        self._itens = itens
        entrega.salvar(self._itens)
        self._desenhar()
        falhas = [i for i in itens if i.situacao == "erro"]
        if falhas:
            self.notificar(
                f"{len(falhas)} verificação(ões) falharam: "
                + ", ".join(i.titulo for i in falhas[:2]), "erro")

    def _abrir(self, janela) -> None:
        # A referencia precisa viver enquanto a janela existe; sem ela o
        # Python coleta o widget e a tela cheia fecha sozinha na hora.
        self._janelas.append(janela)
        janela.destroyed.connect(
            lambda: self._janelas.remove(janela)
            if janela in self._janelas else None)
        janela.showFullScreen()

    def testar_tela(self) -> None:
        self.anotar("Teste de tela aberto. Clique para trocar de cor, Esc sai.")
        self._abrir(TesteDeTela())

    def testar_teclado(self) -> None:
        self.anotar("Teste de teclado aberto. Esc duas vezes para sair.")
        self._abrir(TesteDeTeclado())

    def exportar(self) -> None:
        if self.ocupado:
            return
        destino = QFileDialog.getExistingDirectory(
            self, "Onde criar a pasta do cliente", "")
        if not destino:
            return
        self.btn_exportar.setEnabled(False)
        self.rodar(entrega.exportar_pasta, self._exportado, destino)

    def _exportado(self, r) -> None:
        self.btn_exportar.setEnabled(True)
        for falha in r.falharam:
            self.anotar(f"falhou: {falha}")
        if r.copiados:
            self.notificar(
                f"{len(r.copiados)} item(ns) em {r.destino}", "ok")
        else:
            self.anotar(f"Nada foi copiado para {r.destino}.")
