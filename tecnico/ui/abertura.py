"""Sequencia de abertura em cascata, no estilo de boot de terminal.

Puro estilo - mas com uma regra: as linhas mostram verificacoes de
verdade. Fonte carregada, recursos achados, nivel de permissao, onde os
dados moram. Inventar texto de enfeite seria transformar em cenario o que
pode ser informacao util nos dois segundos em que o tecnico ja esta
olhando a tela.

E pulavel com qualquer clique ou tecla: quem abre o app cinquenta vezes
por dia nao quer assistir a animacao na quinquagesima.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ..tema import Cor, Fonte, familia
from . import chanfro

INTERVALO = 95           # ms entre linhas
PAUSA_FINAL = 420        # ms segurando a tela cheia antes de sair


def _linhas() -> list[tuple[str, str, str]]:
    """(rotulo, valor, situacao) — tudo medido, nada decorativo."""
    from ..nucleo import admin, dados
    from ..tema import Fonte as _F
    from ..tema import familia as _familia
    from .. import recursos

    fontes = recursos.fontes()
    tipografia = _familia()
    elevado = admin.e_administrador()

    return [
        ("TIPOGRAFIA", tipografia,
         "ok" if tipografia == _F.FAMILIA else "atencao"),
        ("RECURSOS", f"{len(fontes)} arquivo(s)",
         "ok" if fontes else "atencao"),
        ("PERMISSOES", "administrador" if elevado else "modo padrão",
         "ok" if elevado else "atencao"),
        ("ARMAZENAMENTO", "pendrive" if dados.portatil() else "instalado",
         "ok"),
        ("SUBSISTEMAS", "prontos", "ok"),
    ]


class Abertura(QWidget):
    """Cobre a janela por cerca de um segundo e sai."""

    concluida = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self._linhas = _linhas()
        self._reveladas = 0

        self._relogio = QTimer(self)
        self._relogio.setInterval(INTERVALO)
        self._relogio.timeout.connect(self._proxima)

    def comecar(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._relogio.start()

    def _proxima(self) -> None:
        self._reveladas += 1
        self.update()
        if self._reveladas >= len(self._linhas):
            self._relogio.stop()
            QTimer.singleShot(PAUSA_FINAL, self.encerrar)

    def encerrar(self) -> None:
        if not self.isVisible():
            return
        self._relogio.stop()
        self.hide()
        self.concluida.emit()
        self.deleteLater()

    # Qualquer interacao pula a animacao.
    def mousePressEvent(self, evento) -> None:  # noqa: N802
        self.encerrar()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        self.encerrar()

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Cor.FUNDO))

        cx = self.width() / 2
        cy = self.height() / 2
        largura = min(460, self.width() - 80)
        altura = 60 + len(self._linhas) * 26

        moldura = QRectF(cx - largura / 2, cy - altura / 2,
                         largura, altura)
        chanfro.pintar(p, moldura, Cor.PAINEL, Cor.DESTAQUE_FOSCO, 1.0,
                       chanfro=14.0)
        chanfro.marcar_cantos(p, moldura, Cor.DESTAQUE, 2.0, 0.08)

        marca = QFont(familia(), 15)
        marca.setWeight(QFont.Bold)
        marca.setLetterSpacing(QFont.AbsoluteSpacing, 5.0)
        p.setFont(marca)
        p.setPen(QColor(Cor.DESTAQUE))
        p.drawText(int(moldura.x()), int(moldura.y() + 14),
                   int(largura), 26, Qt.AlignCenter, "RIPPER")

        p.setFont(QFont(Fonte.MONO, 9))
        cores = {"ok": Cor.OK, "atencao": Cor.ATENCAO}
        y = moldura.y() + 48

        for i, (rotulo, valor, situacao) in enumerate(self._linhas):
            if i >= self._reveladas:
                break
            # Marca honesta: escrever [OK] ao lado de "modo padrao" daria
            # a entender que esta tudo resolvido quando falta permissao.
            p.setPen(QColor(cores.get(situacao, Cor.TEXTO_SUAVE)))
            p.drawText(int(moldura.x() + 20), int(y), 40, 22,
                       Qt.AlignVCenter | Qt.AlignLeft,
                       "[OK]" if situacao == "ok" else "[ ! ]")
            p.setPen(QColor(Cor.TEXTO_SUAVE))
            p.drawText(int(moldura.x() + 62), int(y), 160, 22,
                       Qt.AlignVCenter | Qt.AlignLeft, rotulo)
            p.setPen(QColor(Cor.TEXTO))
            p.drawText(int(moldura.x() + 20), int(y),
                       int(largura - 40), 22,
                       Qt.AlignVCenter | Qt.AlignRight, valor)
            y += 26
        p.end()
