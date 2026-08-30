"""Ativacao do Windows e do Office, e a chave gravada na BIOS.

Duas perguntas que mudam a decisao antes de formatar:

    A licenca sobrevive a formatacao?  OEM e digital sim, volume depende
    do dominio, retail precisa da chave em maos.

    O Office e assinatura ou compra?   Assinatura vencida volta a pedir
    login; MSI comprado precisa da chave.

A chave da BIOS (OA3x) so existe em maquina que veio com Windows de
fabrica. Desktop montado devolve vazio - nao e erro, e a ausencia de
licenca OEM. Distinguir os dois casos e o ponto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import win

# Valores de LicenseStatus do WMI. Sao numeros justamente para nao
# depender do idioma do Windows.
SITUACOES = {
    0: ("Não licenciado", "erro"),
    1: ("Ativado", "ok"),
    2: ("Carência inicial", "atencao"),
    3: ("Carência por troca de hardware", "atencao"),
    4: ("Cópia não genuína", "erro"),
    5: ("Não ativado", "erro"),
    6: ("Carência estendida", "atencao"),
}

# O canal decide se a licenca acompanha a maquina ou o dono.
EXPLICACAO_CANAL = {
    "OEM": "presa a esta placa-mãe; volta sozinha ao reinstalar",
    "RETAIL": "transferível, mas precisa da chave ou da conta Microsoft",
    "VOLUME": "depende do servidor de ativação da empresa",
    "TIMEBASED_SUB": "assinatura: expira e volta a pedir login",
    "SUBSCRIPTION": "assinatura: expira e volta a pedir login",
}


@dataclass
class Produto:
    nome: str
    canal: str = ""
    situacao: str = ""
    alerta: str = ""          # "" | "atencao" | "erro"
    chave_parcial: str = ""
    observacao: str = ""


def _canal(descricao: str) -> str:
    # "Windows(R) Operating System, RETAIL channel" -> "RETAIL"
    if "," not in descricao:
        return ""
    cauda = descricao.rsplit(",", 1)[1].strip()
    return cauda.replace("channel", "").strip().upper()


def _explicar(canal: str) -> str:
    for chave, texto in EXPLICACAO_CANAL.items():
        if chave in canal:
            return texto
    return ""


def chave_da_bios() -> str:
    """Chave OEM gravada no firmware, ou string vazia se nao houver."""
    saida = win.powershell(
        "(Get-CimInstance SoftwareLicensingService).OA3xOriginalProductKey")
    return saida.texto.strip() if saida.ok else ""


def produtos(relatar=lambda _: None) -> list[Produto]:
    relatar("Lendo licenças...")
    consulta = (
        "Get-CimInstance SoftwareLicensingProduct "
        "-Filter 'PartialProductKey IS NOT NULL' "
        "| Select-Object Name,Description,LicenseStatus,PartialProductKey "
        "| ConvertTo-Json -Compress"
    )
    saida = win.powershell(consulta, tempo_limite=120)
    if not saida.ok or not saida.texto.strip():
        return []

    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    lista = []
    for d in dados:
        canal = _canal(d.get("Description") or "")
        rotulo, alerta = SITUACOES.get(d.get("LicenseStatus"),
                                       ("Desconhecido", "atencao"))
        lista.append(Produto(
            nome=(d.get("Name") or "").strip(),
            canal=canal,
            situacao=rotulo,
            alerta=alerta,
            chave_parcial=(d.get("PartialProductKey") or "").strip(),
            observacao=_explicar(canal),
        ))
    return lista


def resumo(relatar=lambda _: None) -> tuple[list[Produto], str]:
    """Produtos e a chave da BIOS, prontos para a tela e para o PDF."""
    lista = produtos(relatar)
    chave = chave_da_bios()
    if chave:
        relatar("Chave OEM encontrada no firmware.")
    return lista, chave
