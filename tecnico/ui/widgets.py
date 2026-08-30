"""Widgets reaproveitados em toda a interface."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QStyledItemDelegate,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..tema import Cor, Fonte, familia
from . import chanfro


class Pilula(QWidget):
    """Rotulo de chamada da cena: titulo e, opcionalmente, um estado.

    Corresponde aos rotulos da referencia: "Verificacao de Rede | Normal".
    O separador so aparece quando ha estado - sem isso a barra sobra
    pendurada em rotulos que ainda nao rodaram.
    """

    clicada = Signal()

    def __init__(self, titulo: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._ativa = False

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_StyledBackground, True)

        linha = QHBoxLayout(self)
        linha.setContentsMargins(14, 7, 14, 7)
        linha.setSpacing(8)

        self.rotulo = QLabel(titulo)
        self.rotulo.setFont(QFont(Fonte.FAMILIA, 9))
        linha.addWidget(self.rotulo)

        self.separador = QLabel("|")
        self.separador.setStyleSheet(f"color: {Cor.BORDA};")
        self.separador.hide()
        linha.addWidget(self.separador)

        self.estado = QLabel("")
        self.estado.setFont(QFont(Fonte.FAMILIA, 9))
        self.estado.hide()
        linha.addWidget(self.estado)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._aplicar_estilo()

    def _aplicar_estilo(self) -> None:
        borda = Cor.DESTAQUE if self._ativa else Cor.BORDA
        fundo = Cor.PAINEL_ALTO if self._ativa else Cor.PAINEL
        texto = Cor.TEXTO if self._ativa else Cor.TEXTO_SUAVE
        self.setStyleSheet(
            f"""
            Pilula {{
                background: {fundo};
                border: 1px solid {borda};
                border-radius: 15px;
            }}
            """
        )
        self.rotulo.setStyleSheet(f"color: {texto}; background: transparent;")

    def definir_estado(self, texto: str, cor: str = Cor.TEXTO_SUAVE) -> None:
        """Mostra o estado ao lado do titulo. Texto vazio esconde."""
        if not texto:
            self.separador.hide()
            self.estado.hide()
        else:
            self.estado.setText(texto)
            self.estado.setStyleSheet(f"color: {cor}; background: transparent;")
            self.separador.show()
            self.estado.show()
        self.adjustSize()

    def definir_ativa(self, ativa: bool) -> None:
        self._ativa = ativa
        self._aplicar_estilo()

    def enterEvent(self, evento) -> None:  # noqa: N802
        if not self._ativa:
            self.setStyleSheet(
                self.styleSheet().replace(Cor.BORDA, Cor.NEUTRO)
            )

    def leaveEvent(self, evento) -> None:  # noqa: N802
        self._aplicar_estilo()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        self.clicada.emit()


class Cartao(QFrame):
    """Superficie de conteudo, chanfrada.

    Pinta a si mesma em vez de usar QSS: `border-radius` so arredonda, e
    canto arredondado e exatamente o que esta linguagem visual nao tem.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(18, 16, 18, 16)
        self.corpo.setSpacing(10)

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        chanfro.pintar(pintor, QRectF(self.rect()), Cor.PAINEL,
                       Cor.BORDA, 1.0)


class Botao(QPushButton):
    """Botao do app. `tipo` decide o peso visual, nao o autor da tela.

    Rotulo em caixa alta com espacamento largo: e como o jogo escreve
    todo comando, e a Rajdhani foi desenhada para isso - em caixa baixa
    ela perde a cara mecanica.
    """

    ESTILOS = {
        # tipo: (fundo, borda, texto, fundo ao passar o mouse)
        "primario": (Cor.DESTAQUE, Cor.DESTAQUE, Cor.SOBRE_DESTAQUE,
                     Cor.DESTAQUE_FORTE),
        "perigo": (None, Cor.ERRO, Cor.ERRO, "#2a0410"),
        "normal": (None, Cor.BORDA, Cor.TEXTO, Cor.PAINEL_ALTO),
    }

    def __init__(self, texto: str, tipo: str = "normal",
                 parent: QWidget | None = None):
        super().__init__(texto.upper(), parent)
        self.tipo = tipo if tipo in self.ESTILOS else "normal"
        self._sob_o_mouse = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(34)
        self.setFlat(True)

        fonte = QFont(familia(), 10)
        fonte.setWeight(QFont.DemiBold)
        fonte.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
        self.setFont(fonte)

    def setText(self, texto: str) -> None:  # noqa: N802
        super().setText(texto.upper())

    def enterEvent(self, evento) -> None:  # noqa: N802
        self._sob_o_mouse = True
        self.update()

    def leaveEvent(self, evento) -> None:  # noqa: N802
        self._sob_o_mouse = False
        self.update()

    def sizeHint(self):  # noqa: N802
        base = super().sizeHint()
        base.setWidth(base.width() + 22)
        return base

    def paintEvent(self, evento) -> None:  # noqa: N802
        fundo, borda, texto, realce = self.ESTILOS[self.tipo]
        if not self.isEnabled():
            fundo, borda, texto = None, Cor.BORDA_SUAVE, Cor.TEXTO_FRACO
        elif self._sob_o_mouse:
            fundo = realce if self.tipo == "primario" else realce

        pintor = QPainter(self)

        # Halo por baixo do botao aceso. O jogo usa bloom pesado nos
        # elementos ativos; sem isso o amarelo fica chapado, como tinta.
        if self.isEnabled() and self.tipo == "primario":
            halo = QColor(Cor.DESTAQUE)
            for recuo, alfa in ((0, 30), (1, 46)):
                halo.setAlpha(alfa)
                chanfro.pintar(pintor,
                               QRectF(self.rect()).adjusted(recuo, recuo,
                                                            -recuo, -recuo),
                               None, halo.name(QColor.HexArgb), 3.0,
                               chanfro=8.0)

        chanfro.pintar(pintor, QRectF(self.rect()), fundo, borda, 1.0,
                       chanfro=8.0)
        pintor.setPen(QColor(texto))
        pintor.setFont(self.font())
        pintor.drawText(self.rect(), Qt.AlignCenter, self.text())


class Titulo(QLabel):
    def __init__(self, texto: str, parent: QWidget | None = None):
        super().__init__(texto, parent)
        f = QFont(familia(), 14)
        f.setWeight(QFont.DemiBold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        self.setFont(f)
        self.setStyleSheet(f"color: {Cor.TEXTO}; background: transparent;")


class Legenda(QLabel):
    def __init__(self, texto: str, parent: QWidget | None = None):
        super().__init__(texto, parent)
        self.setFont(QFont(familia(), 10))
        self.setStyleSheet(f"color: {Cor.TEXTO_SUAVE}; background: transparent;")
        self.setWordWrap(True)


class _ColunaMono(QStyledItemDelegate):
    """Desenha certas colunas em fonte monoespacada.

    Delegate e nao setFont item a item: as arvores sao preenchidas em
    varios lugares e alguns itens nascem dentro de tarefas em segundo
    plano. Aqui a regra fica na tabela, uma vez so, e vale para tudo que
    entrar depois.
    """

    def __init__(self, colunas: set[int], parent=None):
        super().__init__(parent)
        self.colunas = colunas

    def initStyleOption(self, opcao, indice) -> None:  # noqa: N802
        super().initStyleOption(opcao, indice)
        if indice.column() in self.colunas:
            opcao.font = QFont(Fonte.MONO, 9)


def colunas_mono(arvore, *indices: int) -> None:
    """Alinha numeros em coluna. Rajdhani tem largura variavel: '1' e
    muito mais estreito que '8', e uma coluna de tamanhos fica serrilhada.
    Leitura de dados monoespacada e caracteristica citada do proprio jogo.
    """
    delegate = _ColunaMono(set(indices), arvore)
    arvore.setItemDelegate(delegate)
    # A referencia precisa sobreviver: o Qt nao segura o delegate e ele
    # seria coletado, voltando ao desenho padrao sem erro nenhum.
    arvore._delegate_mono = delegate
    for coluna in indices:
        arvore.headerItem().setTextAlignment(coluna, Qt.AlignRight | Qt.AlignVCenter)
