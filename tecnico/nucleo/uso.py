r"""Onde foi parar o espaco, e o que esta pesando agora.

A Limpeza responde "o que da para apagar sem risco" e costuma achar
dezenas de megabytes. Nao responde "para onde foram os 400 GB" - e essa e
a pergunta que o cliente faz. Aqui o app percorre as pastas de verdade e
mostra as maiores.

CUSTO DA VARREDURA
    Percorrer C: inteiro leva minutos e boa parte do tempo se gasta em
    pastas do sistema que ninguem vai mexer. Por isso a varredura tem
    profundidade limitada: soma o tamanho total de cada pasta ate certo
    nivel e para. O tecnico ve "Users\fulano\Videos = 180 GB" e ja sabe
    para onde ir, sem esperar a arvore inteira.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROFUNDIDADE = 2
IGNORAR = {"$recycle.bin", "system volume information", "windows.old",
           "$windows.~bt", "$windows.~ws", "recovery"}


@dataclass
class Pasta:
    caminho: str
    bytes_total: int = 0
    arquivos: int = 0

    @property
    def nome(self) -> str:
        return self.caminho


def _somar(raiz: Path, cancelado) -> tuple[int, int]:
    total = arquivos = 0
    for _dir, _subs, nomes in os.walk(raiz, onerror=lambda _e: None):
        if cancelado():
            break
        for nome in nomes:
            try:
                total += (Path(_dir) / nome).stat().st_size
                arquivos += 1
            except OSError:
                continue
    return total, arquivos


def maiores_pastas(unidade: str = "", limite: int = 20,
                   relatar=lambda _: None, percentual=lambda _: None,
                   cancelado=lambda: False) -> list[Pasta]:
    """As `limite` maiores pastas ate `PROFUNDIDADE` niveis da raiz."""
    unidade = unidade or os.environ.get("SystemDrive", "C:")
    raiz = Path(unidade + "\\")

    # Nivel 1: as pastas da raiz. Nivel 2: os filhos de cada uma. Alem
    # disso a lista fica longa demais para ser util numa tela.
    candidatas: list[Path] = []
    try:
        for item in raiz.iterdir():
            if not item.is_dir() or item.name.lower() in IGNORAR:
                continue
            filhos = []
            try:
                filhos = [f for f in item.iterdir() if f.is_dir()]
            except OSError:
                pass
            # Pasta com poucos filhos e melhor medida inteira; com muitos,
            # os filhos e que interessam.
            candidatas.extend(filhos if len(filhos) > 1 else [item])
    except OSError as erro:
        relatar(f"Não foi possível ler {raiz}: {erro}")
        return []

    achadas: list[Pasta] = []
    for i, pasta in enumerate(candidatas):
        if cancelado():
            break
        percentual(int(i / max(len(candidatas), 1) * 100))
        relatar(f"Medindo {pasta}...")
        total, arquivos = _somar(pasta, cancelado)
        if total:
            achadas.append(Pasta(str(pasta), total, arquivos))

    achadas.sort(key=lambda p: -p.bytes_total)
    percentual(100)
    relatar(f"{len(achadas)} pasta(s) medidas.")
    return achadas[:limite]


# ---------------------------------------------------------------------
# PROCESSOS
# ---------------------------------------------------------------------
@dataclass
class Processo:
    pid: int
    nome: str
    memoria: int = 0
    cpu: float = 0.0
    usuario: str = ""


def processos(limite: int = 15, relatar=lambda _: None) -> list[Processo]:
    """Os que mais pesam agora, por memoria.

    O apontamento de "memoria sob pressao" dizia a porcentagem e nao o
    culpado. Sem o nome do programa, o tecnico nao tem o que fazer com a
    informacao.
    """
    import psutil

    relatar("Lendo processos...")
    # Primeira leitura de cpu_percent sempre volta 0.0: ela mede o
    # intervalo desde a chamada anterior. Por isso duas passadas.
    vivos = list(psutil.process_iter(["pid", "name", "memory_info", "username"]))
    for p in vivos:
        try:
            p.cpu_percent(None)
        except psutil.Error:
            continue

    import time
    time.sleep(0.4)

    lista = []
    for p in vivos:
        try:
            info = p.info
            memoria = info["memory_info"].rss if info["memory_info"] else 0
            lista.append(Processo(
                pid=info["pid"],
                nome=info["name"] or "?",
                memoria=memoria,
                cpu=round(p.cpu_percent(None), 1),
                usuario=(info["username"] or "").split("\\")[-1],
            ))
        except (psutil.Error, KeyError, AttributeError):
            continue

    lista.sort(key=lambda x: -x.memoria)
    relatar(f"{len(lista)} processo(s) lidos.")
    return lista[:limite]
