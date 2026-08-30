"""Painel de diagnostico: le a maquina e gera o relatorio."""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QFileDialog, QTreeWidget, QTreeWidgetItem

from ...nucleo import desempenho, memoria, pdf, sistema
from ...tema import Cor, Fonte
from ..widgets import Botao
from .base import PainelBase


class PainelDiagnostico(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Diagnóstico da máquina",
            "Leitura completa do equipamento. Nada é alterado.",
            parent,
        )
        self._grupos: list[sistema.Grupo] = []

        self.btn_ler = Botao("Executar diagnóstico", "primario")
        self.btn_ler.clicked.connect(self.executar)
        self.acoes.addWidget(self.btn_ler)

        self.btn_disco = Botao("Testar velocidade do disco")
        self.btn_disco.setToolTip(
            "Escreve e lê um arquivo de teste de 192 MB, sem usar o cache "
            "do Windows. O arquivo é apagado no fim.")
        self.btn_disco.clicked.connect(self.medir_disco)
        self.acoes.addWidget(self.btn_disco)

        self.btn_memoria = Botao("Testar memória")
        self.btn_memoria.setToolTip(
            "Escreve e confere padrões na RAM livre. Não substitui o "
            "MemTest86 pelo boot, mas pega defeito grosseiro em segundos.")
        self.btn_memoria.clicked.connect(self.medir_memoria)
        self.acoes.addWidget(self.btn_memoria)

        self.btn_salvar = Botao("Salvar relatório")
        self.btn_salvar.setEnabled(False)
        self.btn_salvar.clicked.connect(self.salvar)
        self.acoes.addWidget(self.btn_salvar)
        self.acoes.addStretch(1)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["Item", "Valor"])
        self.arvore.setColumnWidth(0, 250)
        self.arvore.setRootIsDecorated(True)
        self.conteudo.addWidget(self.arvore)

    def executar(self) -> None:
        if self.ocupado:
            return
        self.arvore.clear()
        self.btn_ler.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.rodar(sistema.coletar, self._pronto)

    def _pronto(self, grupos) -> None:
        self._grupos = grupos
        self.btn_ler.setEnabled(True)
        self.btn_salvar.setEnabled(bool(grupos))
        self._desenhar(grupos)

    def _desenhar(self, grupos) -> None:
        """Acrescenta grupos a arvore, sem limpar o que ja esta la.

        Separado de _pronto porque o teste de disco chega depois e precisa
        entrar na mesma arvore, e nao substituir o diagnostico.
        """
        negrito = QFont(Fonte.FAMILIA, 9)
        negrito.setWeight(QFont.DemiBold)

        for grupo in grupos:
            pai = QTreeWidgetItem(self.arvore, [grupo.titulo, ""])
            pai.setFont(0, negrito)
            pai.setForeground(0, QBrush(QColor(Cor.DESTAQUE)))

            for item in grupo.itens:
                filho = QTreeWidgetItem(pai, [item.rotulo, item.valor])
                # Cor so onde ha algo a dizer: pintar tudo tira o valor de
                # sinalizacao de quem realmente precisa de atencao.
                if item.alerta == "atencao":
                    filho.setForeground(1, QBrush(QColor(Cor.ATENCAO)))
                elif item.alerta == "erro":
                    filho.setForeground(1, QBrush(QColor(Cor.ERRO)))
            pai.setExpanded(True)

    def medir_disco(self) -> None:
        if self.ocupado:
            return
        self.btn_disco.setEnabled(False)
        self.anotar("Medindo o disco sem cache. Leva cerca de meio minuto...")
        self.rodar(desempenho.medir, self._disco_pronto)

    def _disco_pronto(self, m: desempenho.Medida) -> None:
        self.btn_disco.setEnabled(True)
        if m.erro:
            self.anotar(f"Teste de disco: {m.erro}")
            return

        grupo = sistema.Grupo(f"Desempenho do disco {m.unidade}")
        if m.tipo:
            grupo.itens.append(sistema.Item("Tipo", m.tipo))
        grupo.itens.append(sistema.Item(
            "Leitura sequencial", f"{m.leitura_sequencial:,.0f} MB/s".replace(",", ".")))
        grupo.itens.append(sistema.Item(
            "Escrita sequencial", f"{m.escrita_sequencial:,.0f} MB/s".replace(",", ".")))
        # A aleatoria vem com alerta porque e a que o usuario sente: abrir o
        # Windows sao milhares de leituras pequenas, nao uma copia grande.
        alerta = "" if m.leitura_aleatoria >= 5 else (
            "atencao" if m.leitura_aleatoria >= 1.5 else "erro")
        grupo.itens.append(sistema.Item(
            "Leitura aleatória (4 KB)",
            f"{m.leitura_aleatoria:.1f} MB/s — {m.iops:,} IOPS".replace(",", "."),
            alerta))
        grupo.itens.append(sistema.Item("Veredito", m.veredito, alerta))

        self._grupos.append(grupo)
        self._desenhar([grupo])
        self.btn_salvar.setEnabled(True)
        self.anotar(m.veredito)

    def medir_memoria(self) -> None:
        if self.ocupado:
            return
        self.btn_memoria.setEnabled(False)
        self.anotar("Testando a memória livre...")
        self.rodar(memoria.testar, self._memoria_pronta)

    def _memoria_pronta(self, r) -> None:
        from ...nucleo.win import formatar_bytes

        self.btn_memoria.setEnabled(True)
        if r.erro:
            self.anotar(r.erro)
            return

        grupo = sistema.Grupo("Teste de memória")
        grupo.itens.append(sistema.Item(
            "Volume verificado",
            f"{formatar_bytes(r.testado)} em {r.padroes} padrão(ões), "
            f"{r.segundos}s"))
        grupo.itens.append(sistema.Item(
            "Erros encontrados", str(r.erros), "erro" if r.erros else ""))
        for detalhe in r.detalhes[:5]:
            grupo.itens.append(sistema.Item("", detalhe, "erro"))
        grupo.itens.append(sistema.Item(
            "Conclusão", r.veredito, "erro" if r.erros else ""))

        self._grupos.append(grupo)
        self._desenhar([grupo])
        self.btn_salvar.setEnabled(True)
        self.anotar(r.veredito)

    def salvar(self) -> None:
        caminho, _filtro = QFileDialog.getSaveFileName(
            self, "Salvar relatório", pdf.nome_sugerido(), "PDF (*.pdf)")
        if not caminho:
            return
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        try:
            destino = pdf.salvar(pdf.montar_html(grupos=self._grupos), caminho)
        except OSError as erro:
            # Acontece quando o tecnico salva num pendrive que ja saiu.
            self.anotar(f"ERRO ao salvar: {erro}")
            return
        self.anotar(f"Relatório salvo em {destino}")
