"""Privilegio de administrador.

Varias funcoes de reparo do Windows exigem elevacao. O app NAO se eleva
sozinho ao abrir: pedir UAC antes de o tecnico dizer o que quer fazer e
comportamento de software suspeito. A elevacao e solicitada apenas quando
uma acao especifica precisa dela.
"""

from __future__ import annotations

import ctypes
import sys


def e_administrador() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def reabrir_como_administrador() -> bool:
    """Reabre o proprio executavel com elevacao. Devolve True se o pedido
    foi aceito - nesse caso o chamador deve encerrar a instancia atual."""
    if e_administrador():
        return True

    try:
        parametros = " ".join(f'"{a}"' for a in sys.argv[1:])
        # 'runas' e o verbo que dispara o UAC. Retorno acima de 32 = ok.
        codigo = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, parametros, None, 1
        )
        return int(codigo) > 32
    except Exception:  # noqa: BLE001
        return False
