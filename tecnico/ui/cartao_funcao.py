"""Cartao de funcao da tela inicial: ilustracao, titulo e estado."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..tema import Cor, Fonte, familia
from . import chanfro, icones


class Ilustracao(QLabel):
    """Icone de linha dentro de uma moldura chanfrada.

    A versao anterior punha um halo eliptico embaixo do render 3D, imitando
    sombra no chao. Icone de linha nao projeta sombra - aqui o estado se
    mostra recolorindo o proprio traco e a moldura, que e como o jogo
    sinaliza: a forma nao muda, a cor muda.
    """

    def __init__(self, arquivo: str, lado: int = 104, parent=None):
        super().__init__(parent)
        self._cor_halo: str | None = None
        self._nome = arquivo
        self._lado = lado
        self.setFixedSize(lado + 28, lado + 28)
        self.setAlignment(Qt.AlignCenter)

    def definir_halo(self, cor: str | None) -> None:
        self._cor_halo = cor
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        cor = self._cor_halo or Cor.DESTAQUE
        area = QRectF(self.rect()).adjusted(6, 6, -6, -6)

        # Moldura fosca sempre; ela ganha a cor do estado so quando ha um.
        chanfro.pintar(p, area, None,
                       cor if self._cor_halo else Cor.DESTAQUE_FOSCO, 1.0,
                       chanfro=12.0)
        if self._cor_halo:
            chanfro.marcar_cantos(p, area, cor, 2.0, 0.18)

        icones.desenhar(self._nome, p, area.adjusted(16, 16, -16, -16), cor,
                        espessura=2.4)
        p.end()


class CartaoFuncao(QWidget):
    """Celula clicavel da grade inicial."""

    clicado = Signal(str)

    def __init__(self, chave: str, titulo: str, arquivo: str, parent=None):
        super().__init__(parent)
        self.chave = chave
        self._sob_mouse = False

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(196)

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(10, 14, 10, 14)
        coluna.setSpacing(4)
        coluna.setAlignment(Qt.AlignHCenter)

        self.ilustracao = Ilustracao(arquivo)
        coluna.addWidget(self.ilustracao, 0, Qt.AlignHCenter)

        self.rotulo = QLabel(titulo)
        self.rotulo.setAlignment(Qt.AlignCenter)
        self.rotulo.setWordWrap(True)
        f = QFont(Fonte.FAMILIA, 9)
        f.setWeight(QFont.DemiBold)
        self.rotulo.setFont(f)
        self.rotulo.setStyleSheet(f"color: {Cor.TEXTO}; background: transparent;")
        coluna.addWidget(self.rotulo)

        self.estado = QLabel("—")
        self.estado.setAlignment(Qt.AlignCenter)
        self.estado.setFont(QFont(Fonte.FAMILIA, 9))
        self.estado.setStyleSheet(
            f"color: {Cor.TEXTO_FRACO}; background: transparent;"
        )
        coluna.addWidget(self.estado)

        self._aplicar_estilo()

    def _aplicar_estilo(self) -> None:
        # Sem QSS de fundo: a celula se pinta chanfrada no paintEvent.
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        if self._sob_mouse:
            pintor = QPainter(self)
            chanfro.pintar(pintor, QRectF(self.rect()), Cor.PAINEL,
                           Cor.DESTAQUE_FOSCO, 1.0, chanfro=14.0)

    def definir_estado(self, texto: str, cor: str, halo: str | None) -> None:
        self.estado.setText(texto)
        self.estado.setStyleSheet(f"color: {cor}; background: transparent;")
        self.ilustracao.definir_halo(halo)

    def enterEvent(self, evento) -> None:  # noqa: N802
        self._sob_mouse = True
        self._aplicar_estilo()

    def leaveEvent(self, evento) -> None:  # noqa: N802
        self._sob_mouse = False
        self._aplicar_estilo()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        self.clicado.emit(self.chave)
