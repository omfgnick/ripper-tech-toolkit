"""Limpeza de arquivos temporarios e rastros de uso.

REGRA DE SEGURANCA
Esta e a unica parte do app que apaga arquivos, entao ela obedece a tres
limites que nao devem ser afrouxados:

1. LISTA BRANCA. So percorre pastas declaradas em ALVOS. Nunca aceita um
   caminho vindo da interface, nunca varre a pasta do usuario inteira.
2. VARRE ANTES DE APAGAR. A funcao `varrer` so mede. Apagar exige chamar
   `limpar` com a lista que veio da varredura - o tecnico ve o que sai
   antes de sair.
3. NAO INSISTE. Arquivo em uso e pulado em silencio. Forcar exclusao de
   arquivo travado e como se quebra perfil de usuario.

Pasta de documentos, area de trabalho, downloads e imagens NAO aparecem
em ALVOS e nao devem aparecer.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Alvo:
    chave: str
    titulo: str
    descricao: str
    pastas: list[Path] = field(default_factory=list)
    # Mantem os N arquivos mais recentes (usado em logs, onde o ultimo
    # arquivo costuma ser o que o tecnico quer ler).
    manter_recentes: int = 0
    marcado_por_padrao: bool = True


@dataclass
class Achado:
    chave: str
    titulo: str
    bytes_total: int = 0
    arquivos: int = 0
    caminhos: list[Path] = field(default_factory=list)
    marcado: bool = True


def _local(*partes: str) -> Path:
    return Path(os.path.expandvars(os.path.join(*partes)))


def alvos() -> list[Alvo]:
    """Lista branca. Toda pasta que o app pode limpar esta aqui."""
    perfil = os.environ.get("USERPROFILE", "")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    local_app = os.environ.get("LOCALAPPDATA", "")

    return [
        Alvo("temp_usuario", "Temporários do usuário",
             "Pasta %TEMP% da conta atual.",
             [Path(os.environ.get("TEMP", ""))]),

        Alvo("temp_windows", "Temporários do Windows",
             "Pasta Temp do sistema. Exige administrador para limpar tudo.",
             [Path(windir) / "Temp"]),

        Alvo("update", "Cache do Windows Update",
             "Instaladores já aplicados. O Windows rebaixa novamente se precisar.",
             [Path(windir) / "SoftwareDistribution" / "Download"]),

        Alvo("miniaturas", "Cache de miniaturas",
             "Pré-visualizações de imagens. O Explorer refaz sob demanda.",
             [_local(local_app, "Microsoft", "Windows", "Explorer")]),

        Alvo("erros", "Relatórios de erro",
             "Despejos do Windows Error Reporting.",
             [_local(local_app, "CrashDumps"),
              _local(perfil, "AppData", "Local", "Microsoft", "Windows", "WER")]),

        Alvo("cache_navegador", "Cache de navegadores",
             "Chrome, Edge e Brave. Não remove senhas, favoritos nem sessões.",
             [_local(local_app, "Google", "Chrome", "User Data", "Default", "Cache"),
              _local(local_app, "Microsoft", "Edge", "User Data", "Default", "Cache"),
              _local(local_app, "BraveSoftware", "Brave-Browser", "User Data",
                     "Default", "Cache")]),

        Alvo("rastros", "Rastros de uso",
             "Lista de documentos recentes e atalhos de Jump List.",
             [_local(perfil, "AppData", "Roaming", "Microsoft", "Windows", "Recent")],
             marcado_por_padrao=False),

        Alvo("logs", "Logs de instalação",
             "Registros do CBS e do DISM. Mantém os 2 mais recentes.",
             [Path(windir) / "Logs" / "CBS", Path(windir) / "Logs" / "DISM"],
             manter_recentes=2, marcado_por_padrao=False),
    ]


def _dentro_da_lista_branca(caminho: Path, permitidas: list[Path]) -> bool:
    """Ultima barreira antes de apagar.

    Mesmo que a lista de caminhos chegue adulterada, nada e removido se
    nao estiver sob uma das pastas declaradas em ALVOS. Vale a redundancia:
    o custo de errar aqui e apagar arquivo de cliente.
    """
    try:
        real = caminho.resolve()
    except OSError:
        return False

    for base in permitidas:
        try:
            real.relative_to(base.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def varrer(relatar=lambda _: None, percentual=lambda _: None,
           cancelado=lambda: False) -> list[Achado]:
    """Mede o que pode ser liberado. NAO apaga nada."""
    lista = alvos()
    achados: list[Achado] = []

    for i, alvo in enumerate(lista):
        if cancelado():
            break
        relatar(f"Verificando {alvo.titulo.lower()}...")
        percentual(int(i / len(lista) * 100))

        achado = Achado(alvo.chave, alvo.titulo, marcado=alvo.marcado_por_padrao)

        for pasta in alvo.pastas:
            if not pasta.exists():
                continue

            entradas: list[tuple[Path, int, float]] = []
            for raiz, _dirs, arquivos in os.walk(pasta, onerror=lambda _e: None):
                for nome in arquivos:
                    caminho = Path(raiz) / nome
                    try:
                        st = caminho.stat()
                    except OSError:
                        continue
                    entradas.append((caminho, st.st_size, st.st_mtime))

            # Preserva os mais recentes quando o alvo pede
            if alvo.manter_recentes:
                entradas.sort(key=lambda e: e[2], reverse=True)
                entradas = entradas[alvo.manter_recentes:]

            for caminho, tamanho, _mtime in entradas:
                achado.caminhos.append(caminho)
                achado.bytes_total += tamanho
                achado.arquivos += 1

        achados.append(achado)

    percentual(100)
    total = sum(a.bytes_total for a in achados)
    from .win import formatar_bytes
    relatar(f"Varredura concluída — {formatar_bytes(total)} podem ser liberados.")
    return achados


@dataclass
class Resultado:
    removidos: int = 0
    bytes_liberados: int = 0
    ignorados: int = 0     # em uso ou sem permissao
    erros: list[str] = field(default_factory=list)


def limpar(achados: list[Achado], relatar=lambda _: None,
           percentual=lambda _: None, cancelado=lambda: False) -> Resultado:
    """Remove os arquivos dos achados MARCADOS.

    Recebe o resultado da varredura, e nao caminhos avulsos: assim o que
    e apagado e exatamente o que foi mostrado ao tecnico.
    """
    permitidas = [p for a in alvos() for p in a.pastas]
    selecionados = [a for a in achados if a.marcado and a.caminhos]
    total = sum(len(a.caminhos) for a in selecionados) or 1

    resultado = Resultado()
    feitos = 0

    for achado in selecionados:
        if cancelado():
            break
        relatar(f"Limpando {achado.titulo.lower()}...")

        for caminho in achado.caminhos:
            if cancelado():
                break
            feitos += 1
            if feitos % 40 == 0:
                percentual(int(feitos / total * 100))

            if not _dentro_da_lista_branca(caminho, permitidas):
                resultado.ignorados += 1
                continue

            try:
                tamanho = caminho.stat().st_size
                caminho.unlink()
                resultado.removidos += 1
                resultado.bytes_liberados += tamanho
            except (PermissionError, OSError):
                # Arquivo aberto por outro processo. Pular e o certo -
                # insistir aqui e o que corrompe perfil e cache.
                resultado.ignorados += 1
            except Exception as erro:  # noqa: BLE001
                resultado.erros.append(f"{caminho.name}: {erro}")

    # Remove pastas que ficaram vazias, sem tocar nas raizes dos alvos.
    for base in permitidas:
        if not base.exists():
            continue
        for raiz, dirs, _arquivos in os.walk(base, topdown=False,
                                             onerror=lambda _e: None):
            if Path(raiz) == base:
                continue
            try:
                if not os.listdir(raiz):
                    os.rmdir(raiz)
            except OSError:
                pass

    percentual(100)
    from .win import formatar_bytes
    relatar(f"Limpeza concluída — {formatar_bytes(resultado.bytes_liberados)} liberados.")
    return resultado


def esvaziar_lixeira() -> Resultado:
    """Lixeira tem API propria: apagar os arquivos direto deixaria o
    contador do Explorer dessincronizado."""
    from . import win
    r = Resultado()
    saida = win.powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    if not saida.ok and saida.erro:
        r.erros.append(saida.erro.strip()[:200])
    return r
