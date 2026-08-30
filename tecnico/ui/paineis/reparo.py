"""Painel de reparo do Windows.

Toda acao aqui altera o sistema. Nenhuma roda sem confirmacao, e a
confirmacao mostra o comando exato - o tecnico precisa poder dizer ao
cliente o que foi executado na maquina dele.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget

from ...nucleo import admin, reparo
from ...tema import Cor, Fonte
from ..widgets import Botao, Cartao, Legenda, Titulo
from .base import PainelBase


class PainelReparo(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Reparo do Windows",
            "Cada ação exige confirmação e mostra o comando antes de rodar. "
            "Crie um ponto de restauração antes das demoradas.",
            parent,
        )

        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setFont(QFont(Fonte.FAMILIA, 9))
        self._atualizar_aviso()
        self.conteudo.addWidget(self.aviso)

        area = QScrollArea()
        area.setWidgetResizable(True)
        interior = QWidget()
        coluna = QVBoxLayout(interior)
        coluna.setContentsMargins(0, 0, 8, 0)
        coluna.setSpacing(10)

        for acao in reparo.ACOES:
            coluna.addWidget(self._cartao(acao))
        coluna.addStretch(1)

        area.setWidget(interior)
        self.conteudo.addWidget(area)

    def _atualizar_aviso(self) -> None:
        if admin.e_administrador():
            self.aviso.setText("Executando como administrador.")
            self.aviso.setStyleSheet(f"color: {Cor.OK};")
        else:
            self.aviso.setText(
                "Sem privilégio de administrador — a maioria das ações abaixo "
                "vai falhar. Use o botão 'Reabrir como admin' na barra "
                "lateral."
            )
            self.aviso.setStyleSheet(f"color: {Cor.ATENCAO};")

    def _cartao(self, acao: reparo.Acao) -> Cartao:
        cartao = Cartao()
        cartao.corpo.addWidget(Titulo(acao.titulo))
        cartao.corpo.addWidget(Legenda(acao.descricao))

        etiquetas = []
        if acao.exige_admin:
            etiquetas.append("administrador")
        if acao.demorada:
            etiquetas.append("demorada")
        if acao.exige_reinicio:
            etiquetas.append("exige reiniciar")
        if etiquetas:
            marca = QLabel(" · ".join(etiquetas))
            marca.setFont(QFont(Fonte.MONO, 8))
            marca.setStyleSheet(f"color: {Cor.TEXTO_FRACO}; background: transparent;")
            cartao.corpo.addWidget(marca)

        botao = Botao("Executar", "perigo" if acao.exige_reinicio else "normal")
        botao.clicked.connect(lambda _=False, c=acao.chave: self.executar(c))
        cartao.corpo.addWidget(botao, 0, Qt.AlignLeft)
        return cartao

    def executar(self, chave: str) -> None:
        if self.ocupado:
            self.anotar("Aguarde a operação atual terminar.")
            return

        acao = reparo.por_chave(chave)
        partes = [acao.descricao, "", "Comando:", f"  {' '.join(acao.comando)}"]
        if acao.demorada:
            partes += ["", "Pode levar vários minutos. Não feche o aplicativo."]
        if acao.exige_reinicio:
            partes += ["", "A máquina precisará ser REINICIADA depois."]
        partes += ["", "Executar?"]

        if QMessageBox.question(
            self, acao.titulo, "\n".join(partes),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            self.anotar(f"'{acao.titulo}' cancelada pelo operador.")
            return

        self.rodar(reparo.executar, self._pronto, chave)

    def _pronto(self, saida: str) -> None:
        for linha in saida.splitlines():
            if linha.strip():
                self.anotar("  " + linha.strip())

        # O veredito vem depois da saida crua, nao no lugar dela: o texto
        # do comando continua util para quem sabe ler, e a conclusao serve
        # para quem precisa do proximo passo agora.
        situacao, explicacao = reparo.interpretar(saida)
        if explicacao:
            self.anotar("")
            self.notificar(explicacao, "ok" if situacao == "ok" else "erro")
