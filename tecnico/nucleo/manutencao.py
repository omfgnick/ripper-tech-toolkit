"""Acoes de manutencao: instalacao em lote e backup de perfil.

Duas tarefas que ocupam a maior parte de um pos-formatacao e que nao
exigem pensar - so exigem tempo.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import win


# ---------------------------------------------------------------------
# INSTALACAO EM LOTE
# ---------------------------------------------------------------------
@dataclass
class Programa:
    id_winget: str
    nome: str
    categoria: str
    padrao: bool = False


# Lista curada. Ids conferidos no repositorio publico do winget; nomes
# escritos como o tecnico fala, nao como o fabricante registra.
CATALOGO: list[Programa] = [
    Programa("Google.Chrome", "Google Chrome", "Navegador", True),
    Programa("Mozilla.Firefox", "Mozilla Firefox", "Navegador"),
    Programa("7zip.7zip", "7-Zip", "Utilitário", True),
    Programa("Adobe.Acrobat.Reader.64-bit", "Adobe Acrobat Reader", "Documentos", True),
    Programa("VideoLAN.VLC", "VLC Media Player", "Mídia", True),
    Programa("Notepad++.Notepad++", "Notepad++", "Utilitário"),
    Programa("AnyDeskSoftwareGmbH.AnyDesk", "AnyDesk", "Acesso remoto", True),
    Programa("TeamViewer.TeamViewer", "TeamViewer", "Acesso remoto"),
    Programa("Microsoft.PowerToys", "Microsoft PowerToys", "Utilitário"),
    Programa("Piriform.CCleaner", "CCleaner", "Utilitário"),
    Programa("Oracle.JavaRuntimeEnvironment", "Java Runtime", "Runtime"),
    Programa("Microsoft.VCRedist.2015+.x64", "Visual C++ Redistribuível", "Runtime", True),
    Programa("Google.Drive", "Google Drive", "Nuvem"),
    Programa("Microsoft.WindowsTerminal", "Windows Terminal", "Utilitário"),
]


def winget_disponivel() -> bool:
    """winget nao vem em toda instalacao: falta em Windows 10 antigo e em
    imagens LTSC. Melhor descobrir antes de oferecer a tela."""
    return win.rodar(["winget", "--version"], 20).ok


@dataclass
class ResultadoInstalacao:
    instalados: list[str] = field(default_factory=list)
    falharam: list[tuple[str, str]] = field(default_factory=list)
    ja_tinha: list[str] = field(default_factory=list)


def instalar(ids: list[str], relatar=lambda _: None, percentual=lambda _: None,
             cancelado=lambda: False) -> ResultadoInstalacao:
    r = ResultadoInstalacao()
    nomes = {p.id_winget: p.nome for p in CATALOGO}

    for i, ident in enumerate(ids):
        if cancelado():
            break
        nome = nomes.get(ident, ident)
        relatar(f"Instalando {nome}...")
        percentual(int(i / max(len(ids), 1) * 100))

        saida = win.rodar([
            "winget", "install", "--id", ident, "--exact",
            "--silent", "--accept-package-agreements",
            "--accept-source-agreements",
            # Escopo de maquina falha sem elevacao; o winget cai para
            # usuario sozinho quando permitido.
            "--disable-interactivity",
        ], 900)

        texto = (saida.texto + saida.erro).lower()
        if saida.ok:
            r.instalados.append(nome)
        elif "already installed" in texto or "já está instalado" in texto:
            r.ja_tinha.append(nome)
        else:
            primeira = next((l.strip() for l in (saida.texto or saida.erro).splitlines()
                             if l.strip()), "falha desconhecida")
            r.falharam.append((nome, primeira[:120]))

    percentual(100)
    relatar(f"{len(r.instalados)} instalado(s), {len(r.ja_tinha)} já presente(s), "
            f"{len(r.falharam)} com falha.")
    return r


# ---------------------------------------------------------------------
# BACKUP DE PERFIL
# ---------------------------------------------------------------------
@dataclass
class Pasta:
    chave: str
    titulo: str
    caminho: Path
    bytes_total: int = 0
    arquivos: int = 0
    marcada: bool = True


def pastas_perfil() -> list[Pasta]:
    """Pastas do usuario que valem copiar antes de formatar.

    Nao inclui AppData: e enorme, cheio de cache e a maior parte nao
    serve em maquina nova. Quem precisa de algo de la sabe pedir.
    """
    perfil = Path(os.environ.get("USERPROFILE", ""))
    candidatas = [
        ("documentos", "Documentos", perfil / "Documents"),
        ("area_trabalho", "Área de Trabalho", perfil / "Desktop"),
        ("imagens", "Imagens", perfil / "Pictures"),
        ("videos", "Vídeos", perfil / "Videos"),
        ("musicas", "Músicas", perfil / "Music"),
        ("downloads", "Downloads", perfil / "Downloads"),
        ("favoritos", "Favoritos", perfil / "Favorites"),
    ]
    return [Pasta(c, t, p) for c, t, p in candidatas if p.is_dir()]


def medir_perfil(relatar=lambda _: None, percentual=lambda _: None,
                 cancelado=lambda: False) -> list[Pasta]:
    lista = pastas_perfil()
    for i, pasta in enumerate(lista):
        if cancelado():
            break
        relatar(f"Medindo {pasta.titulo}...")
        percentual(int(i / max(len(lista), 1) * 100))
        for raiz, _dirs, arquivos in os.walk(pasta.caminho,
                                             onerror=lambda _e: None):
            for nome in arquivos:
                try:
                    pasta.bytes_total += (Path(raiz) / nome).stat().st_size
                    pasta.arquivos += 1
                except OSError:
                    continue
        # Downloads costuma ser o maior e o menos importante: fica
        # desmarcado por padrao para nao inflar o backup sem querer.
        pasta.marcada = pasta.chave != "downloads"
    percentual(100)
    return lista


@dataclass
class ResultadoBackup:
    copiados: int = 0
    bytes_copiados: int = 0
    falharam: int = 0
    destino: str = ""


def copiar_perfil(pastas: list[Pasta], destino: str | Path,
                  relatar=lambda _: None, percentual=lambda _: None,
                  cancelado=lambda: False) -> ResultadoBackup:
    """Copia as pastas marcadas para `destino`, preservando a estrutura."""
    import socket
    from datetime import datetime

    selecionadas = [p for p in pastas if p.marcada and p.arquivos]
    total_bytes = sum(p.bytes_total for p in selecionadas) or 1

    raiz_destino = Path(destino) / (
        f"backup_{socket.gethostname()}_{datetime.now():%Y-%m-%d_%H%M}"
    )
    raiz_destino.mkdir(parents=True, exist_ok=True)

    r = ResultadoBackup(destino=str(raiz_destino))
    feitos = 0

    for pasta in selecionadas:
        if cancelado():
            break
        relatar(f"Copiando {pasta.titulo}...")
        alvo_base = raiz_destino / pasta.titulo

        for raiz, _dirs, arquivos in os.walk(pasta.caminho,
                                             onerror=lambda _e: None):
            if cancelado():
                break
            relativo = Path(raiz).relative_to(pasta.caminho)
            alvo_dir = alvo_base / relativo
            try:
                alvo_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                r.falharam += 1
                continue

            for nome in arquivos:
                if cancelado():
                    break
                origem = Path(raiz) / nome
                try:
                    tamanho = origem.stat().st_size
                    # copy2 preserva data de modificacao: o cliente
                    # reconhece os proprios arquivos pela data.
                    shutil.copy2(origem, alvo_dir / nome)
                    r.copiados += 1
                    r.bytes_copiados += tamanho
                    feitos += tamanho
                    if r.copiados % 25 == 0:
                        percentual(min(100, int(feitos / total_bytes * 100)))
                except OSError:
                    # Arquivo em uso ou sem permissao. Contar e seguir e
                    # melhor que abortar um backup de 40 GB no fim.
                    r.falharam += 1

    percentual(100)
    from .win import formatar_bytes
    relatar(f"{r.copiados} arquivos copiados ({formatar_bytes(r.bytes_copiados)}), "
            f"{r.falharam} com falha.")
    return r


def espaco_livre(destino: str | Path) -> int:
    try:
        return shutil.disk_usage(str(destino)).free
    except OSError:
        return 0
