"""Instantaneos da maquina: antes/depois do atendimento e historico local.

Duas necessidades que compartilham a mesma estrutura:

1. Provar o servico. O cliente ve "limpei o computador" e nao sabe o que
   mudou. Um instantaneo no inicio e outro no fim viram uma tabela com
   numeros: espaco liberado, itens de inicializacao removidos.

2. Reconhecer a maquina. Quando o mesmo computador volta em tres meses, o
   historico mostra se o problema e recorrente ou novo.

O arquivo e JSON Lines: cada atendimento e uma linha. Formato que aguenta
ser truncado no meio (queda de energia durante a gravacao) sem perder as
linhas anteriores, ao contrario de um JSON unico.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from . import dados, limpeza, programas, win


# ---------------------------------------------------------------------
# CAPTURA
# ---------------------------------------------------------------------
@dataclass
class Instantaneo:
    momento: str = ""
    maquina: str = ""
    serie: str = ""
    marca: str = ""
    rotulo: str = ""              # "antes" | "depois" | livre
    disco_livre: int = 0
    disco_total: int = 0
    lixo_bytes: int = 0
    lixo_arquivos: int = 0
    itens_inicializacao: int = 0
    programas_instalados: int = 0
    memoria_usada_pct: float = 0.0
    uptime_horas: float = 0.0


# Placeholders que fabricantes de placa-mae deixam no BIOS. Um desktop
# montado quase sempre tem um destes, e todos cairiam no mesmo arquivo de
# historico — misturando clientes diferentes na mesma ficha.
LIXO_SERIE = {
    "to be filled by o.e.m.", "to be filled by o.e.m",
    "default string", "system serial number", "0123456789",
    "none", "n/a", "na", "not specified", "not applicable",
    "chassis serial number", "无", "0",
}


def _serie_valida(valor: str | None) -> str:
    valor = (valor or "").strip()
    if len(valor) < 4 or valor.lower() in LIXO_SERIE:
        return ""
    return valor


def _primeiro(classe: str, campos: list[str]) -> dict:
    dados = win.consultar(classe, campos) or {}
    if isinstance(dados, list):
        dados = dados[0] if dados else {}
    return dados


def identidade() -> tuple[str, str, str]:
    """(nome, identificador estavel, marca+modelo).

    A cadeia de fallback vai do mais especifico ao mais generico: serie do
    sistema, serie da placa-mae, UUID, e por fim o nome do computador. Em
    notebook de marca a primeira resolve; em desktop montado ela e um
    placeholder e quem identifica de verdade e a placa-mae.
    """
    sistema_ = _primeiro("Win32_ComputerSystemProduct",
                         ["IdentifyingNumber", "Vendor", "Name", "UUID"])
    placa = _primeiro("Win32_BaseBoard", ["SerialNumber", "Manufacturer",
                                          "Product"])

    def limpar(*partes):
        # O mesmo placeholder aparece no fabricante e no modelo. Sem filtrar,
        # a ficha do cliente sai como "To Be Filled By O.E.M. B450M".
        bons = [x.strip() for x in partes
                if x and x.strip().lower() not in LIXO_SERIE]
        return " ".join(bons).strip()

    marca = (limpar(sistema_.get("Vendor"), sistema_.get("Name"))
             or limpar(placa.get("Manufacturer"), placa.get("Product")))

    serie = (_serie_valida(sistema_.get("IdentifyingNumber"))
             or _serie_valida(placa.get("SerialNumber"))
             or _serie_valida(sistema_.get("UUID"))
             or socket.gethostname())
    return socket.gethostname(), serie, marca


def capturar(rotulo: str = "", achados: list | None = None,
             relatar=lambda _: None, percentual=lambda _: None) -> Instantaneo:
    """Mede o estado atual. Reaproveita `achados` de uma varredura ja feita.

    A varredura de lixo e a parte lenta (percorre milhares de arquivos).
    Quem ja tem o resultado na tela passa a lista pronta.
    """
    import psutil

    nome, serie, marca = identidade()
    inst = Instantaneo(
        momento=datetime.now().isoformat(timespec="seconds"),
        maquina=nome, serie=serie, marca=marca, rotulo=rotulo,
    )

    relatar("Medindo disco e memória...")
    percentual(10)
    try:
        uso = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        inst.disco_livre, inst.disco_total = uso.free, uso.total
    except OSError:
        pass
    inst.memoria_usada_pct = psutil.virtual_memory().percent
    inst.uptime_horas = round(
        (datetime.now().timestamp() - psutil.boot_time()) / 3600, 1)

    percentual(35)
    if achados is None:
        relatar("Medindo arquivos temporários...")
        achados = limpeza.varrer()
    inst.lixo_bytes = sum(a.bytes_total for a in achados)
    inst.lixo_arquivos = sum(a.arquivos for a in achados)

    percentual(65)
    relatar("Contando inicialização e programas...")
    try:
        inst.itens_inicializacao = len(programas.listar_inicializacao())
    except OSError:
        pass
    try:
        inst.programas_instalados = len(programas.listar())
    except OSError:
        pass

    percentual(100)
    return inst


# ---------------------------------------------------------------------
# COMPARACAO
# ---------------------------------------------------------------------
@dataclass
class Mudanca:
    rotulo: str
    antes: str
    depois: str
    variacao: str = ""
    situacao: str = "neutro"      # "melhorou" | "piorou" | "neutro"


def _mudanca(rotulo, a, d, formatar, maior_e_melhor: bool,
             limiar: float = 0.0) -> Mudanca:
    """Compara um par de valores.

    O `limiar` existe porque a maquina nunca fica parada: o Windows grava
    log e cache sozinho entre as duas medicoes. Sem uma faixa morta o
    relatorio anunciaria "40 MB liberados" que ninguem liberou.
    """
    delta = d - a
    m = Mudanca(rotulo, formatar(a), formatar(d))
    if abs(delta) <= limiar:
        return m
    melhorou = (delta > 0) == maior_e_melhor
    m.situacao = "melhorou" if melhorou else "piorou"
    m.variacao = ("+" if delta > 0 else "-") + formatar(abs(delta))
    return m


def comparar(antes: Instantaneo, depois: Instantaneo) -> list[Mudanca]:
    def inteiro(v):
        return str(int(v))

    mega = 1024 * 1024
    return [
        _mudanca("Espaço livre no disco", antes.disco_livre, depois.disco_livre,
                 win.formatar_bytes, maior_e_melhor=True, limiar=50 * mega),
        _mudanca("Arquivos temporários", antes.lixo_bytes, depois.lixo_bytes,
                 win.formatar_bytes, maior_e_melhor=False, limiar=10 * mega),
        _mudanca("Itens na inicialização", antes.itens_inicializacao,
                 depois.itens_inicializacao, inteiro, maior_e_melhor=False),
        _mudanca("Programas instalados", antes.programas_instalados,
                 depois.programas_instalados, inteiro, maior_e_melhor=True),
        _mudanca("Memória em uso", antes.memoria_usada_pct,
                 depois.memoria_usada_pct, lambda v: f"{v:.0f}%",
                 maior_e_melhor=False, limiar=3),
    ]


# ---------------------------------------------------------------------
# ARMAZENAMENTO
# ---------------------------------------------------------------------
def pasta() -> Path:
    return dados.pasta("historico")


def _arquivo(inst_ou_serie) -> Path:
    if isinstance(inst_ou_serie, Instantaneo):
        chave = inst_ou_serie.serie or inst_ou_serie.maquina
    else:
        chave = str(inst_ou_serie)
    # Numero de serie vem do fabricante e costuma trazer barra ou espaco.
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in chave)
    return pasta() / f"{seguro or 'desconhecida'}.jsonl"


def registrar(inst: Instantaneo) -> Path:
    destino = _arquivo(inst)
    with destino.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(inst), ensure_ascii=False) + "\n")
    return destino


def carregar(serie: str = "") -> list[Instantaneo]:
    if not serie:
        _nome, serie, _marca = identidade()
        if not serie:
            serie = socket.gethostname()
    arquivo = _arquivo(serie)
    if not arquivo.exists():
        return []

    registros = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            # Ignora linha corrompida em vez de perder o historico inteiro:
            # e exatamente o motivo de usar JSON Lines.
            registros.append(Instantaneo(**json.loads(linha)))
        except (json.JSONDecodeError, TypeError):
            continue
    return registros


def maquinas() -> list[tuple[str, int, str]]:
    """(nome, atendimentos, ultimo momento) de tudo que ja passou aqui."""
    resultado = []
    for arquivo in sorted(pasta().glob("*.jsonl")):
        registros = carregar(arquivo.stem)
        if registros:
            resultado.append((registros[-1].maquina or arquivo.stem,
                              len(registros), registros[-1].momento))
    return resultado
