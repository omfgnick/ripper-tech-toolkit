r"""Onde o app guarda o que precisa sobreviver ao fechamento.

Dois lugares possiveis:

    dados/ ao lado do executavel   -> modo pendrive
    %LOCALAPPDATA%\Ripper\        -> modo instalado

O modo pendrive nao e detectado por tipo de unidade. Testar se o drive e
removivel falha nos dois sentidos: HD externo aparece como fixo, e cartao
SD interno de notebook aparece como removivel. A marca e explicita - a
existencia da pasta `dados` ao lado do executavel. O tecnico cria uma vez
no pendrive e o historico passa a viajar junto, em vez de ficar espalhado
pelas maquinas dos clientes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MARCA = "dados"


def _ao_lado_do_executavel() -> Path:
    if getattr(sys, "_MEIPASS", None):
        # _MEIPASS e a pasta temporaria onde o onefile se descompacta e
        # some ao fechar. O que interessa e onde esta o .exe de verdade.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def portatil() -> bool:
    return (_ao_lado_do_executavel() / MARCA).is_dir()


# Nome anterior do produto. Fica aqui ate nao sobrar instalacao antiga.
NOME_ANTERIOR = "Bancada"


def _migrar(destino: Path) -> None:
    """Move os dados da pasta do nome antigo, uma vez so.

    Renomear o produto nao pode custar o historico de quem ja atendeu
    maquina com a versao anterior: a ficha e os instantaneos sao a memoria
    do servico, e some-los seria pior que manter o nome velho.
    """
    antiga = Path(os.environ.get("LOCALAPPDATA", Path.home())) / NOME_ANTERIOR
    if not antiga.is_dir() or antiga == destino:
        return

    import shutil

    for item in antiga.iterdir():
        alvo = destino / item.name
        if alvo.exists():
            # Ja existe no destino: nao sobrescrever. O tecnico decide.
            continue
        try:
            shutil.move(str(item), str(alvo))
        except OSError:
            continue
    # Sobram as subpastas vazias de onde o conteudo saiu; limpa-las evita
    # deixar uma arvore fantasma com o nome antigo no perfil do usuario.
    for sobra in sorted(antiga.rglob("*"), reverse=True):
        try:
            if sobra.is_dir():
                sobra.rmdir()
        except OSError:
            pass
    try:
        antiga.rmdir()      # so remove se ficou vazia
    except OSError:
        pass


def base() -> Path:
    if portatil():
        destino = _ao_lado_do_executavel() / MARCA
    else:
        destino = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Ripper"
        destino.mkdir(parents=True, exist_ok=True)
        _migrar(destino)
        return destino
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def pasta(nome: str) -> Path:
    destino = base() / nome
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ativar_portatil() -> Path:
    """Cria a pasta `dados` ao lado do executavel e devolve o caminho."""
    destino = _ao_lado_do_executavel() / MARCA
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def descricao() -> str:
    return f"{'pendrive' if portatil() else 'instalado'} — {base()}"


def registro_da_sessao() -> Path:
    """Arquivo de log do dia, ao lado do historico.

    O registro que aparece na tela some quando o app fecha. Meses depois,
    ao reabrir a ficha da maquina, o que ficou foram os numeros do
    instantaneo - nao o que o tecnico de fato executou. Este arquivo
    guarda isso.

    Um arquivo por dia e nao por atendimento: o tecnico atende varias
    maquinas no mesmo dia e nem sempre em ordem, e separar por sessao
    geraria dezenas de arquivos de tres linhas.
    """
    from datetime import date

    return pasta("registros") / f"{date.today():%Y-%m-%d}.log"


def anotar_no_registro(painel: str, mensagem: str) -> None:
    from datetime import datetime

    try:
        with registro_da_sessao().open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S}  [{painel}] {mensagem}\n")
    except OSError:
        # Log e conveniencia, nao funcao. Pendrive protegido contra
        # escrita nao pode derrubar o atendimento por causa disso.
        pass
