r"""Impressoras, fila travada e o reparo do spooler.

Chamado de todo dia: "manda imprimir e nao sai nada". Quase sempre e um
documento com erro travando a fila inteira - o proximo trabalho entra,
espera e nunca sai. Limpar a fila resolve em trinta segundos.

O REPARO E DESTRUTIVO E ESTA ESCRITO
    Parar o spooler e apagar C:\Windows\System32\spool\PRINTERS descarta
    TODOS os trabalhos pendentes, de todas as impressoras e de todos os
    usuarios. Nao ha como apagar so o travado por esse caminho. Por isso a
    tela pede confirmacao mostrando quantos trabalhos serao perdidos.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import win

# Numeros do WMI/CIM, imunes a idioma.
ESTADOS_TRABALHO = {
    0: "normal", 1: "pausado", 2: "erro", 4: "excluindo",
    8: "em impressão", 16: "offline", 32: "papel acabou",
    64: "impresso", 128: "excluído", 256: "bloqueado",
}


@dataclass
class Trabalho:
    documento: str
    dono: str = ""
    estado: str = ""
    paginas: int = 0
    problema: bool = False


@dataclass
class Impressora:
    nome: str
    estado: str = ""
    padrao: bool = False
    offline: bool = False
    porta: str = ""
    driver: str = ""
    fila: list[Trabalho] = field(default_factory=list)

    @property
    def travada(self) -> bool:
        return any(t.problema for t in self.fila)


def _json(consulta: str, tempo_limite: int = 120):
    saida = win.powershell(consulta, tempo_limite=tempo_limite)
    if not saida.ok or not saida.texto.strip():
        return []
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    return [dados] if isinstance(dados, dict) else dados


def listar(relatar=lambda _: None) -> list[Impressora]:
    relatar("Lendo impressoras...")
    dados = _json(
        "Get-CimInstance Win32_Printer | Select-Object Name,Default,"
        "WorkOffline,PortName,DriverName,PrinterStatus "
        "| ConvertTo-Json -Compress")

    lista = []
    for d in dados:
        nome = (d.get("Name") or "").strip()
        if not nome:
            continue
        lista.append(Impressora(
            nome=nome,
            padrao=bool(d.get("Default")),
            offline=bool(d.get("WorkOffline")),
            porta=(d.get("PortName") or "").strip(),
            driver=(d.get("DriverName") or "").strip(),
        ))

    trabalhos = _json(
        "Get-CimInstance Win32_PrintJob | Select-Object Name,Document,Owner,"
        "StatusMask,TotalPages | ConvertTo-Json -Compress")
    for t in trabalhos:
        # Win32_PrintJob.Name vem como "Impressora, 3" - a parte antes da
        # virgula e a impressora dona do trabalho.
        bruto = (t.get("Name") or "")
        alvo = bruto.split(",")[0].strip()
        mascara = int(t.get("StatusMask") or 0)
        rotulos = [texto for bit, texto in ESTADOS_TRABALHO.items()
                   if bit and (mascara & bit)]
        trabalho = Trabalho(
            documento=(t.get("Document") or "(sem nome)").strip(),
            dono=(t.get("Owner") or "").strip(),
            estado=", ".join(rotulos) or "na fila",
            paginas=int(t.get("TotalPages") or 0),
            # Erro, offline ou papel acabado seguram a fila inteira.
            problema=bool(mascara & (2 | 16 | 32 | 256)),
        )
        for imp in lista:
            if imp.nome.lower() == alvo.lower():
                imp.fila.append(trabalho)
                break

    relatar(f"{len(lista)} impressora(s), "
            f"{sum(len(i.fila) for i in lista)} trabalho(s) na fila.")
    return lista


@dataclass
class ResultadoSpooler:
    ok: bool = False
    mensagem: str = ""


COMANDO_SPOOLER = [
    "powershell", "-NoProfile", "-Command",
    "Stop-Service Spooler -Force -ErrorAction Stop; "
    r'Remove-Item "$env:WINDIR\System32\spool\PRINTERS\*" -Recurse -Force '
    "-ErrorAction SilentlyContinue; "
    "Start-Service Spooler -ErrorAction Stop",
]


def limpar_fila(relatar=lambda _: None,
                percentual=lambda _: None) -> ResultadoSpooler:
    """Para o spooler, esvazia a pasta de trabalhos e religa."""
    from . import admin

    if not admin.e_administrador():
        return ResultadoSpooler(
            mensagem="Limpar a fila exige executar como administrador.")

    relatar("Parando o spooler e limpando a fila...")
    percentual(-1)
    saida = win.rodar(COMANDO_SPOOLER, tempo_limite=180)
    percentual(100)

    if saida.ok:
        relatar("Spooler reiniciado com a fila vazia.")
        return ResultadoSpooler(True, "Fila limpa e spooler reiniciado.")
    return ResultadoSpooler(
        False, (saida.erro.strip().splitlines() or ["falha desconhecida"])[0])
