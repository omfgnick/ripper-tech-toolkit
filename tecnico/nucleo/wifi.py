"""Wi-Fi: redes ao redor, qualidade do sinal e perfis salvos.

Boa parte dos chamados de "internet lenta" nao e do provedor: e canal
congestionado. O teste de velocidade sozinho nao separa os dois casos -
ele mede o resultado, nao a causa. Ver quantas redes dividem o mesmo
canal responde isso em cinco segundos.

PERFIS SALVOS SAEM POR XML, NAO POR TEXTO
    `netsh wlan show profile name=X key=clear` imprime rotulos traduzidos.
    Ja `netsh wlan export profile key=clear` grava XML com nomes de tag
    fixos em qualquer idioma. Custa um arquivo temporario e economiza um
    parser que quebraria em Windows ingles.

A LISTA DE REDES AINDA E TEXTO
    Nao existe equivalente estruturado no Windows para varredura de
    redes. A leitura aqui procura padroes de valor (BSSID em formato MAC,
    porcentagem, numero de canal) em vez de rotulos traduzidos, que e o
    mais robusto possivel sem sair do netsh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import win

MAC = re.compile(r"\b([0-9a-f]{2}(?::[0-9a-f]{2}){5})\b", re.I)
PORCENTO = re.compile(r"\b(\d{1,3})\s*%")
# Canal aparece sozinho na linha depois do rotulo; 1-14 em 2.4 GHz e
# 32-177 em 5/6 GHz. A faixa evita confundir com taxa de transmissao.
SO_NUMERO = re.compile(r":\s*(\d{1,3})\s*$")


@dataclass
class Rede:
    ssid: str
    sinal: int = 0
    canal: int = 0
    autenticacao: str = ""
    pontos: int = 1          # BSSIDs vistos (repetidor conta separado)

    @property
    def faixa(self) -> str:
        if 1 <= self.canal <= 14:
            return "2,4 GHz"
        if self.canal >= 32:
            return "5 GHz"
        return ""


@dataclass
class Perfil:
    nome: str
    senha: str = ""
    seguranca: str = ""


@dataclass
class Estado:
    disponivel: bool = False
    motivo: str = ""
    redes: list[Rede] = field(default_factory=list)
    perfis: list[Perfil] = field(default_factory=list)


ESTADO_WIFI = (
    "@{ servico = (Get-Service wlansvc -ErrorAction SilentlyContinue)"
    ".Status.ToString(); adaptadores = @(Get-NetAdapter -Physical "
    "-ErrorAction SilentlyContinue | Where-Object "
    "{ $_.PhysicalMediaType -like '*802.11*' } "
    "| Select-Object -ExpandProperty Name) } | ConvertTo-Json -Compress"
)


def disponibilidade() -> tuple[bool, str]:
    """(tem Wi-Fi utilizavel, motivo quando nao tem).

    Checado por CIM e nao pela mensagem de erro do netsh: aquele texto e
    traduzido e, dependendo da pagina de codigo do console, chega ilegivel.
    Aqui o motivo e escrito por nos, em portugues, sempre igual.
    """
    import json

    saida = win.powershell(ESTADO_WIFI, tempo_limite=90)
    if not saida.ok or not saida.texto.strip():
        return False, "Não foi possível consultar o subsistema de rede."
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return False, "Resposta inesperada ao consultar os adaptadores."

    adaptadores = dados.get("adaptadores") or []
    if isinstance(adaptadores, str):
        adaptadores = [adaptadores]
    if not adaptadores:
        return False, "Esta máquina não tem adaptador Wi-Fi."

    servico = (dados.get("servico") or "").lower()
    if servico and servico != "running":
        return False, ("O serviço Configuração Automática de Rede sem Fio "
                       "(wlansvc) está parado. Inicie-o para usar o Wi-Fi.")
    return True, ""


def redes(relatar=lambda _: None) -> tuple[list[Rede], str]:
    """Redes ao alcance, agrupadas por SSID."""
    relatar("Varrendo redes ao alcance...")
    tem, motivo = disponibilidade()
    if not tem:
        return [], motivo

    saida = win.rodar(["netsh", "wlan", "show", "networks", "mode=bssid"],
                      tempo_limite=60)
    if not saida.ok:
        return [], "A varredura de redes falhou."

    encontradas: list[Rede] = []
    atual: Rede | None = None

    for linha in saida.texto.splitlines():
        bruta = linha.rstrip()
        if not bruta.strip():
            continue

        # Cabecalho de rede: "SSID 3 : NomeDaRede". O prefixo SSID nao e
        # traduzido pelo netsh, so os rotulos internos sao.
        cabecalho = re.match(r"\s*SSID\s+\d+\s*:\s*(.*)$", bruta)
        if cabecalho:
            nome = cabecalho.group(1).strip()
            atual = Rede(ssid=nome or "(rede oculta)")
            encontradas.append(atual)
            continue

        if atual is None:
            continue

        if MAC.search(bruta):
            atual.pontos = max(atual.pontos, len(
                [r for r in [bruta] if MAC.search(r)]) + atual.pontos - 1)
            continue

        forca = PORCENTO.search(bruta)
        if forca:
            atual.sinal = max(atual.sinal, int(forca.group(1)))
            continue

        canal = SO_NUMERO.search(bruta)
        if canal:
            valor = int(canal.group(1))
            if 1 <= valor <= 196 and not atual.canal:
                atual.canal = valor
            continue

        if ":" in bruta and not atual.autenticacao:
            valor = bruta.split(":", 1)[1].strip()
            # WPA2-Personal, WPA3-SAE, Aberta... o valor traz o padrao.
            if valor.upper().startswith(("WPA", "WEP", "RSNA")):
                atual.autenticacao = valor

    encontradas.sort(key=lambda r: r.sinal, reverse=True)
    relatar(f"{len(encontradas)} rede(s) ao alcance.")
    return encontradas, ""


def canais_disputados(lista: list[Rede]) -> dict[int, int]:
    """Quantas redes ocupam cada canal. Numero alto explica lentidao."""
    contagem: dict[int, int] = {}
    for r in lista:
        if r.canal:
            contagem[r.canal] = contagem.get(r.canal, 0) + 1
    return dict(sorted(contagem.items(), key=lambda p: -p[1]))


def _texto(no, sufixo: str) -> str:
    """Busca uma tag pelo fim do nome, ignorando o namespace do WLANProfile."""
    for filho in no.iter():
        if filho.tag.rsplit("}", 1)[-1] == sufixo and filho.text:
            return filho.text.strip()
    return ""


def perfis(relatar=lambda _: None) -> tuple[list[Perfil], str]:
    """Redes salvas com senha, exportando os perfis como XML.

    A senha em claro exige elevacao. Sem ela o Windows exporta o perfil
    sem o campo da chave: a lista sai, as senhas nao. Melhor entregar
    metade e dizer o porque do que falhar inteiro.
    """
    import shutil
    import tempfile
    import xml.etree.ElementTree as ET

    from . import admin

    tem, motivo = disponibilidade()
    if not tem:
        return [], motivo

    elevado = admin.e_administrador()
    pasta = Path(tempfile.mkdtemp(prefix="bancada_wlan_"))
    try:
        comando = ["netsh", "wlan", "export", "profile", f"folder={pasta}"]
        if elevado:
            comando.append("key=clear")
        relatar("Exportando perfis salvos...")
        win.rodar(comando, tempo_limite=120)

        lista = []
        for arquivo in sorted(pasta.glob("*.xml")):
            try:
                raiz = ET.parse(arquivo).getroot()
            except ET.ParseError:
                continue
            nome = _texto(raiz, "name")
            if not nome:
                continue
            lista.append(Perfil(
                nome=nome,
                senha=_texto(raiz, "keyMaterial"),
                seguranca=_texto(raiz, "authentication"),
            ))
    finally:
        # O XML tem senha em claro: sair sem apagar deixaria credencial do
        # cliente no %TEMP% da propria maquina dele.
        shutil.rmtree(pasta, ignore_errors=True)

    aviso = ""
    if lista and not elevado:
        aviso = ("Sem privilégio de administrador as senhas não são "
                 "exportadas. Reabra o Ripper elevado para vê-las.")
    relatar(f"{len(lista)} perfil(is) salvo(s).")
    return lista, aviso
