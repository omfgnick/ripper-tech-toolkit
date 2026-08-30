"""Inventario de hardware voltado a orcamento de upgrade.

O Diagnostico ja diz quanta memoria a maquina tem. O que decide venda e
outra coisa: quantos slots estao LIVRES, que tipo de pente cabe e ate
quanto a placa aceita. Sem isso o tecnico precisa abrir o gabinete ou
procurar o manual da placa para dar um preco.

TIPO DE MEMORIA VEM POR NUMERO
    SMBIOSMemoryType e um codigo numerico da especificacao, igual em
    qualquer idioma de Windows. O campo de texto equivalente costuma vir
    vazio ou como "Unknown" em placa de consumo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import win

TIPOS_MEMORIA = {
    20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3",
    26: "DDR4", 34: "DDR5", 35: "LPDDR5",
}


@dataclass
class Pente:
    slot: str
    bytes_total: int = 0
    velocidade: int = 0
    fabricante: str = ""
    codigo: str = ""


@dataclass
class Memoria:
    slots_totais: int = 0
    slots_usados: int = 0
    maximo_bytes: int = 0
    tipo: str = ""
    pentes: list[Pente] = field(default_factory=list)

    @property
    def slots_livres(self) -> int:
        return max(0, self.slots_totais - self.slots_usados)

    @property
    def instalado_bytes(self) -> int:
        return sum(p.bytes_total for p in self.pentes)

    @property
    def cabe_upgrade(self) -> bool:
        return self.slots_livres > 0 or (
            self.maximo_bytes > self.instalado_bytes * 1.5)


@dataclass
class Inventario:
    memoria: Memoria = field(default_factory=Memoria)
    discos: list = field(default_factory=list)
    oportunidades: list[str] = field(default_factory=list)


def _json(consulta: str, tempo_limite: int = 120):
    saida = win.powershell(consulta, tempo_limite=tempo_limite)
    if not saida.ok or not saida.texto.strip():
        return []
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    return [dados] if isinstance(dados, dict) else dados


def memoria(relatar=lambda _: None) -> Memoria:
    relatar("Lendo slots de memória...")
    m = Memoria()

    arranjo = _json("Get-CimInstance Win32_PhysicalMemoryArray "
                    "| Select-Object MemoryDevices,MaxCapacityEx "
                    "| ConvertTo-Json -Compress")
    if arranjo:
        m.slots_totais = int(arranjo[0].get("MemoryDevices") or 0)
        # MaxCapacityEx vem em KB.
        m.maximo_bytes = int(arranjo[0].get("MaxCapacityEx") or 0) * 1024

    pentes = _json("Get-CimInstance Win32_PhysicalMemory "
                   "| Select-Object BankLabel,DeviceLocator,Capacity,Speed,"
                   "Manufacturer,PartNumber,SMBIOSMemoryType "
                   "| ConvertTo-Json -Compress")
    for d in pentes:
        m.pentes.append(Pente(
            slot=f"{(d.get('BankLabel') or '').strip()} "
                 f"{(d.get('DeviceLocator') or '').strip()}".strip(),
            bytes_total=int(d.get("Capacity") or 0),
            velocidade=int(d.get("Speed") or 0),
            fabricante=(d.get("Manufacturer") or "").strip(),
            codigo=(d.get("PartNumber") or "").strip(),
        ))
        if not m.tipo:
            m.tipo = TIPOS_MEMORIA.get(d.get("SMBIOSMemoryType"), "")

    m.slots_usados = len(m.pentes)
    return m


def levantar(relatar=lambda _: None, percentual=lambda _: None) -> Inventario:
    """Inventario com as oportunidades de upgrade ja escritas."""
    from . import desempenho, saude
    from .win import formatar_bytes

    inv = Inventario()
    percentual(20)
    inv.memoria = memoria(relatar)

    percentual(60)
    relatar("Lendo discos...")
    try:
        inv.discos = saude.discos()
    except OSError:
        inv.discos = []

    m = inv.memoria
    if m.slots_livres:
        inv.oportunidades.append(
            f"{m.slots_livres} slot(s) de memória livre(s) de {m.slots_totais}. "
            f"Cabe mais {m.tipo or 'memória'}"
            + (f" de {m.pentes[0].velocidade} MHz" if m.pentes
               and m.pentes[0].velocidade else "")
            + f", até {formatar_bytes(m.maximo_bytes)} no total."
            if m.maximo_bytes else ".")
    elif m.maximo_bytes and m.maximo_bytes > m.instalado_bytes:
        inv.oportunidades.append(
            f"Slots cheios, mas a placa aceita até "
            f"{formatar_bytes(m.maximo_bytes)}. Upgrade exige trocar os "
            "pentes, não acrescentar.")

    mecanicos = [d for d in inv.discos if (d.tipo or "").upper().startswith("HDD")]
    if mecanicos:
        inv.oportunidades.append(
            f"{len(mecanicos)} disco(s) mecânico(s): "
            + ", ".join(d.modelo for d in mecanicos[:2])
            + ". Troca por SSD é o upgrade de maior impacto.")

    percentual(100)
    relatar(f"{len(inv.oportunidades)} oportunidade(s) de upgrade.")
    return inv
