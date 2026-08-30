"""Base comum dos paineis.

Concentra o que todo painel precisa: cabecalho, area de conteudo, barra de
andamento e registro. Sem isso cada tela reinventaria o mesmo cabecalho
com um espacamento ligeiramente diferente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ...nucleo import dados
from ...nucleo.tarefa import Tarefa, executar
from ...tema import Cor, Fonte, familia
from ..widgets import Botao


class PainelBase(QWidget):
    def __init__(self, titulo: str, subtitulo: str = "",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._tarefa: Tarefa | None = None
        self._nome_curto = titulo.split()[0].lower()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(28, 24, 28, 20)
        raiz.setSpacing(16)

        # -------- cabecalho --------
        cabecalho = QVBoxLayout()
        cabecalho.setSpacing(3)

        # Titulo em caixa alta com espacamento largo e uma barra amarela
        # a esquerda: e como o jogo rotula cada secao, e resolve de longe
        # em que tela o tecnico esta.
        faixa = QHBoxLayout()
        faixa.setSpacing(10)

        marca = QFrame()
        marca.setFixedWidth(4)
        marca.setStyleSheet(f"background: {Cor.DESTAQUE};")
        faixa.addWidget(marca)

        rotulo = QLabel(titulo.upper())
        f = QFont(familia(), 17)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        rotulo.setFont(f)
        rotulo.setStyleSheet(f"color: {Cor.TEXTO};")
        faixa.addWidget(rotulo)
        faixa.addStretch(1)
        cabecalho.addLayout(faixa)

        if subtitulo:
            sub = QLabel(subtitulo)
            sub.setFont(QFont(familia(), 10))
            sub.setStyleSheet(
                f"color: {Cor.TEXTO_SUAVE}; margin-left: 14px;")
            sub.setWordWrap(True)
            cabecalho.addWidget(sub)

        raiz.addLayout(cabecalho)

        # -------- barra de acoes (preenchida pelo painel filho) --------
        self.acoes = QHBoxLayout()
        self.acoes.setSpacing(8)
        raiz.addLayout(self.acoes)

        # -------- conteudo --------
        self.conteudo = QVBoxLayout()
        self.conteudo.setSpacing(12)
        raiz.addLayout(self.conteudo, 1)

        # -------- andamento --------
        # Andamento e cancelamento na mesma linha. SFC leva quinze
        # minutos: sem um jeito de parar, a unica saida era fechar o app
        # no meio da operacao - justamente o que nao se deve fazer.
        andamento = QHBoxLayout()
        andamento.setSpacing(10)

        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(6)
        self.barra.hide()
        andamento.addWidget(self.barra, 1)

        self.btn_cancelar = Botao("Cancelar", "perigo")
        self.btn_cancelar.setFixedHeight(26)
        self.btn_cancelar.hide()
        self.btn_cancelar.clicked.connect(self.cancelar)
        andamento.addWidget(self.btn_cancelar, 0)

        raiz.addLayout(andamento)

        self.registro = QPlainTextEdit()
        self.registro.setReadOnly(True)
        self.registro.setFixedHeight(84)
        self.registro.setFont(QFont(Fonte.MONO, 9))
        self.registro.setStyleSheet(
            f"background: {Cor.FUNDO}; color: {Cor.TEXTO_SUAVE};"
            f"border: 1px solid {Cor.BORDA_SUAVE}; border-radius: 6px;"
        )
        raiz.addWidget(self.registro)

    # ------------------------------------------------------------------
    def anotar(self, mensagem: str) -> None:
        self.registro.appendPlainText(mensagem)
        dados.anotar_no_registro(self._nome_curto, mensagem)
        if self._tarefa is not None:
            # A faixa mostra o passo atual da operacao em curso, que e
            # exatamente o que o painel acabou de escrever no registro.
            self._avisar_janela("operacao", mensagem[:52])
        self.registro.verticalScrollBar().setValue(
            self.registro.verticalScrollBar().maximum()
        )

    def rodar(self, funcao, ao_concluir, *args, **kwargs):
        """Executa em segundo plano e liga os sinais na barra e no registro.

        Um painel nunca chama funcao do nucleo diretamente: `sfc /scannow`
        na thread da interface congela a janela por minutos e o tecnico
        conclui que o app travou.
        """
        if self._tarefa is not None:
            self.anotar("Já existe uma operação em andamento.")
            return None

        self.barra.show()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.btn_cancelar.show()
        self.btn_cancelar.setEnabled(True)

        tarefa = executar(funcao, *args, **kwargs)
        self._tarefa = tarefa
        self._avisar_janela("operacao", self._nome_curto)

        tarefa.sinais.progresso.connect(self.anotar)
        tarefa.sinais.percentual.connect(self._andamento)
        tarefa.sinais.falhou.connect(self._falhou)

        def concluir(resultado):
            self._tarefa = None
            self.barra.hide()
            self.btn_cancelar.hide()
            self._avisar_janela("operacao", "")
            ao_concluir(resultado)

        tarefa.sinais.concluido.connect(concluir)
        # Devolvida para o painel ligar sinais proprios, como a medida
        # ao vivo que alimenta o velocimetro.
        return tarefa

    def _andamento(self, valor: int) -> None:
        if valor < 0:
            # Indeterminado: operacao sem progresso mensuravel. Fingir uma
            # porcentagem seria inventar informacao.
            self.barra.setRange(0, 0)
        else:
            self.barra.setRange(0, 100)
            self.barra.setValue(valor)

    def cancelar(self) -> None:
        """Pede o cancelamento. Quem para de fato e a funcao do nucleo.

        As funcoes longas consultam `cancelado()` entre as etapas, entao a
        parada acontece no proximo ponto seguro - nunca no meio de uma
        escrita em disco.
        """
        if self._tarefa is None:
            return
        self._tarefa.cancelar()
        self.btn_cancelar.setEnabled(False)
        self.anotar("Cancelamento pedido; encerrando na próxima etapa...")

    def _avisar_janela(self, metodo: str, *args) -> None:
        """Chama a janela principal, se ela existir.

        O painel nao guarda referencia para a janela: ele e criado antes
        dela terminar de montar, e subir a arvore na hora do uso evita
        uma dependencia circular entre os dois modulos.
        """
        alvo = self.window()
        funcao = getattr(alvo, metodo, None)
        if callable(funcao):
            funcao(*args)

    def notificar(self, texto: str, tipo: str = "info") -> None:
        self._avisar_janela("notificar", texto, tipo)
        self.anotar(texto)

    def _falhou(self, mensagem: str) -> None:
        self._tarefa = None
        self.barra.hide()
        self.btn_cancelar.hide()
        self._avisar_janela("operacao", "")
        self._avisar_janela("notificar",
                            mensagem.splitlines()[0][:120], "erro")
        self.anotar(f"ERRO: {mensagem.splitlines()[0]}")

    @property
    def ocupado(self) -> bool:
        return self._tarefa is not None
