"""Gera o executavel unico do aplicativo.

    python construir.py

Resultado: dist/Ripper.exe - roda em qualquer Windows
10/11 de 64 bits, sem Python instalado e sem runtime externo.

Nao usa --uac-admin de proposito: um utilitario que pede UAC toda vez que
abre acostuma o usuario a clicar "sim" sem ler, e a maioria das telas
funciona sem elevacao. As acoes que precisam avisam na propria tela.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOME = "Ripper"

# Modulos do Qt que o app nao usa. Sem excluir, o executavel carrega
# WebEngine, 3D e multimidia e passa de 150 MB.
EXCLUIR = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "tkinter",
    "unittest",
    "pydoc",
]


def main() -> int:
    for pasta in ("build", "dist"):
        alvo = RAIZ / pasta
        if alvo.exists():
            shutil.rmtree(alvo, ignore_errors=True)

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile",
        "--windowed",                # sem console preto atras da janela
        "--name", NOME,
        # ENTRADA: principal.py, nunca tecnico/__main__.py. O __main__ usa
        # import relativo; o PyInstaller o analisa como script solto, o
        # import falha em silencio e o .exe sai sem o Qt dentro.
    ]

    icone = RAIZ / "recursos" / "app.ico"
    if icone.exists():
        comando += ["--icon", str(icone)]

    # Os SVG da cena precisam viajar dentro do executavel. Sem isto o app
    # abre na maquina do cliente com a plataforma vazia - e o localizador
    # em tecnico/recursos.py cuida de achar a pasta extraida em tempo de
    # execucao.
    fontes = RAIZ / "recursos" / "fontes"
    if fontes.is_dir():
        # Sem as fontes empacotadas o Qt cai num substituto e a interface
        # inteira muda de cara na maquina do cliente.
        comando += ["--add-data", f"{fontes}{os.pathsep}recursos/fontes"]

    # Os PNGs do 3dicons continuam no repositorio como referencia, mas nao
    # entram mais no executavel: a grade desenha os icones em codigo desde
    # o visual novo, e empacotar 12 imagens sem uso e so peso.

    for modulo in EXCLUIR:
        comando += ["--exclude-module", modulo]

    comando.append("principal.py")

    print("Compilando... isso leva alguns minutos.\n")
    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        print("\nFalhou.")
        return resultado.returncode

    exe = RAIZ / "dist" / f"{NOME}.exe"
    if exe.exists():
        print(f"\nPronto: {exe}")
        print(f"Tamanho: {exe.stat().st_size / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
