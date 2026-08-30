"""Localizacao de arquivos de recurso.

Rodando do codigo, os recursos ficam ao lado do pacote. Dentro do .exe
gerado pelo PyInstaller com --onefile, eles sao extraidos para uma pasta
temporaria cujo caminho vem em sys._MEIPASS. Sem tratar os dois casos, o
app funciona no desenvolvimento e abre sem icone nenhum na maquina do
cliente - o tipo de falha que so aparece depois de entregue.
"""

from __future__ import annotations

import sys
from pathlib import Path


def raiz() -> Path:
    empacotado = getattr(sys, "_MEIPASS", None)
    if empacotado:
        return Path(empacotado)
    return Path(__file__).resolve().parent.parent


def icone(nome: str) -> Path:
    """Caminho de uma ilustracao em recursos/icones.

    Aceita nome com extensao ou sem. Sem extensao, procura .png antes de
    .svg: as ilustracoes 3D atuais sao PNG renderizado.
    """
    pasta = raiz() / "recursos" / "icones"
    if "." in nome:
        return pasta / nome
    for ext in (".png", ".svg"):
        caminho = pasta / f"{nome}{ext}"
        if caminho.is_file():
            return caminho
    return pasta / f"{nome}.png"


def existe(nome: str) -> bool:
    return icone(nome).is_file()


def fontes() -> list[Path]:
    """Arquivos .ttf embutidos, em ordem estavel.

    Ordem importa: o Qt registra a familia pelo primeiro arquivo e os
    demais entram como pesos dela. Alfabetica basta para ser previsivel.
    """
    pasta = raiz() / "recursos" / "fontes"
    if not pasta.is_dir():
        return []
    return sorted(pasta.glob("*.ttf"))
