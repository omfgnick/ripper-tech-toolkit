"""Registro de falha nao tratada e trava de instancia unica.

REGISTRO DE FALHA
    O executavel e compilado com --windowed: nao ha console. Sem um
    excepthook, uma excecao nao tratada fecha a janela e nao deixa
    vestigio nenhum - nem traceback, nem hora, nem em que tela estava.
    Na maquina de um cliente isso vira "o programa sumiu" e acabou a
    investigacao.

    Aqui a falha vira arquivo com data, versao, estado de permissao e o
    traceback inteiro, e o tecnico ve na hora onde ele foi parar.

INSTANCIA UNICA
    Duas copias abertas gravam historico e ficha uma por cima da outra,
    sem aviso, porque as duas acham que sao a unica. E travam o proprio
    executavel para regravacao - o que aconteceu de verdade durante o
    desenvolvimento desta ferramenta.

    O mutex nomeado do Windows resolve: o segundo processo descobre que
    ja existe um antes de abrir qualquer janela.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

NOME_MUTEX = r"Global\RipperAtendimentoTecnico"
ERRO_JA_EXISTE = 183

# O identificador precisa sobreviver ao escopo da funcao: o Windows solta
# o mutex quando o ultimo identificador fecha, e uma variavel local seria
# coletada logo depois de criada.
_mutex = None


def instancia_unica() -> bool:
    """True se esta e a unica instancia. False se ja havia outra."""
    global _mutex

    try:
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        _mutex = k32.CreateMutexW(None, False, ctypes.c_wchar_p(NOME_MUTEX))
        return ctypes.get_last_error() != ERRO_JA_EXISTE
    except (AttributeError, OSError):
        # Sem mutex disponivel, seguir e melhor que impedir o atendimento.
        return True


def _cabecalho() -> list[str]:
    from . import admin, dados

    return [
        "FALHA NAO TRATADA NO RIPPER",
        "=" * 62,
        f"Quando        : {datetime.now():%d/%m/%Y %H:%M:%S}",
        f"Python        : {sys.version.split()[0]}",
        f"Empacotado    : {'sim' if getattr(sys, '_MEIPASS', None) else 'nao'}",
        f"Administrador : {'sim' if admin.e_administrador() else 'nao'}",
        f"Dados em      : {dados.base()}",
        "",
    ]


def registrar(tipo, valor, rastro) -> Path | None:
    """Grava a falha e devolve o caminho do arquivo, ou None."""
    from . import dados

    linhas = _cabecalho()
    linhas.extend(traceback.format_exception(tipo, valor, rastro))

    try:
        destino = (dados.pasta("falhas")
                   / f"{datetime.now():%Y-%m-%d_%H%M%S}.txt")
        destino.write_text(
            "".join(l if l.endswith("\n") else l + "\n" for l in linhas),
            encoding="utf-8")
    except OSError:
        return None

    try:
        dados.anotar_no_registro(
            "falha", f"{tipo.__name__}: {valor} - ver {destino.name}")
    except OSError:
        pass
    return destino


def instalar_excecoes(ao_falhar=None) -> None:
    """Liga o excepthook. `ao_falhar(caminho, resumo)` avisa a interface."""
    anterior = sys.excepthook

    def capturar(tipo, valor, rastro):
        if issubclass(tipo, KeyboardInterrupt):
            anterior(tipo, valor, rastro)
            return

        caminho = registrar(tipo, valor, rastro)
        resumo = f"{tipo.__name__}: {valor}"
        if ao_falhar is not None:
            try:
                ao_falhar(caminho, resumo)
            except Exception:  # noqa: BLE001
                # Falhar ao avisar sobre a falha nao pode virar recursao.
                pass
        anterior(tipo, valor, rastro)

    sys.excepthook = capturar
