"""Faixa de status e notificacoes de canto.

O HUD do Cyberpunk 2077 e contextual: ele muda conforme a tarefa - dirigir,
combater, explorar mostram informacoes diferentes. A ideia aqui e a mesma,
aplicada ao atendimento: uma faixa fina que diz sempre em que maquina se
esta mexendo e o que esta rodando agora.

E resolve um problema pratico, nao so estetico. O tecnico troca de painel
o tempo todo; sem a faixa, saber se a varredura ainda esta rodando exige
voltar ate a tela que a disparou.

NOTIFICACAO EM VEZ DE SO O REGISTRO
    Operacao longa termina enquanto o tecnico esta em outra tela, e o
    aviso morre na caixa de registro daquele painel. O toast aparece por
    cima de qualquer tela e some sozinho.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QWidget

from ..tema import Cor, Fonte, familia
from . import chanfro

DURACAO_TOAST = 4200          # ms na tela
ALTURA_FAIXA = 26


class FaixaStatus(QWidget):
    """Linha fina com identidade da maquina e operacao em curso."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(ALTURA_FAIXA)
        self._maquina = ""
        self._operacao = ""
        self._modo = ""

        fonte = QFont(Fonte.MONO, 8)
        fonte.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        self.setFont(fonte)

        # Pisca so enquanto ha operacao: parado, a faixa fica imovel para
        # nao competir com a leitura da tela.
        self._fase = 0
        self._pulso = QTimer(self)
        self._pulso.setInterval(560)
        self._pulso.timeout.connect(self._piscar)

    def definir_maquina(self, texto: str) -> None:
        self._maquina = texto.upper()
        self.update()

    def definir_modo(self, texto: str) -> None:
        self._modo = texto.upper()
        self.update()

    def definir_operacao(self, texto: str) -> None:
        self._operacao = texto.upper()
        if texto and not self._pulso.isActive():
            self._pulso.start()
        elif not texto:
            self._pulso.stop()
            self._fase = 0
        self.update()

    def _piscar(self) -> None:
        self._fase = (self._fase + 1) % 2
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Cor.FUNDO_ALTO))
        p.setPen(QColor(Cor.DESTAQUE_FOSCO))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        p.setFont(self.font())
        margem = 14

        # Tres faixas desiguais. Com um terco cada, a identidade da
        # maquina - que e a mais longa - era cortada pela operacao no
        # meio. A esquerda recebe o dobro do que a direita precisa.
        largura = self.width() - margem * 2
        esq = largura * 0.42
        centro = largura * 0.36
        dir_ = largura - esq - centro

        p.setPen(QColor(Cor.TEXTO_SUAVE))
        p.drawText(QRectF(margem, 0, esq, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._maquina)

        if self._operacao:
            marca = "▶" if self._fase else "▷"
            p.setPen(QColor(Cor.DESTAQUE))
            texto = f"{marca} {self._operacao}"
        else:
            p.setPen(QColor(Cor.TEXTO_FRACO))
            texto = "PRONTO"
        p.drawText(QRectF(margem + esq, 0, centro, self.height()),
                   Qt.AlignVCenter | Qt.AlignCenter, texto)

        p.setPen(QColor(Cor.TEXTO_FRACO))
        p.drawText(QRectF(margem + esq + centro, 0, dir_, self.height()),
                   Qt.AlignVCenter | Qt.AlignRight, self._modo)
        p.end()


class Aviso(QLabel):
    """Toast de canto. Some sozinho e nao rouba o foco."""

    @staticmethod
    def cores() -> dict[str, str]:
        # Lido na hora: atributo de classe congela a paleta da importacao.
        return {"ok": Cor.OK, "atencao": Cor.ATENCAO, "erro": Cor.ERRO,
                "info": Cor.DESTAQUE}

    def __init__(self, texto: str, tipo: str, parent: QWidget):
        super().__init__(texto, parent)
        self.tipo = tipo if tipo in self.cores() else "info"
        self.setWordWrap(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMargin(0)
        self.setContentsMargins(16, 10, 16, 10)
        self.setFixedWidth(340)

        fonte = QFont(familia(), 11)
        fonte.setWeight(QFont.DemiBold)
        self.setFont(fonte)
        self.setStyleSheet(
            f"color: {self.cores()[self.tipo]}; background: transparent;")
        self.adjustSize()

    def paintEvent(self, evento) -> None:  # noqa: N802
        p = QPainter(self)
        cor = self.cores()[self.tipo]
        chanfro.pintar(p, QRectF(self.rect()), Cor.PAINEL, cor, 1.0,
                       chanfro=10.0)
        # Barra cheia na esquerda: repete o cabecalho dos paineis e deixa
        # a gravidade legivel antes mesmo de ler o texto.
        p.fillRect(1, 1, 3, self.height() - 2, QColor(cor))
        p.end()
        super().paintEvent(evento)


class Avisos:
    """Empilha os toasts no canto inferior direito da janela."""

    def __init__(self, janela: QWidget):
        self.janela = janela
        self._ativos: list[Aviso] = []

    def mostrar(self, texto: str, tipo: str = "info") -> None:
        aviso = Aviso(texto, tipo, self.janela)
        self._ativos.append(aviso)
        aviso.show()
        aviso.raise_()
        self._reposicionar()

        # Temporizador FILHO do proprio aviso, e nao singleShot solto: ao
        # fechar a janela com um toast na tela, o singleShot disparava
        # depois e tentava destruir um widget que o Qt ja tinha destruido,
        # levantando "Internal C++ object already deleted". Sendo filho,
        # ele morre junto e nao chega a disparar.
        relogio = QTimer(aviso)
        relogio.setSingleShot(True)
        relogio.setInterval(DURACAO_TOAST)
        relogio.timeout.connect(lambda: self._remover(aviso))
        relogio.start()

    def _remover(self, aviso: Aviso) -> None:
        if aviso in self._ativos:
            self._ativos.remove(aviso)
        try:
            aviso.deleteLater()
        except RuntimeError:
            # Ja destruido junto com a janela; nada a fazer.
            pass
        self._reposicionar()

    def _reposicionar(self) -> None:
        margem = 18
        y = self.janela.height() - margem
        # De baixo para cima: o mais recente fica embaixo, perto de onde o
        # olho ja esta quando algo acaba de acontecer.
        for aviso in reversed(self._ativos):
            try:
                y -= aviso.height() + 8
                aviso.move(self.janela.width() - aviso.width() - margem, y)
            except RuntimeError:
                # Widget ja destruido pelo deleteLater; sai da lista na
                # proxima passada.
                continue
