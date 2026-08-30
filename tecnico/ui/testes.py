"""Testes que exigem o olho e a mao do tecnico: tela e teclado.

Sao os dois defeitos que o cliente relata e que somem na hora de mostrar.
Pixel morto so aparece contra campo de cor solida, e tecla que falha so
aparece quando alguem aperta todas.

Ambos abrem em tela cheia porque e a unica forma honesta de testar: barra
de titulo e janela cobrem justamente a area que precisa ser inspecionada.
Esc fecha, sempre, e isso fica escrito na tela.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter
from PySide6.QtWidgets import QWidget

from ..tema import Cor, Fonte, familia

# Branco pega pixel morto (preto); preto pega pixel travado aceso; as
# primarias pegam subpixel com defeito em um canal so; cinza revela
# mancha de retroiluminacao, que some no branco puro.
CAMPOS = [
    ("#ffffff", "BRANCO — pixels mortos aparecem como pontos escuros"),
    ("#000000", "PRETO — pixels travados aparecem como pontos acesos"),
    ("#ff0000", "VERMELHO — falha no subpixel vermelho"),
    ("#00ff00", "VERDE — falha no subpixel verde"),
    ("#0000ff", "AZUL — falha no subpixel azul"),
    ("#808080", "CINZA — manchas de retroiluminação e vazamento"),
]


class TesteDeTela(QWidget):
    """Campos de cor em tela cheia, trocados por clique ou seta."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Teste de tela")
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._indice = 0

    def _andar(self, passo: int) -> None:
        self._indice = (self._indice + passo) % len(CAMPOS)
        self.update()

    def keyPressEvent(self, evento: QKeyEvent) -> None:  # noqa: N802
        if evento.key() == Qt.Key_Escape:
            self.close()
        elif evento.key() in (Qt.Key_Left, Qt.Key_Up):
            self._andar(-1)
        else:
            self._andar(1)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        self._andar(-1 if evento.button() == Qt.RightButton else 1)

    def paintEvent(self, evento) -> None:  # noqa: N802
        cor, descricao = CAMPOS[self._indice]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(cor))

        # A legenda tem que ser legivel sobre qualquer campo, inclusive o
        # branco puro: por isso vai numa tarja escura, e nao solta.
        texto = (f"{self._indice + 1}/{len(CAMPOS)}  ·  {descricao}"
                 "        CLIQUE = PRÓXIMO  ·  ESC = SAIR")
        fonte = QFont(Fonte.MONO, 10)
        p.setFont(fonte)
        altura = 34
        faixa = QRectF(0, self.height() - altura, self.width(), altura)
        p.fillRect(faixa, QColor(0, 0, 0, 210))
        p.setPen(QColor(Cor.DESTAQUE))
        p.drawText(faixa, Qt.AlignCenter, texto)
        p.end()


# Layout ABNT2 simplificado. Cada linha e uma lista de (rotulo, largura),
# onde largura 1.0 e uma tecla normal. Nao e o teclado inteiro: numerico
# e teclas de midia variam demais entre modelos, e desenhar um layout que
# nao bate com a maquina do cliente confunde mais do que ajuda.
LINHAS_TECLADO = [
    [("Esc", 1.0), ("F1", 1.0), ("F2", 1.0), ("F3", 1.0), ("F4", 1.0),
     ("F5", 1.0), ("F6", 1.0), ("F7", 1.0), ("F8", 1.0), ("F9", 1.0),
     ("F10", 1.0), ("F11", 1.0), ("F12", 1.0)],
    [("'", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0),
     ("6", 1.0), ("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0),
     ("=", 1.0), ("Back", 2.0)],
    [("Tab", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0),
     ("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("´", 1.0),
     ("[", 1.0), ("Enter", 1.5)],
    [("Caps", 1.8), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0),
     ("G", 1.0), ("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), ("Ç", 1.0),
     ("~", 1.0), ("]", 1.0)],
    [("Shift", 2.3), ("\\", 1.0), ("Z", 1.0), ("X", 1.0), ("C", 1.0),
     ("V", 1.0), ("B", 1.0), ("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0),
     (";", 1.0), ("/", 1.0), ("Shift", 1.7)],
    [("Ctrl", 1.4), ("Win", 1.1), ("Alt", 1.1), ("Espaço", 6.0),
     ("AltGr", 1.1), ("Menu", 1.1), ("Ctrl", 1.4)],
]

# Qt entrega codigos, nao letras, para as teclas nao imprimiveis.
ESPECIAIS = {
    Qt.Key_Escape: "Esc", Qt.Key_Tab: "Tab", Qt.Key_Backspace: "Back",
    Qt.Key_Return: "Enter", Qt.Key_Enter: "Enter", Qt.Key_CapsLock: "Caps",
    Qt.Key_Shift: "Shift", Qt.Key_Control: "Ctrl", Qt.Key_Alt: "Alt",
    Qt.Key_AltGr: "AltGr", Qt.Key_Meta: "Win", Qt.Key_Menu: "Menu",
    Qt.Key_Space: "Espaço", Qt.Key_Ccedilla: "Ç",
}
for _n in range(1, 13):
    ESPECIAIS[getattr(Qt, f"Key_F{_n}")] = f"F{_n}"


class TesteDeTeclado(QWidget):
    """Acende cada tecla ao ser pressionada. Sai com Esc pressionado duas
    vezes, porque a primeira precisa contar como teste da propria tecla."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Teste de teclado")
        self.setWindowState(Qt.WindowFullScreen)
        self.setFocusPolicy(Qt.StrongFocus)
        self._testadas: set[str] = set()
        self._escapes = 0

    def _rotulo(self, evento: QKeyEvent) -> str:
        if evento.key() in ESPECIAIS:
            return ESPECIAIS[evento.key()]
        texto = evento.text().strip().upper()
        return texto or ""

    def keyPressEvent(self, evento: QKeyEvent) -> None:  # noqa: N802
        if evento.key() == Qt.Key_Escape:
            self._escapes += 1
            self._testadas.add("Esc")
            if self._escapes >= 2:
                self.close()
                return
        rotulo = self._rotulo(evento)
        if rotulo:
            self._testadas.add(rotulo)
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        from . import chanfro

        p = QPainter(self)
        p.fillRect(self.rect(), QColor(Cor.FUNDO))

        margem = 40
        largura_util = self.width() - margem * 2
        unidades = max(sum(w for _r, w in linha) for linha in LINHAS_TECLADO)
        lado = min(largura_util / unidades, (self.height() - 220) / 7)
        vao = lado * 0.10

        total = sum(len(linha) for linha in LINHAS_TECLADO)
        y = (self.height() - (lado + vao) * len(LINHAS_TECLADO)) / 2

        p.setFont(QFont(familia(), max(8, int(lado * 0.26))))
        for linha in LINHAS_TECLADO:
            comprimento = sum(w for _r, w in linha) * lado + vao * (len(linha) - 1)
            x = (self.width() - comprimento) / 2
            for rotulo, peso in linha:
                caixa = QRectF(x, y, lado * peso, lado)
                testada = rotulo in self._testadas
                chanfro.pintar(
                    p, caixa.adjusted(1, 1, -1, -1),
                    Cor.DESTAQUE if testada else Cor.PAINEL,
                    Cor.DESTAQUE if testada else Cor.BORDA, 1.0,
                    chanfro=lado * 0.18)
                p.setPen(QColor(Cor.SOBRE_DESTAQUE if testada else Cor.TEXTO_SUAVE))
                p.drawText(caixa, Qt.AlignCenter, rotulo)
                x += lado * peso + vao
            y += lado + vao

        p.setFont(QFont(Fonte.MONO, 11))
        p.setPen(QColor(Cor.TEXTO_SUAVE))
        p.drawText(QRectF(0, self.height() - 70, self.width(), 30),
                   Qt.AlignCenter,
                   f"{len(self._testadas)} de {total} teclas do layout "
                   "acionadas   ·   ESC DUAS VEZES PARA SAIR")
        p.end()
