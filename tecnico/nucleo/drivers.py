r"""Backup e restauracao dos drivers de terceiros.

O caso que justifica existir: notebook de 2016, fabricante tirou a pagina
de suporte do ar, e o unico lugar do mundo onde ainda existe o driver da
placa de rede e a instalacao que o tecnico esta prestes a formatar. Sem
rede na maquina nova nao da nem para baixar o resto.

Sao exportados so os pacotes de terceiros (oemN.inf). Driver nativo do
Windows volta sozinho na instalacao e copiar so faria peso.

LISTAGEM SEM ADMIN, EXPORTACAO COM
    Listar usa CIM e roda com usuario comum. Exportar e restaurar mexem no
    repositorio de drivers do Windows e exigem elevacao - o app avisa em
    vez de falhar no meio.

POR QUE CIM E NAO `pnputil /enum-drivers`
    A saida do pnputil e texto traduzido: "Nome Publicado", "Nome do
    Provedor". Depender disso quebra em cada idioma de Windows. O CIM
    devolve os mesmos dados com nomes de campo fixos.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import win

CONSULTA = (
    "Get-CimInstance Win32_PnPSignedDriver "
    "| Where-Object { $_.InfName -like 'oem*' } "
    "| Select-Object InfName,DeviceName,DriverProviderName,DriverVersion,"
    "DeviceClass | ConvertTo-Json -Compress"
)


@dataclass
class Driver:
    inf: str
    dispositivo: str
    fornecedor: str
    versao: str
    classe: str


def listar(relatar=lambda _: None) -> list[Driver]:
    """Pacotes de terceiros ligados a um dispositivo PRESENTE.

    A lista aqui e sempre menor que o que a exportacao produz, e isso e
    esperado: o teste elevado desta maquina listou 22 pacotes e exportou
    37. O CIM so enxerga driver preso a um dispositivo conectado agora; o
    repositorio do Windows guarda tambem os de impressora que ficou na
    outra sala, dock desconectado e webcam que o cliente levou junto.

    A exportacao leva tudo de proposito - o que falta na maquina nova e
    justamente o driver do periferico que nao estava plugado no dia.
    """
    relatar("Lendo drivers de terceiros...")
    saida = win.powershell(CONSULTA)
    if not saida.ok or not saida.texto.strip():
        return []

    import json
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        # Uma unica maquina com um unico driver de terceiro devolve objeto,
        # nao lista. ConvertTo-Json nao tem -AsArray em PowerShell 5.
        dados = [dados]

    vistos, drivers = set(), []
    for d in dados:
        inf = (d.get("InfName") or "").lower()
        # Um pacote cobre varios dispositivos: o mesmo oem12.inf aparece
        # uma vez por porta USB. Contar repetido inflaria o numero.
        if not inf or inf in vistos:
            continue
        vistos.add(inf)
        drivers.append(Driver(
            inf=inf,
            dispositivo=(d.get("DeviceName") or "").strip(),
            fornecedor=(d.get("DriverProviderName") or "").strip(),
            versao=(d.get("DriverVersion") or "").strip(),
            classe=(d.get("DeviceClass") or "").strip().title(),
        ))
    drivers.sort(key=lambda x: (x.classe, x.fornecedor, x.dispositivo))
    return drivers


@dataclass
class Resultado:
    ok: bool = False
    destino: str = ""
    pacotes: int = 0
    mensagem: str = ""


def _contar_inf(pasta: Path) -> int:
    try:
        return sum(1 for _ in pasta.rglob("*.inf"))
    except OSError:
        return 0


def exportar(destino: str | Path, relatar=lambda _: None,
             percentual=lambda _: None) -> Resultado:
    """Copia todos os pacotes de terceiros para uma pasta.

    Nao lemos a saida do pnputil, que e traduzida. O que interessa e o
    codigo de retorno e quantos .inf existem na pasta no fim - fato
    verificavel, independente de idioma.
    """
    from . import admin

    if not admin.e_administrador():
        return Resultado(mensagem="Exportar drivers exige executar como "
                                  "administrador. Reabra o Ripper elevado.")

    pasta = Path(destino) / "drivers"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as erro:
        return Resultado(mensagem=f"Não foi possível criar {pasta}: {erro}")

    relatar(f"Exportando drivers para {pasta}...")
    percentual(-1)      # sem progresso mensuravel: o pnputil nao informa
    saida = win.rodar(["pnputil", "/export-driver", "*", str(pasta)],
                      tempo_limite=600)
    pacotes = _contar_inf(pasta)
    percentual(100)

    if pacotes == 0:
        return Resultado(destino=str(pasta), mensagem=(
            saida.erro.strip() or "Nenhum driver foi exportado."))

    relatar(f"{pacotes} pacote(s) exportado(s).")
    return Resultado(ok=True, destino=str(pasta), pacotes=pacotes,
                     mensagem=f"{pacotes} pacote(s) em {pasta}")


def restaurar(origem: str | Path, relatar=lambda _: None,
              percentual=lambda _: None) -> Resultado:
    """Instala de volta os pacotes de uma pasta de backup."""
    from . import admin

    if not admin.e_administrador():
        return Resultado(mensagem="Restaurar drivers exige executar como "
                                  "administrador. Reabra o Ripper elevado.")

    pasta = Path(origem)
    if pasta.name.lower() != "drivers" and (pasta / "drivers").is_dir():
        # Conveniencia: o tecnico aponta a pasta do backup e o app acha a
        # subpasta que ele mesmo criou na exportacao.
        pasta = pasta / "drivers"

    total = _contar_inf(pasta)
    if total == 0:
        return Resultado(mensagem=f"Nenhum arquivo .inf em {pasta}.")

    relatar(f"Instalando {total} pacote(s) de {pasta}...")
    percentual(-1)
    saida = win.rodar(
        ["pnputil", "/add-driver", str(pasta / "*.inf"), "/subdirs", "/install"],
        tempo_limite=900)
    percentual(100)

    # 3010 = sucesso pedindo reinicio. Tratar como falha assustaria o
    # tecnico a toa: os drivers entraram.
    if saida.codigo in (0, 3010):
        reinicio = " Reinicie para concluir." if saida.codigo == 3010 else ""
        relatar(f"Drivers instalados.{reinicio}")
        return Resultado(ok=True, destino=str(pasta), pacotes=total,
                         mensagem=f"{total} pacote(s) instalado(s).{reinicio}")
    return Resultado(destino=str(pasta), pacotes=total, mensagem=(
        saida.erro.strip() or f"pnputil retornou código {saida.codigo}."))
