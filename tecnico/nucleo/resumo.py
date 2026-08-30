"""Resumo do atendimento em uma imagem, para mandar ao cliente.

O PDF e para imprimir, anexar e arquivar. O cliente, na pratica, pergunta
pelo WhatsApp - e la um PDF vira "baixar arquivo", que metade das pessoas
nao abre. Uma imagem aparece na conversa.

O QUE ENTRA E O QUE FICA DE FORA
    Entra o que o cliente entende: o que melhorou, em numero, e o que
    ainda merece atencao, em uma linha cada. Fica de fora tudo que so
    interessa ao tecnico - IOPS, canal de Wi-Fi, nome de pacote AppX.
    Resumo que precisa de traducao nao e resumo.

FORMATO RETRATO
    1080x1350 e o que o WhatsApp mostra inteiro na conversa, sem cortar e
    sem exigir que a pessoa abra em tela cheia.
"""

from __future__ import annotations

from pathlib import Path

LARGURA = 1080
MARGEM = 64
LIMITE_APONTAMENTOS = 4


def _primeira_frase(texto: str, limite: int = 88) -> str:
    """Primeira frase, sem quebrar em numero decimal.

    Cortar no primeiro ponto transformava "0.6 MB/s em leitura aleatoria"
    em "0". A frase so termina quando o ponto e seguido de espaco.
    """
    texto = (texto or "").strip()
    fim = texto.find(". ")
    if fim > 0:
        texto = texto[:fim]
    elif texto.endswith("."):
        texto = texto[:-1]
    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0] + "..."
    return texto


def _fonte(tamanho: int, negrito: bool = False, mono: bool = False):
    from PySide6.QtGui import QFont

    from ..tema import Fonte, familia

    f = QFont(Fonte.MONO if mono else familia(), tamanho)
    if negrito:
        f.setWeight(QFont.Bold)
    return f


def gerar(destino, ficha=None, mudancas=None, sugestoes=None,
          checklist=None, relatar=lambda _: None) -> Path:
    """Desenha o resumo e grava o PNG. Devolve o caminho."""
    from datetime import datetime

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from ..tema import Cor
    from ..ui import chanfro

    mudancas = [m for m in (mudancas or []) if m.situacao != "neutro"]
    graves = [s for s in (sugestoes or []) if s.gravidade in ("alta", "media")]
    graves = graves[:LIMITE_APONTAMENTOS]

    altura = (300 + len(mudancas) * 58 + (140 if graves else 0)
              + len(graves) * 78 + 150)
    altura = max(altura, 900)

    imagem = QImage(LARGURA, altura, QImage.Format_RGB32)
    imagem.fill(QColor(Cor.FUNDO))
    p = QPainter(imagem)
    p.setRenderHint(QPainter.Antialiasing, True)

    interno = LARGURA - MARGEM * 2
    y = MARGEM

    # ---- cabecalho ----
    p.fillRect(0, 0, LARGURA, 8, QColor(Cor.DESTAQUE))
    p.setFont(_fonte(38, negrito=True))
    p.setPen(QColor(Cor.DESTAQUE))
    p.drawText(QRectF(MARGEM, y, interno, 54), Qt.AlignLeft | Qt.AlignVCenter,
               "RIPPER")
    p.setFont(_fonte(19))
    p.setPen(QColor(Cor.TEXTO_SUAVE))
    p.drawText(QRectF(MARGEM, y, interno, 54), Qt.AlignRight | Qt.AlignVCenter,
               datetime.now().strftime("%d/%m/%Y"))
    y += 66

    p.setFont(_fonte(26, negrito=True))
    p.setPen(QColor(Cor.TEXTO))
    titulo = "Resumo do atendimento"
    if ficha is not None and ficha.cliente:
        titulo = ficha.cliente
    p.drawText(QRectF(MARGEM, y, interno, 40), Qt.AlignLeft, titulo)
    y += 44

    if ficha is not None and ficha.equipamento:
        p.setFont(_fonte(20))
        p.setPen(QColor(Cor.TEXTO_SUAVE))
        p.drawText(QRectF(MARGEM, y, interno, 32), Qt.AlignLeft,
                   ficha.equipamento)
        y += 38
    y += 22

    # ---- o que melhorou ----
    if mudancas:
        p.setFont(_fonte(17, negrito=True))
        p.setPen(QColor(Cor.DESTAQUE))
        p.drawText(QRectF(MARGEM, y, interno, 26), Qt.AlignLeft,
                   "O QUE MUDOU")
        y += 36

        for m in mudancas:
            cor = Cor.OK if m.situacao == "melhorou" else Cor.ERRO
            caixa = QRectF(MARGEM, y, interno, 48)
            chanfro.pintar(p, caixa, Cor.PAINEL, None, 1.0, chanfro=12.0)
            p.fillRect(int(MARGEM), int(y), 4, 48, QColor(cor))

            p.setFont(_fonte(20))
            p.setPen(QColor(Cor.TEXTO))
            p.drawText(caixa.adjusted(22, 0, 0, 0),
                       Qt.AlignLeft | Qt.AlignVCenter, m.rotulo)

            p.setFont(_fonte(19, mono=True))
            p.setPen(QColor(Cor.TEXTO_FRACO))
            p.drawText(caixa.adjusted(0, 0, -150, 0),
                       Qt.AlignRight | Qt.AlignVCenter,
                       f"{m.antes}  →  ")
            p.setFont(_fonte(20, negrito=True, mono=True))
            p.setPen(QColor(cor))
            p.drawText(caixa.adjusted(0, 0, -22, 0),
                       Qt.AlignRight | Qt.AlignVCenter, m.depois)
            y += 58
        y += 18

    # ---- o que ainda merece atencao ----
    if graves:
        p.setFont(_fonte(17, negrito=True))
        p.setPen(QColor(Cor.ATENCAO))
        p.drawText(QRectF(MARGEM, y, interno, 26), Qt.AlignLeft,
                   "PONTOS DE ATENÇÃO")
        y += 36

        for s in graves:
            cor = Cor.ERRO if s.gravidade == "alta" else Cor.ATENCAO
            caixa = QRectF(MARGEM, y, interno, 70)
            chanfro.pintar(p, caixa, Cor.PAINEL, None, 1.0, chanfro=12.0)
            p.fillRect(int(MARGEM), int(y), 4, 70, QColor(cor))

            p.setFont(_fonte(20, negrito=True))
            p.setPen(QColor(Cor.TEXTO))
            p.drawText(caixa.adjusted(22, 6, -22, -36), Qt.AlignLeft,
                       s.titulo)

            p.setFont(_fonte(17))
            p.setPen(QColor(Cor.TEXTO_SUAVE))
            # Uma linha so: o cliente le no celular, e paragrafo tecnico
            # nesse espaco vira parede de texto que ninguem termina.
            p.drawText(caixa.adjusted(22, 32, -22, -4), Qt.AlignLeft,
                       _primeira_frase(s.detalhe))
            y += 78
        y += 12

    # ---- rodape ----
    if checklist:
        feitos = sum(1 for i in checklist if i.marcado)
        p.setFont(_fonte(19))
        p.setPen(QColor(Cor.OK))
        p.drawText(QRectF(MARGEM, y, interno, 32), Qt.AlignLeft,
                   f"✓  {feitos} de {len(checklist)} itens de entrega "
                   "conferidos")
        y += 44

    p.setFont(_fonte(16, mono=True))
    p.setPen(QColor(Cor.TEXTO_FRACO))
    rodape = "Relatório completo em PDF disponível"
    if ficha is not None and ficha.tecnico:
        rodape = f"{ficha.tecnico}  ·  {rodape.lower()}"
    p.drawText(QRectF(MARGEM, altura - 74, interno, 30), Qt.AlignLeft, rodape)
    p.fillRect(0, altura - 8, LARGURA, 8, QColor(Cor.DESTAQUE))
    p.end()

    caminho = Path(destino)
    if caminho.suffix.lower() != ".png":
        caminho = caminho.with_suffix(".png")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(str(caminho))
    relatar(f"Resumo salvo em {caminho}")
    return caminho


def nome_sugerido() -> str:
    import socket
    from datetime import datetime

    return (f"resumo_{socket.gethostname()}_"
            f"{datetime.now():%Y-%m-%d_%H%M}.png")
