"""Programas instalados e itens de inicializacao."""

from __future__ import annotations

import winreg
from dataclasses import dataclass, field


@dataclass
class Programa:
    nome: str
    versao: str = ""
    fabricante: str = ""
    tamanho_kb: int = 0
    comando_desinstalar: str = ""
    origem: str = ""


@dataclass
class ItemInicializacao:
    nome: str
    comando: str
    origem: str          # onde esta registrado
    _chave: str = ""
    _raiz: int = 0
    _caminho: str = ""


_CHAVES_DESINSTALAR = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "64 bits"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "32 bits"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "usuário"),
]


def _ler(chave, nome: str, padrao=""):
    try:
        valor, _tipo = winreg.QueryValueEx(chave, nome)
        return valor
    except OSError:
        return padrao


def listar(relatar=lambda _: None, percentual=lambda _: None,
           cancelado=lambda: False) -> list[Programa]:
    """Le o registro. Mais confiavel que Win32_Product, que dispara
    revalidacao do MSI em cada programa e chega a levar minutos."""
    encontrados: dict[str, Programa] = {}

    for i, (raiz, caminho, origem) in enumerate(_CHAVES_DESINSTALAR):
        if cancelado():
            break
        relatar(f"Lendo programas ({origem})...")
        percentual(int(i / len(_CHAVES_DESINSTALAR) * 100))

        try:
            base = winreg.OpenKey(raiz, caminho)
        except OSError:
            continue

        with base:
            total = winreg.QueryInfoKey(base)[0]
            for indice in range(total):
                try:
                    sub = winreg.EnumKey(base, indice)
                    with winreg.OpenKey(base, sub) as k:
                        nome = str(_ler(k, "DisplayName")).strip()
                        if not nome:
                            continue
                        # Atualizacoes e componentes de sistema entopem a
                        # lista e nao sao o que o tecnico procura.
                        if _ler(k, "SystemComponent", 0) == 1:
                            continue
                        if _ler(k, "ParentKeyName"):
                            continue

                        encontrados[nome.lower()] = Programa(
                            nome=nome,
                            versao=str(_ler(k, "DisplayVersion")).strip(),
                            fabricante=str(_ler(k, "Publisher")).strip(),
                            tamanho_kb=int(_ler(k, "EstimatedSize", 0) or 0),
                            comando_desinstalar=str(
                                _ler(k, "QuietUninstallString")
                                or _ler(k, "UninstallString")).strip(),
                            origem=origem,
                        )
                except OSError:
                    continue

    percentual(100)
    lista = sorted(encontrados.values(), key=lambda p: p.nome.lower())
    relatar(f"{len(lista)} programas encontrados.")
    return lista


_CHAVES_INICIO = [
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "usuário"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "máquina"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "máquina (32 bits)"),
]


def listar_inicializacao(relatar=lambda _: None, percentual=lambda _: None,
                         cancelado=lambda: False) -> list[ItemInicializacao]:
    itens: list[ItemInicializacao] = []

    for raiz, caminho, origem in _CHAVES_INICIO:
        if cancelado():
            break
        try:
            with winreg.OpenKey(raiz, caminho) as k:
                total = winreg.QueryInfoKey(k)[1]
                for indice in range(total):
                    try:
                        nome, valor, _t = winreg.EnumValue(k, indice)
                        itens.append(ItemInicializacao(
                            nome=nome, comando=str(valor), origem=origem,
                            _raiz=raiz, _caminho=caminho, _chave=nome))
                    except OSError:
                        continue
        except OSError:
            continue

    percentual(100)
    relatar(f"{len(itens)} itens de inicialização.")
    return itens


def remover_da_inicializacao(item: ItemInicializacao) -> None:
    """Remove a entrada do registro. Itens de HKLM exigem administrador."""
    with winreg.OpenKey(item._raiz, item._caminho, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.DeleteValue(k, item._chave)
