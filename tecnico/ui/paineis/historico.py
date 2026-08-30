"""Painel de historico: o que ja passou por esta bancada.

Responde duas perguntas que so aparecem no reatendimento: esta maquina ja
esteve aqui, e o problema de hoje e o mesmo de antes? O nucleo grava por
numero de serie desde o inicio; faltava a tela.
"""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...nucleo import dados, historico
from ...nucleo.win import formatar_bytes
from ...tema import Cor, Fonte, familia
from ..widgets import Botao, colunas_mono
from .base import PainelBase

ROTULOS = {"antes": "estado inicial", "depois": "estado final"}


class PainelHistorico(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Histórico",
            "Atendimentos registrados nesta bancada, identificados pelo "
            "número de série da placa.",
            parent,
        )
        self._registros: list[historico.Instantaneo] = []

        self.btn_ler = Botao("Carregar histórico", "primario")
        self.btn_ler.clicked.connect(self.carregar)
        self.acoes.addWidget(self.btn_ler)

        self.btn_csv = Botao("Exportar CSV")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self.exportar)
        self.acoes.addWidget(self.btn_csv)
        self.btn_log = Botao("Abrir pasta")
        self.btn_log.setToolTip("Abre a pasta onde ficam histórico e registros.")
        self.btn_log.clicked.connect(self.abrir_pasta)
        self.acoes.addWidget(self.btn_log)
        self.acoes.addStretch(1)

        self.resumo = QLabel("Nenhum histórico carregado.")
        self.resumo.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.resumo.setWordWrap(True)
        self.conteudo.addWidget(self.resumo)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(
            ["Quando", "Registro", "Disco livre", "Lixo", "Inicialização"])
        self.arvore.setColumnWidth(0, 190)
        self.arvore.setColumnWidth(1, 150)
        colunas_mono(self.arvore, 2, 3, 4)
        self.abas = QTabWidget()
        self.abas.addTab(self.arvore, "Atendimentos")

        # O log ja era gravado e so abria por fora do app. Aqui ele fica ao
        # lado dos instantaneos, que e onde o tecnico procura quando reabre
        # a ficha de uma maquina.
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont(Fonte.MONO, 9))
        self.abas.addTab(self.log, "Registro do dia")

        self.conteudo.addWidget(self.abas)

    # ------------------------------------------------------------------
    def carregar(self) -> None:
        if self.ocupado:
            return
        self.arvore.clear()
        self.btn_ler.setEnabled(False)
        self.rodar(self._coletar, self._pronto)

    @staticmethod
    def _coletar(relatar=lambda _: None):
        relatar("Lendo o histórico local...")
        nome, serie, marca = historico.identidade()
        return (historico.carregar(), historico.maquinas(),
                (nome, serie, marca))

    def _pronto(self, resultado) -> None:
        self.btn_ler.setEnabled(True)
        desta, todas, identidade = resultado
        self._registros = desta
        nome, serie, marca = identidade

        self.resumo.setText(
            f"{nome} · {marca or 'modelo não informado'} · série {serie}  —  "
            f"{len(desta)} registro(s) desta máquina, "
            f"{len(todas)} máquina(s) no acervo  ·  {dados.descricao()}")
        self.btn_csv.setEnabled(bool(desta))
        self._carregar_log()

        if not desta:
            self.anotar("Nenhum atendimento gravado ainda para esta máquina.")
            return

        negrito = QFont(familia(), 10)
        negrito.setWeight(QFont.DemiBold)
        anterior = None

        for inst in desta:
            quando = inst.momento.replace("T", "  ")
            item = QTreeWidgetItem(self.arvore, [
                quando,
                ROTULOS.get(inst.rotulo, inst.rotulo or "avulso"),
                formatar_bytes(inst.disco_livre),
                formatar_bytes(inst.lixo_bytes),
                str(inst.itens_inicializacao),
            ])
            if inst.rotulo == "depois":
                item.setFont(1, negrito)
                item.setForeground(1, QBrush(QColor(Cor.DESTAQUE)))

            # Um par antes/depois vira uma linha filha com o resultado, que
            # e a leitura que interessa ao reabrir a ficha meses depois.
            if inst.rotulo == "depois" and anterior is not None:
                for m in historico.comparar(anterior, inst):
                    if m.situacao == "neutro":
                        continue
                    filho = QTreeWidgetItem(
                        item, ["", m.rotulo, m.antes, m.depois, m.variacao])
                    cor = Cor.OK if m.situacao == "melhorou" else Cor.ERRO
                    filho.setForeground(4, QBrush(QColor(cor)))
                item.setExpanded(True)
            anterior = inst if inst.rotulo == "antes" else None

    def exportar(self) -> None:
        if not self._registros:
            return
        caminho, _f = QFileDialog.getSaveFileName(
            self, "Exportar histórico", "historico_ripper.csv",
            "Planilha CSV (*.csv)")
        if not caminho:
            return

        import csv
        from dataclasses import asdict, fields

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
                # utf-8-sig: sem o BOM o Excel em portugues abre acentuacao
                # quebrada, e o tecnico conclui que o arquivo veio corrompido.
                escritor = csv.DictWriter(
                    f, fieldnames=[c.name for c in fields(historico.Instantaneo)],
                    delimiter=";")
                escritor.writeheader()
                for inst in self._registros:
                    escritor.writerow(asdict(inst))
        except OSError as erro:
            self.anotar(f"ERRO ao exportar: {erro}")
            return
        self.anotar(f"{len(self._registros)} registro(s) exportados para {caminho}")

    # ------------------------------------------------------------------
    def _carregar_log(self) -> None:
        arquivo = dados.registro_da_sessao()
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except OSError:
            texto = ""
        self.log.setPlainText(
            texto or f"Nenhum registro hoje ainda.{chr(10)}Arquivo: {arquivo}")
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum())

    def abrir_pasta(self) -> None:
        """Abre o Explorer na pasta de dados.

        Util no modo pendrive, quando o tecnico quer copiar o historico
        inteiro para outro lugar antes de devolver a maquina.
        """
        import subprocess

        from ...nucleo.win import SEM_JANELA

        try:
            subprocess.Popen(["explorer", str(dados.base())],
                             creationflags=SEM_JANELA)
        except OSError as erro:
            self.anotar(f"Não foi possível abrir a pasta: {erro}")
