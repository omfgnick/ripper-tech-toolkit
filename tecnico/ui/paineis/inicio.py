"""Tela inicial: grade das seis funcoes, com verificacao automatica."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...nucleo import limpeza as nucleo_limpeza
from ...nucleo import rede as nucleo_rede
from ...nucleo.tarefa import executar
from ...nucleo.win import formatar_bytes
from ...tema import Cor, Fonte, familia
from ..cartao_funcao import CartaoFuncao

# (chave do cartao, titulo, arquivo da ilustracao, painel de destino)
# (chave, titulo, icone Lucide, painel de destino, legenda)
#
# Um card por painel, sem duplicata e sem promessa errada: a versao
# anterior tinha dois cards abrindo a mesma tela de Limpeza, e um chamado
# "Restaurar Itens Padrao" que abria o painel de Reparo.
FUNCOES = [
    ("roteiro", "Roteiro", "route", "roteiro",
     "Executa o atendimento inteiro e termina no PDF"),
    ("diagnostico", "Diagnóstico", "activity", "diagnostico",
     "Lê o equipamento sem alterar nada"),
    ("limpeza", "Limpeza", "trash-2", "limpeza",
     "Mostra o que ocupa espaço antes de apagar"),
    ("rede", "Rede", "wifi", "rede",
     "Testa a conexão em camadas e mede a velocidade"),
    ("programas", "Programas", "package", "programas",
     "Instalados, inicialização e o que se esconde"),
    ("reparo", "Reparo", "wrench", "reparo",
     "SFC, DISM e CHKDSK, com ponto de restauração antes"),
    ("manutencao", "Manutenção", "hard-drive-download", "manutencao",
     "Instala em lote, salva drivers e copia o perfil"),
    ("relatorios", "Relatórios", "chart-column", "relatorios",
     "Junta tudo e aponta o que merece ação"),
    ("entrega", "Entrega", "clipboard-check", "entrega",
     "Confere item a item antes de devolver"),
    ("historico", "Histórico", "file-clock", "historico",
     "O que já passou por esta bancada"),
]

POR_LINHA = 5


class PainelInicio(QWidget):
    ir_para = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(30, 26, 30, 22)
        raiz.setSpacing(6)

        # Mesmo cabecalho dos demais paineis: faixa amarela, caixa alta
        # e espacamento largo. Antes esta tela tinha um titulo proprio e
        # destoava das outras oito.
        faixa = QHBoxLayout()
        faixa.setSpacing(10)
        marca = QFrame()
        marca.setFixedWidth(4)
        marca.setStyleSheet(f"background: {Cor.DESTAQUE};")
        faixa.addWidget(marca)

        titulo = QLabel("PAINEL DE ATENDIMENTO")
        f = QFont(familia(), 17)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        titulo.setFont(f)
        faixa.addWidget(titulo)
        faixa.addStretch(1)
        raiz.addLayout(faixa)

        self.subtitulo = QLabel("Verificando a máquina...")
        self.subtitulo.setFont(QFont(familia(), 10))
        self.subtitulo.setStyleSheet(
            f"color: {Cor.TEXTO_SUAVE}; margin-left: 14px;")
        raiz.addWidget(self.subtitulo)

        raiz.addStretch(1)

        grade = QGridLayout()
        grade.setSpacing(10)
        grade.setContentsMargins(0, 8, 0, 8)

        self.cartoes: dict[str, CartaoFuncao] = {}
        self._destinos: dict[str, str] = {}

        for i, (chave, rotulo, arquivo, destino, legenda) in enumerate(
                FUNCOES):
            cartao = CartaoFuncao(chave, rotulo, arquivo, legenda)
            cartao.clicado.connect(self._abrir)
            grade.addWidget(cartao, i // POR_LINHA, i % POR_LINHA)
            self.cartoes[chave] = cartao
            self._destinos[chave] = destino

        # Colunas com o mesmo peso: sem isto uma coluna com rotulo mais
        # longo rouba largura das vizinhas e a grade sai torta.
        for coluna in range(POR_LINHA):
            grade.setColumnStretch(coluna, 1)

        raiz.addLayout(grade)
        raiz.addStretch(1)

        rodape = QLabel("Clique em um item para abrir a ferramenta.")
        rodape.setFont(QFont(Fonte.FAMILIA, 8))
        rodape.setStyleSheet(f"color: {Cor.TEXTO_FRACO};")
        rodape.setAlignment(Qt.AlignCenter)
        raiz.addWidget(rodape)

    # ------------------------------------------------------------------
    def _abrir(self, chave: str) -> None:
        destino = self._destinos.get(chave)
        if destino:
            self.ir_para.emit(destino)

    def verificar(self) -> None:
        """Duas verificacoes rapidas, so de leitura.

        Abrir o app nao pode alterar nada na maquina do cliente antes de
        alguem pedir.
        """
        for chave in ("rede", "limpeza"):
            self.cartoes[chave].definir_estado(
                "verificando...", Cor.DESTAQUE, Cor.DESTAQUE)

        t_rede = executar(nucleo_rede.diagnosticar)
        t_rede.sinais.concluido.connect(self._rede_pronta)
        t_rede.sinais.falhou.connect(
            lambda _e: self.cartoes["rede"].definir_estado(
                "falhou", Cor.ERRO, Cor.ERRO))

        t_limpeza = executar(nucleo_limpeza.varrer)
        t_limpeza.sinais.concluido.connect(self._limpeza_pronta)
        t_limpeza.sinais.falhou.connect(
            lambda _e: self.cartoes["limpeza"].definir_estado(
                "falhou", Cor.ERRO, Cor.ERRO))

    def _rede_pronta(self, diagnostico) -> None:
        mapa = {
            "ok": ("Normal", Cor.OK, Cor.OK),
            "atencao": ("Instável", Cor.ATENCAO, Cor.ATENCAO),
            "erro": ("Com falha", Cor.ERRO, Cor.ERRO),
        }
        self.cartoes["rede"].definir_estado(*mapa[diagnostico.situacao_geral])
        self._concluir()

    def _limpeza_pronta(self, achados) -> None:
        total = sum(a.bytes_total for a in achados)

        # A grade antiga tinha dois cards para a mesma tela - um de espaco
        # e um de rastros. Agora e um so, e o total ja inclui os rastros.
        #
        # Abaixo de 100 MB nao vale chamar o tecnico para limpar: o rotulo
        # diz "sem excesso" em vez de exibir um numero irrelevante.
        if total < 100 * 1024 * 1024:
            self.cartoes["limpeza"].definir_estado(
                "Sem excesso", Cor.OK, Cor.OK)
        else:
            self.cartoes["limpeza"].definir_estado(
                formatar_bytes(total), Cor.ATENCAO, Cor.ATENCAO)

        self._concluir()

    def _concluir(self) -> None:
        self.subtitulo.setText("Verificação concluída. Clique em um item para agir.")
