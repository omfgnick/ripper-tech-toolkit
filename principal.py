r"""Ponto de entrada para execucao direta e para o PyInstaller.

Existe separado de tecnico/__main__.py por um motivo pratico: o
__main__.py usa import relativo (`from .app import main`), que so funciona
quando o modulo roda dentro do pacote. O PyInstaller analisa o arquivo
como script solto, o import relativo falha em silencio e o executavel sai
sem nenhuma biblioteca do Qt dentro - 8 MB em vez de 47.

Aqui o import e absoluto, entao a analise enxerga a arvore inteira.

MODOS SEM JANELA
    Ripper.exe --verificar          confere os recursos empacotados
    Ripper.exe --marcar-antes       registra o estado inicial da maquina
    Ripper.exe --relatorio          varre e gera o PDF
    Ripper.exe --relatorio --comparar --saida D:\cliente\

Sem nenhum desses argumentos a janela abre normalmente. A verificacao
grava um arquivo ao lado do executavel: como a versao empacotada roda sem
console, ele e a unica forma de diagnosticar "abriu mas a ilustracao nao
aparece" na maquina de um cliente.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _verificar() -> int:
    from tecnico import recursos
    from tecnico.nucleo import admin

    empacotado = getattr(sys, "_MEIPASS", None)
    linhas = [
        "VERIFICACAO DO ASSISTENTE DE ATENDIMENTO",
        "=" * 52,
        f"Python            : {sys.version.split()[0]}",
        f"Empacotado        : {'sim' if empacotado else 'nao (rodando do codigo)'}",
        f"Pasta de recursos : {recursos.raiz()}",
        f"Administrador     : {'sim' if admin.e_administrador() else 'nao'}",
        "",
    ]

    from tecnico.ui.paineis.inicio import FUNCOES

    faltando = 0

    # Os icones da grade sao desenhados em codigo, nao carregados de
    # arquivo - conferir a existencia de PNG aqui daria falha falsa em
    # tudo. O que importa agora e o nome bater com uma forma registrada.
    from tecnico.ui import icones

    linhas.append("ICONES DA GRADE")
    linhas.append("-" * 52)
    for _chave, rotulo, nome, _destino in FUNCOES:
        existe = nome in icones.FORMAS
        if not existe:
            faltando += 1
        linhas.append(f"  {'OK   ' if existe else 'FALTA'} {rotulo:<30} {nome}")

    # A fonte viaja dentro do executavel. Sem ela o Qt cai num substituto
    # e o visual muda de cara na maquina do cliente - falha silenciosa que
    # so este relatorio revela, porque a versao empacotada nao tem console.
    linhas += ["", "TIPOGRAFIA", "-" * 52]
    from PySide6.QtGui import QGuiApplication

    from tecnico import recursos, tema

    arquivos = recursos.fontes()
    linhas.append(f"  Arquivos .ttf encontrados : {len(arquivos)}")
    for arquivo in arquivos:
        linhas.append(f"    {arquivo.name}")

    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv[:1])
    registrou = tema.registrar_fontes()
    familia = tema.familia()
    if familia != tema.Fonte.FAMILIA:
        faltando += 1
    linhas.append(f"  Registro no Qt            : {'ok' if registrou else 'FALHOU'}")
    linhas.append(f"  Familia em uso            : {familia}")

    destino = Path(sys.executable).parent / "verificacao.txt"
    if not empacotado:
        destino = Path(__file__).resolve().parent / "verificacao.txt"
    destino.write_text("\n".join(linhas), encoding="utf-8")

    print("\n".join(linhas))
    print(f"\nRelatorio salvo em: {destino}")
    return 0 if not faltando else 1


if __name__ == "__main__":
    from tecnico.cli import _prender_console, executar

    if "--verificar" in sys.argv:
        _prender_console()
        raise SystemExit(_verificar())

    # -1 significa "nenhum argumento de linha de comando": segue para a
    # janela. Qualquer outro valor e o codigo de saida do modo sem janela.
    codigo = executar()
    if codigo != -1:
        raise SystemExit(codigo)

    from tecnico.app import main
    raise SystemExit(main())
