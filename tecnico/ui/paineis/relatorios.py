"""Painel de relatorios e otimizacoes.

Roda tudo de uma vez e transforma o resultado em recomendacao. E a tela
que responde "o que ha de errado nesta maquina" sem o tecnico ter que
abrir as outras cinco.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...nucleo import entrega as nucleo_entrega
from ...nucleo import ficha as nucleo_ficha
from ...nucleo import historico, otimizacao, pdf, resumo
from ...tema import Cor, Fonte
from ..widgets import Botao, colunas_mono, Cartao, Legenda, Titulo
from .base import PainelBase

# Funcao e nao constante: dicionario no topo do modulo congela as
# cores da paleta ativa na IMPORTACAO, e a troca de tema depois
# nao chega ate ele. Foi assim que o texto do botao sumiu no tema
# claro - continuava branco.
def cores_gravidade() -> dict[str, str]:
    return {"alta": Cor.ERRO, "media": Cor.ATENCAO, "baixa": Cor.OK}
ROTULO_GRAVIDADE = {"alta": "PRIORIDADE", "media": "ATENÇÃO", "baixa": "OBSERVAÇÃO"}


class PainelRelatorios(PainelBase):
    ir_para = Signal(str)

    def __init__(self, parent=None):
        super().__init__(
            "Relatórios e otimizações",
            "Varre sistema, rede, temporários e inicialização de uma vez, "
            "e aponta o que merece ação. Somente leitura.",
            parent,
        )
        self._varredura: otimizacao.Varredura | None = None
        self._antes: historico.Instantaneo | None = None
        self._mudancas: list[historico.Mudanca] = []

        self.btn_varrer = Botao("Executar varredura completa", "primario")
        self.btn_varrer.clicked.connect(self.varrer)
        self.acoes.addWidget(self.btn_varrer)

        self.btn_estado = Botao("Marcar estado inicial")
        self.btn_estado.setToolTip(
            "Fotografa disco, lixo, inicialização e memória agora. "
            "No fim do atendimento, compare para provar o que mudou.")
        self.btn_estado.clicked.connect(self.marcar_estado)
        self.acoes.addWidget(self.btn_estado)

        self.btn_resumo = Botao("Resumo em imagem")
        self.btn_resumo.setToolTip(
            "PNG de uma página para mandar ao cliente. O PDF continua para "
            "imprimir e anexar.")
        self.btn_resumo.setEnabled(False)
        self.btn_resumo.clicked.connect(self.salvar_resumo)
        self.acoes.addWidget(self.btn_resumo)

        self.btn_salvar = Botao("Salvar relatório em PDF")
        self.btn_salvar.setEnabled(False)
        self.btn_salvar.clicked.connect(self.salvar)
        self.acoes.addWidget(self.btn_salvar)
        self.acoes.addStretch(1)

        self.resumo = QLabel("Nenhuma varredura executada.")
        self.resumo.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.conteudo.addWidget(self.resumo)

        self.tabela_antes = QTreeWidget()
        self.tabela_antes.setHeaderLabels(
            ["Indicador", "Antes", "Depois", "Variação"])
        self.tabela_antes.setColumnWidth(0, 260)
        colunas_mono(self.tabela_antes, 1, 2, 3)
        self.tabela_antes.setFixedHeight(160)
        self.tabela_antes.hide()
        self.conteudo.addWidget(self.tabela_antes)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self._interior = QWidget()
        self._coluna = QVBoxLayout(self._interior)
        self._coluna.setContentsMargins(0, 0, 8, 0)
        self._coluna.setSpacing(10)
        self._coluna.addStretch(1)
        self.area.setWidget(self._interior)

        self.abas = QTabWidget()
        self.abas.addTab(self.area, "Apontamentos")
        self.abas.addTab(self._aba_ficha(), "Ficha")
        self.conteudo.addWidget(self.abas)

    # ------------------------------------------------------------------
    def varrer(self) -> None:
        if self.ocupado:
            return
        self._limpar()
        self.btn_varrer.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.resumo.setText("Varrendo...")
        self.rodar(otimizacao.varrer_tudo, self._pronto)

    def _limpar(self) -> None:
        while self._coluna.count() > 1:
            item = self._coluna.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _pronto(self, v: otimizacao.Varredura) -> None:
        self._varredura = v
        self.btn_varrer.setEnabled(True)
        self.btn_salvar.setEnabled(True)
        self.btn_resumo.setEnabled(True)

        graves = sum(1 for s in v.sugestoes if s.gravidade == "alta")
        medias = sum(1 for s in v.sugestoes if s.gravidade == "media")
        self.resumo.setText(
            f"{len(v.sugestoes)} apontamento(s) — {graves} de prioridade, "
            f"{medias} de atenção."
        )

        for sugestao in v.sugestoes:
            self._coluna.insertWidget(self._coluna.count() - 1,
                                      self._cartao(sugestao))

    def _cartao(self, s: otimizacao.Sugestao) -> Cartao:
        cartao = Cartao()

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)

        marca = QLabel(ROTULO_GRAVIDADE[s.gravidade])
        marca.setFont(QFont(Fonte.MONO, 8))
        marca.setStyleSheet(
            f"color: {cores_gravidade()[s.gravidade]}; background: transparent;"
        )
        cabecalho.addWidget(marca)
        cabecalho.addWidget(Titulo(s.titulo), 1)
        cartao.corpo.addLayout(cabecalho)

        cartao.corpo.addWidget(Legenda(s.detalhe))

        if s.painel:
            botao = Botao("Abrir ferramenta")
            botao.clicked.connect(lambda _=False, p=s.painel: self.ir_para.emit(p))
            cartao.corpo.addWidget(botao, 0, Qt.AlignLeft)

        return cartao

    # ------------------------------------------------------------------
    # ANTES / DEPOIS
    # ------------------------------------------------------------------
    def marcar_estado(self) -> None:
        if self.ocupado:
            return
        self.btn_estado.setEnabled(False)
        alvo = "antes" if self._antes is None else "depois"
        self.anotar(f"Capturando estado ({alvo})...")
        # Reaproveita os achados da varredura quando ela ja rodou: medir o
        # lixo de novo custa segundos e daria o mesmo numero.
        achados = self._varredura.achados if self._varredura else None
        self.rodar(historico.capturar, self._estado_pronto, alvo, achados)

    def _estado_pronto(self, inst: historico.Instantaneo) -> None:
        self.btn_estado.setEnabled(True)
        historico.registrar(inst)

        if self._antes is None:
            self._antes = inst
            self.btn_estado.setText("Comparar com o inicial")
            anteriores = len(historico.carregar()) - 1
            extra = (f" Esta máquina já passou aqui {anteriores}x."
                     if anteriores > 0 else "")
            self.anotar(f"Estado inicial marcado em {inst.momento}.{extra}")
            return

        self._mudancas = historico.comparar(self._antes, inst)
        self._mostrar_comparacao()
        # Volta ao inicio: o proximo atendimento comeca do zero, e nao
        # comparado com o estado de outra maquina que ficou na memoria.
        self._antes = None
        self.btn_estado.setText("Marcar estado inicial")
        self.anotar("Comparação pronta. Ela entra no PDF.")

    def _mostrar_comparacao(self) -> None:
        cores = {"melhorou": Cor.OK, "piorou": Cor.ERRO, "neutro": Cor.TEXTO_SUAVE}
        self.tabela_antes.clear()
        for m in self._mudancas:
            item = QTreeWidgetItem(
                self.tabela_antes,
                [m.rotulo, m.antes, m.depois, m.variacao or "sem mudança"])
            item.setForeground(3, QBrush(QColor(cores[m.situacao])))
        self.tabela_antes.show()

    # ------------------------------------------------------------------
    def salvar(self) -> None:
        if self._varredura is None:
            return
        v = self._varredura

        caminho, _f = QFileDialog.getSaveFileName(
            self, "Salvar relatório", pdf.nome_sugerido(),
            "Documento PDF (*.pdf)")
        if not caminho:
            return

        try:
            html = pdf.montar_html(
                grupos=v.grupos,
                rede_testes=v.rede.testes if v.rede else None,
                sugestoes=v.sugestoes,
                achados=v.achados,
                inicializacao=v.inicializacao,
                comparacao=self._mudancas or None,
                ficha=self._ficha_atual(),
                checklist=nucleo_entrega.carregar(),
            )
            destino = pdf.salvar(html, caminho)
        except OSError as erro:
            # Acontece quando o tecnico salva num pendrive que ja saiu.
            self.anotar(f"ERRO ao salvar: {erro}")
            return
        self.anotar(f"Relatório salvo em {destino}")

    # ------------------------------------------------------------------
    # FICHA DE ORDEM DE SERVICO
    # ------------------------------------------------------------------
    def _aba_ficha(self) -> QWidget:
        aba = QWidget()
        coluna = QVBoxLayout(aba)
        coluna.setContentsMargins(4, 12, 4, 4)
        coluna.setSpacing(10)

        formulario = QFormLayout()
        formulario.setSpacing(8)

        self.f_cliente = QLineEdit()
        self.f_telefone = QLineEdit()
        self.f_equipamento = QLineEdit()
        self.f_tecnico = QLineEdit()
        formulario.addRow("Cliente", self.f_cliente)
        formulario.addRow("Telefone", self.f_telefone)
        formulario.addRow("Equipamento", self.f_equipamento)
        formulario.addRow("Técnico", self.f_tecnico)
        coluna.addLayout(formulario)

        for rotulo, atributo in (("Defeito relatado", "f_defeito"),
                                 ("Serviço executado", "f_executado"),
                                 ("Observações", "f_observacoes")):
            titulo = QLabel(rotulo.upper())
            titulo.setStyleSheet(f"color: {Cor.DESTAQUE}; font-size: 10px;")
            coluna.addWidget(titulo)
            campo = QPlainTextEdit()
            campo.setFixedHeight(58)
            setattr(self, atributo, campo)
            coluna.addWidget(campo)

        linha = QHBoxLayout()
        botao = Botao("Salvar ficha", "primario")
        botao.clicked.connect(self.salvar_ficha)
        linha.addWidget(botao)
        self.aviso_ficha = QLabel("")
        self.aviso_ficha.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        linha.addWidget(self.aviso_ficha, 1)
        coluna.addLayout(linha)

        # Carregada na montagem: quando a mesma maquina volta, o que o
        # cliente reclamou da outra vez ja esta na tela.
        self._preencher_ficha(nucleo_ficha.carregar())
        return aba

    def _preencher_ficha(self, f) -> None:
        self.f_cliente.setText(f.cliente)
        self.f_telefone.setText(f.telefone)
        self.f_equipamento.setText(f.equipamento)
        self.f_tecnico.setText(f.tecnico)
        self.f_defeito.setPlainText(f.defeito)
        self.f_executado.setPlainText(f.executado)
        self.f_observacoes.setPlainText(f.observacoes)
        if not f.vazia:
            self.aviso_ficha.setText(f"Ficha de {f.abertura} recuperada.")

    def _ficha_atual(self):
        return nucleo_ficha.Ficha(
            cliente=self.f_cliente.text().strip(),
            telefone=self.f_telefone.text().strip(),
            equipamento=self.f_equipamento.text().strip(),
            tecnico=self.f_tecnico.text().strip(),
            defeito=self.f_defeito.toPlainText().strip(),
            executado=self.f_executado.toPlainText().strip(),
            observacoes=self.f_observacoes.toPlainText().strip(),
        )

    def salvar_ficha(self) -> None:
        f = self._ficha_atual()
        if f.vazia:
            self.aviso_ficha.setText("Nada para salvar.")
            return
        try:
            nucleo_ficha.salvar(f)
        except OSError as erro:
            self.aviso_ficha.setText(f"Falhou: {erro}")
            return
        self.aviso_ficha.setText("Ficha salva. Ela entra no PDF.")
        self.anotar(f"Ficha de {f.cliente or 'cliente sem nome'} salva.")

    # ------------------------------------------------------------------
    def salvar_resumo(self) -> None:
        """PNG de uma pagina, para o cliente. Nao substitui o PDF."""
        if self._varredura is None:
            return
        caminho, _f = QFileDialog.getSaveFileName(
            self, "Salvar resumo em imagem", resumo.nome_sugerido(),
            "Imagem PNG (*.png)")
        if not caminho:
            return

        try:
            destino = resumo.gerar(
                caminho,
                ficha=self._ficha_atual(),
                mudancas=self._mudancas,
                sugestoes=self._varredura.sugestoes,
                checklist=nucleo_entrega.carregar(),
            )
        except OSError as erro:
            self.anotar(f"ERRO ao gerar o resumo: {erro}")
            return
        self.notificar(f"Resumo salvo em {destino}", "ok")
