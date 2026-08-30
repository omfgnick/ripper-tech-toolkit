"""Remocao dos aplicativos de fabrica que ninguem pediu.

CATALOGO CURADO, NAO "TUDO QUE E REMOVIVEL"
    O Windows marca 46 dos 91 pacotes desta maquina como NonRemovable, e
    seria tentador oferecer os outros 45. Mas essa lista inclui o pacote
    de idioma pt-BR, os codecs HEIF/HEVC (sem eles as fotos do celular
    param de abrir) e os proprios programas que o cliente instalou.

    Entao vale a mesma regra da limpeza: lista branca do que se oferece,
    nunca lista negra do que se protege. Item desconhecido fica de fora -
    o custo de esquecer um jogo e zero, o de apagar o codec e um chamado
    de volta.

O QUE NAO ENTRA
    Edge, Store, Terminal, Notepad, Paint, Foto, Calculadora e camera:
    sao usados de verdade e removelos gera retrabalho.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import win

# (identificador do pacote, nome legivel, categoria)
CATALOGO = [
    ("Microsoft.549981C3F5F10", "Cortana", "Assistente"),
    ("Microsoft.BingNews", "Notícias", "Bing"),
    ("Microsoft.BingWeather", "Clima", "Bing"),
    ("Microsoft.BingSearch", "Pesquisa Bing", "Bing"),
    ("Microsoft.GetHelp", "Obter Ajuda", "Suporte"),
    ("Microsoft.Getstarted", "Dicas do Windows", "Suporte"),
    ("Microsoft.Microsoft3DViewer", "Visualizador 3D", "Mídia"),
    ("Microsoft.MicrosoftOfficeHub", "Office (atalho da Store)", "Office"),
    ("Microsoft.MicrosoftSolitaireCollection", "Paciência", "Jogo"),
    ("Microsoft.MixedReality.Portal", "Portal de Realidade Mista", "Mídia"),
    ("Microsoft.NetworkSpeedTest", "Teste de Velocidade", "Utilitário"),
    ("Microsoft.People", "Pessoas", "Comunicação"),
    ("Microsoft.SkypeApp", "Skype", "Comunicação"),
    ("Microsoft.Todos", "Microsoft To Do", "Produtividade"),
    ("Microsoft.WindowsAlarms", "Alarmes e Relógio", "Utilitário"),
    ("Microsoft.WindowsFeedbackHub", "Hub de Comentários", "Suporte"),
    ("Microsoft.WindowsMaps", "Mapas", "Utilitário"),
    ("Microsoft.YourPhone", "Vincular ao Celular", "Comunicação"),
    ("Microsoft.ZuneMusic", "Media Player / Groove", "Mídia"),
    ("Microsoft.ZuneVideo", "Filmes e TV", "Mídia"),
    ("Microsoft.XboxApp", "Xbox (legado)", "Xbox"),
    ("Microsoft.XboxGameOverlay", "Sobreposição do Xbox", "Xbox"),
    ("Microsoft.XboxGamingOverlay", "Barra de Jogos", "Xbox"),
    ("Microsoft.XboxSpeechToTextOverlay", "Legendas do Xbox", "Xbox"),
    ("Microsoft.GamingApp", "Aplicativo Xbox", "Xbox"),
    ("MicrosoftTeams", "Teams (pessoal)", "Comunicação"),
    ("MSTeams", "Teams", "Comunicação"),
    ("Clipchamp.Clipchamp", "Clipchamp", "Mídia"),
    ("Microsoft.OutlookForWindows", "Novo Outlook", "Comunicação"),
    ("Microsoft.Copilot", "Copilot", "Assistente"),
    # Bloat de fabricante, comum em maquina nova de loja.
    ("king.com.CandyCrush", "Candy Crush", "Jogo de fábrica"),
    ("SpotifyAB.SpotifyMusic", "Spotify (pré-instalado)", "Fábrica"),
    ("Disney.37853FC22B2CE", "Disney+", "Fábrica"),
    ("BytedancePte.Ltd.TikTok", "TikTok", "Fábrica"),
    ("Facebook.InstagramBeta", "Instagram", "Fábrica"),
    ("AmazonVideo.PrimeVideo", "Prime Video", "Fábrica"),
    ("Netflix.Netflix", "Netflix", "Fábrica"),
    ("5A894077.McAfeeSecurity", "McAfee Security", "Fábrica"),
    ("DolbyLaboratories.DolbyAccess", "Dolby Access", "Fábrica"),
]


@dataclass
class Pacote:
    identificador: str
    nome: str
    categoria: str
    nome_completo: str = ""
    marcado: bool = True


def instalados(relatar=lambda _: None) -> list[Pacote]:
    """So os itens do catalogo que existem nesta maquina."""
    relatar("Lendo aplicativos de fábrica...")
    saida = win.powershell(
        "Get-AppxPackage | Where-Object { -not $_.IsFramework } "
        "| Select-Object Name,PackageFullName,NonRemovable "
        "| ConvertTo-Json -Compress", tempo_limite=180)
    if not saida.ok or not saida.texto.strip():
        return []

    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    presentes = {}
    for d in dados:
        nome = (d.get("Name") or "").strip()
        # NonRemovable e o veredito do proprio Windows. Mesmo estando no
        # catalogo, se o sistema diz que e parte dele, nao se oferece.
        if nome and not d.get("NonRemovable"):
            presentes[nome.lower()] = (d.get("PackageFullName") or "").strip()

    achados = []
    for identificador, rotulo, categoria in CATALOGO:
        completo = presentes.get(identificador.lower())
        if completo:
            achados.append(Pacote(identificador, rotulo, categoria, completo))
    achados.sort(key=lambda p: (p.categoria, p.nome))
    relatar(f"{len(achados)} aplicativo(s) de fábrica encontrado(s).")
    return achados


@dataclass
class ResultadoRemocao:
    removidos: list[str]
    falharam: list[tuple[str, str]]


def remover(pacotes: list[Pacote], relatar=lambda _: None,
            percentual=lambda _: None,
            cancelado=lambda: False) -> ResultadoRemocao:
    """Remove os pacotes marcados, um a um.

    Um por vez, e nao num unico comando, para que a falha de um nao leve
    junto os outros - e para o tecnico ver na hora qual travou.
    """
    alvos = [p for p in pacotes if p.marcado]
    resultado = ResultadoRemocao([], [])

    for i, pacote in enumerate(alvos):
        if cancelado():
            break
        relatar(f"Removendo {pacote.nome}...")
        percentual(int(i / max(len(alvos), 1) * 100))

        saida = win.powershell(
            f"Remove-AppxPackage -Package '{pacote.nome_completo}' "
            "-ErrorAction Stop", tempo_limite=180)
        if saida.ok:
            resultado.removidos.append(pacote.nome)
        else:
            motivo = (saida.erro or saida.texto or "").strip().splitlines()
            resultado.falharam.append(
                (pacote.nome, motivo[0] if motivo else "falha desconhecida"))

    percentual(100)
    relatar(f"{len(resultado.removidos)} removido(s), "
            f"{len(resultado.falharam)} com falha.")
    return resultado
