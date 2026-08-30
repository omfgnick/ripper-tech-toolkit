"""Diagnostico de rede. Leitura e testes; nada e alterado sem pedido."""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field

import psutil

from . import win


@dataclass
class Teste:
    rotulo: str
    valor: str
    situacao: str = "ok"   # ok | atencao | erro


@dataclass
class Diagnostico:
    testes: list[Teste] = field(default_factory=list)
    saida_bruta: str = ""

    @property
    def situacao_geral(self) -> str:
        if any(t.situacao == "erro" for t in self.testes):
            return "erro"
        if any(t.situacao == "atencao" for t in self.testes):
            return "atencao"
        return "ok"


def _adaptador_ativo() -> tuple[str, str] | None:
    """Devolve (nome, ip) da primeira interface com IPv4 nao-local."""
    for nome, enderecos in psutil.net_if_addrs().items():
        estatisticas = psutil.net_if_stats().get(nome)
        if not estatisticas or not estatisticas.isup:
            continue
        for e in enderecos:
            if e.family == socket.AF_INET and not e.address.startswith("127."):
                return nome, e.address
    return None


def _ping(alvo: str, tentativas: int = 4) -> tuple[bool, float | None, float]:
    """Devolve (respondeu, latencia_media_ms, perda_pct).

    Usa Test-Connection e nao o ping.exe: a saida do ping vem traduzida
    para o idioma do Windows e qualquer regex sobre ela quebra numa
    maquina em ingles. ResponseTime devolve numero inteiro em ms.

    A perda sai da diferenca entre respostas pedidas e recebidas - e o
    sintoma que separa "sem internet" de "internet instavel", que sao
    dois atendimentos completamente diferentes.
    """
    script = (
        f"(Test-Connection -ComputerName '{alvo}' -Count {tentativas} "
        f"-ErrorAction SilentlyContinue).ResponseTime -join ','"
    )
    saida = win.powershell(script, 45)
    bruto = saida.texto.strip()

    if not bruto:
        return False, None, 100.0

    tempos: list[float] = []
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            tempos.append(float(pedaco))
        except ValueError:
            continue

    if not tempos:
        return False, None, 100.0

    perda = max(0.0, (tentativas - len(tempos)) / tentativas * 100.0)
    return True, sum(tempos) / len(tempos), perda


def _configuracao_ip() -> tuple[str | None, list[str]]:
    """Gateway e DNS via Get-NetIPConfiguration.

    Substitui o parsing de `ipconfig /all`, que so funciona se o Windows
    estiver no mesmo idioma que o regex.
    """
    script = (
        "$c = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | "
        "Select-Object -First 1; "
        "if ($c) { [pscustomobject]@{ "
        "gw = $c.IPv4DefaultGateway.NextHop; "
        "dns = @($c.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | "
        "ForEach-Object { $_.ServerAddresses }) } | "
        "ConvertTo-Json -Compress }"
    )
    saida = win.powershell(script, 30)
    if not saida.texto.strip():
        return None, []

    import json
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return None, []

    gw = dados.get("gw")
    dns = dados.get("dns") or []
    if isinstance(dns, str):
        dns = [dns]
    return gw, [d for d in dns if d]


def diagnosticar(relatar=lambda _: None, percentual=lambda _: None,
                 cancelado=lambda: False) -> Diagnostico:
    d = Diagnostico()
    bruto: list[str] = []

    relatar("Identificando adaptador...")
    percentual(10)
    ativo = _adaptador_ativo()
    if ativo:
        nome, ip = ativo
        d.testes.append(Teste("Adaptador ativo", nome))
        d.testes.append(Teste("Endereço IPv4", ip))
    else:
        d.testes.append(Teste("Adaptador ativo", "nenhum encontrado", "erro"))
        return d

    if cancelado():
        return d

    relatar("Lendo gateway e DNS...")
    percentual(28)
    endereco_gw, dns = _configuracao_ip()
    bruto.append(win.rodar(["ipconfig", "/all"], 25).texto)

    d.testes.append(Teste("Gateway", endereco_gw or "não identificado",
                          "ok" if endereco_gw else "erro"))
    d.testes.append(Teste("Servidor DNS", ", ".join(dns) if dns else "não configurado",
                          "ok" if dns else "erro"))

    if cancelado():
        d.saida_bruta = "\n".join(bruto)
        return d

    if endereco_gw:
        relatar("Testando o gateway...")
        percentual(48)
        ok, lat, perda = _ping(endereco_gw, 4)
        d.testes.append(Teste(
            "Resposta do gateway",
            f"{lat:.0f} ms" if ok and lat is not None else "sem resposta",
            "ok" if ok and perda == 0 else ("atencao" if ok else "erro")))

    relatar("Testando saída para a internet...")
    percentual(68)
    ok, lat, perda = _ping("1.1.1.1", 4)
    # Perda parcial e o sintoma classico de wi-fi ruim ou cabo mal crimpado:
    # merece destaque proprio, nao pode virar so "ok".
    situacao = "ok" if ok and perda == 0 else ("atencao" if ok else "erro")
    d.testes.append(Teste(
        "Internet (1.1.1.1)",
        f"{lat:.0f} ms, {perda:.0f}% de perda" if ok else "sem resposta",
        situacao))

    if cancelado():
        d.saida_bruta = "\n".join(bruto)
        return d

    relatar("Resolvendo nome...")
    percentual(86)
    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname("www.google.com")
        d.testes.append(Teste("Resolução de nomes", "funcionando"))
    except OSError:
        # DNS quebrado com ping OK e o caso mais comum de "internet caiu"
        d.testes.append(Teste("Resolução de nomes", "falhou", "erro"))

    relatar("Diagnóstico de rede concluído.")
    percentual(100)
    d.saida_bruta = "\n".join(bruto)
    return d


# --------------------------------------------------------------------
# Acoes que ALTERAM a configuracao. Chamadas so com confirmacao na tela.
# --------------------------------------------------------------------
ACOES = {
    "limpar_dns": ("Limpar cache DNS",
                   "Descarta o cache de nomes. Resolve site que abre em um "
                   "aparelho e não em outro.",
                   ["ipconfig", "/flushdns"], False),
    "renovar_ip": ("Renovar IP",
                   "Devolve o IP atual e pede outro ao servidor DHCP. A "
                   "conexão cai por alguns segundos.",
                   ["ipconfig", "/renew"], False),
    "reset_winsock": ("Redefinir Winsock",
                      "Restaura a pilha de rede do Windows. EXIGE REINICIAR "
                      "a máquina depois.",
                      ["netsh", "winsock", "reset"], True),
    "reset_tcpip": ("Redefinir TCP/IP",
                    "Reescreve a configuração TCP/IP. EXIGE REINICIAR a "
                    "máquina depois.",
                    ["netsh", "int", "ip", "reset"], True),
}


def executar_acao(chave: str, relatar=lambda _: None, percentual=lambda _: None,
                  cancelado=lambda: False) -> str:
    titulo, _desc, comando, _admin = ACOES[chave]
    relatar(f"Executando: {' '.join(comando)}")
    percentual(-1)
    saida = win.rodar(comando, 90)
    texto = (saida.texto or saida.erro).strip()
    relatar(f"{titulo}: {'concluído' if saida.ok else 'falhou'}")
    return texto or "(sem saída)"


# --------------------------------------------------------------------
# TESTE DE VELOCIDADE
# --------------------------------------------------------------------
@dataclass
class Velocidade:
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    latencia_ms: float | None = None
    bytes_baixados: int = 0
    erro: str = ""

    @property
    def ok(self) -> bool:
        return not self.erro and self.download_mbps > 0


# Endpoint publico da Cloudflare, sem cadastro e sem chave. Usado porque
# tem presenca global: o resultado reflete a conexao do cliente e nao a
# distancia ate um servidor unico no outro hemisferio.
_URL_DOWNLOAD = "https://speed.cloudflare.com/__down?bytes={n}"
_URL_UPLOAD = "https://speed.cloudflare.com/__up"

# Servidores de teste, tentados em ordem. Ter mais de um nao e excesso de
# zelo: a Cloudflare devolve 403 depois de varias medicoes seguidas do
# mesmo IP, e rede corporativa costuma liberar um provedor e barrar outro.
# `bytes_previstos` alimenta a barra de progresso; None significa que o
# tamanho vem do proprio arquivo.
SERVIDORES = [
    ("Cloudflare", "https://speed.cloudflare.com/__down?bytes={n}", None),
    ("Hetzner", "https://speed.hetzner.de/10MB.bin", 10_000_000),
    ("OVH", "https://proof.ovh.net/files/10Mb.dat", 10_000_000),
]

_URL_UPLOAD = "https://speed.cloudflare.com/__up"

# O endpoint recusa User-Agent desconhecido com 403. Identificar-se como
# navegador nao e disfarce: e o formato que o servico aceita.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _baixar_medindo(url: str, previsto: int, percentual, medida,
                    cancelado) -> tuple[int, float]:
    """Baixa e cronometra. Devolve (bytes lidos, segundos decorridos)."""
    import time
    import urllib.request

    pedido = urllib.request.Request(url, headers={"User-Agent": _UA})
    inicio = time.perf_counter()
    lidos = 0
    ultimo_aviso = 0.0

    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        while True:
            if cancelado():
                break
            pedaco = resposta.read(64 * 1024)
            if not pedaco:
                break
            lidos += len(pedaco)
            percentual(min(100, int(lidos / previsto * 100)))

            # No maximo 12 leituras por segundo. Emitir a cada bloco de
            # 64 KB inundaria a fila de sinais do Qt numa conexao rapida
            # e travaria o ponteiro em vez de anima-lo.
            agora = time.perf_counter()
            if agora - ultimo_aviso >= 0.08:
                ultimo_aviso = agora
                parcial = agora - inicio
                if parcial > 0.15:
                    medida((lidos * 8) / parcial / 1_000_000)

    return lidos, time.perf_counter() - inicio


def testar_velocidade(bytes_alvo: int = 25_000_000, relatar=lambda _: None,
                      percentual=lambda _: None, medida=lambda _: None,
                      cancelado=lambda: False) -> Velocidade:
    """Mede a banda real baixando um bloco de dados e cronometrando.

    Nao usa biblioteca de speedtest: elas trazem dependencia pesada e
    dependem de lista de servidores que muda. urllib da biblioteca padrao
    resolve, e o numero que importa - quanto o cliente realmente recebe -
    e o mesmo.
    """
    import time
    import urllib.error
    import urllib.request

    v = Velocidade()

    # Latencia primeiro: uma conexao curta antes de saturar o link
    ok, lat, _perda = _ping("1.1.1.1", 3)
    if ok:
        v.latencia_ms = lat

    if cancelado():
        return v

    ultimo_erro = ""
    for nome, molde, previsto in SERVIDORES:
        if cancelado():
            return v
        relatar(f"Medindo download via {nome}...")
        url = molde.format(n=bytes_alvo) if "{n}" in molde else molde
        alvo = previsto or bytes_alvo

        try:
            lidos, decorrido = _baixar_medindo(url, alvo, percentual,
                                               medida, cancelado)
        except Exception as erro:  # noqa: BLE001
            ultimo_erro = str(erro)
            relatar(f"{nome} indisponível ({erro}). Tentando o próximo...")
            continue

        if lidos > 0 and decorrido > 0:
            v.bytes_baixados = lidos
            # 8 bits por byte, 1 Mbit = 1e6 bits (padrao de operadora, e
            # nao 2^20 - por isso "100 mega" nunca da 100 MB/s)
            v.download_mbps = (lidos * 8) / decorrido / 1_000_000
            medida(v.download_mbps)
            break
    else:
        v.erro = f"Nenhum servidor de teste respondeu. Último: {ultimo_erro}"
        return v

    if cancelado():
        return v

    relatar("Medindo upload...")
    percentual(-1)
    try:
        carga = b"0" * 5_000_000
        pedido = urllib.request.Request(
            _URL_UPLOAD, data=carga,
            headers={"Content-Type": "application/octet-stream",
                     "User-Agent": _UA},
        )
        inicio = time.perf_counter()
        with urllib.request.urlopen(pedido, timeout=30):
            pass
        decorrido = time.perf_counter() - inicio
        if decorrido > 0:
            v.upload_mbps = (len(carga) * 8) / decorrido / 1_000_000
    except Exception:  # noqa: BLE001
        # Upload e complemento: falhar aqui nao invalida o download, que
        # e o numero que o cliente reclama.
        pass

    percentual(100)
    relatar(f"Download {v.download_mbps:.1f} Mbps · "
            f"Upload {v.upload_mbps:.1f} Mbps")
    return v
