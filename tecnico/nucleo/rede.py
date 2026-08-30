"""Diagnostico de rede. Leitura e testes; nada e alterado sem pedido."""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field

import psutil

from . import win


@dataclass
class Teste:
    """Uma camada do diagnostico. `isola` diz o que a falha DAQUI aponta.

    A leitura em camadas so vale se cada degrau explicar o que exclui: o
    tecnico experiente sabe que gateway morto com IP valido nao e problema
    do provedor, mas o app nao dizia isso em lugar nenhum.
    """
    rotulo: str
    valor: str
    situacao: str = "ok"   # ok | atencao | erro
    isola: str = ""


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



# O que a falha de cada camada isola. Ordem do diagnostico: se uma camada
# cai, as de baixo dela nem sao a causa.
ISOLA = {
    "Adaptador ativo":
        "Nenhuma placa de rede ligada. Verifique o cabo na traseira, se o "
        "Wi-Fi está ativado e se o adaptador aparece no Gerenciador de "
        "Dispositivos. Nada abaixo disto funciona sem resolver primeiro.",
    "Endereço IPv4":
        "A placa está ligada mas não recebeu endereço. Endereço 169.254.x.x "
        "significa que o DHCP não respondeu: cabo ruim, porta do switch ou "
        "roteador travado. Reiniciar o roteador resolve a maioria.",
    "Gateway":
        "Sem rota para fora da máquina. O problema está entre ela e o "
        "roteador — cabo, porta, ou o roteador desligado. Não é o provedor.",
    "Resposta do gateway":
        "O roteador não responde ao ping. Se o IP veio por DHCP, ele estava "
        "vivo há pouco: costuma ser travamento do roteador ou Wi-Fi com "
        "sinal fraco demais para manter a sessão.",
    "Internet (1.1.1.1)":
        "A rede local funciona e a saída não. Aqui sim o dedo aponta para o "
        "provedor, ou para o roteador sem sincronizar. Confirme se outro "
        "aparelho na mesma rede também está sem internet.",
    "Servidor DNS":
        "Sem servidor de nomes configurado. A máquina alcança endereços IP "
        "mas não nomes de site — o sintoma clássico de 'a internet caiu' "
        "com o WhatsApp funcionando.",
    "Resolução de nomes":
        "IP responde e nome não resolve. O servidor DNS está configurado mas "
        "não responde, ou foi sequestrado por malware. Trocar para 1.1.1.1 "
        "ou 8.8.8.8 confirma em segundos.",
}

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
    # Preenchido no fim, e nao em cada Teste: assim a orientacao vive num
    # catalogo unico e nao espalhada por sete pontos de construcao.
    for t in d.testes:
        if t.situacao in ("erro", "atencao"):
            t.isola = ISOLA.get(t.rotulo, "")

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


# ---------------------------------------------------------------------
# LEITURA DA VELOCIDADE
# ---------------------------------------------------------------------
# A Anatel exige, para banda larga fixa, media mensal de no minimo 80% da
# velocidade contratada e instantanea de no minimo 40%. Sao esses os dois
# numeros que decidem se o caso e reclamacao com o provedor ou problema na
# casa do cliente - e sem eles o tecnico so tem um numero solto.
PISO_MEDIO = 0.80
PISO_INSTANTANEO = 0.40


def avaliar_velocidade(medido: float, plano: float) -> tuple[str, str]:
    """(situacao, leitura) do medido contra o plano contratado.

    Uma medicao unica e instantanea, entao o piso que se aplica aqui e o
    de 40%. Abaixo disso ha caso a levar ao provedor; entre 40% e 80% a
    entrega esta fraca mas exige varias medicoes para reclamar.
    """
    if not plano or plano <= 0:
        return "", ""

    fracao = medido / plano
    pct = fracao * 100

    if fracao >= PISO_MEDIO:
        return "ok", (f"{pct:.0f}% do plano de {plano:.0f} Mbps — dentro do "
                      "que a Anatel exige de média mensal (80%).")
    if fracao >= PISO_INSTANTANEO:
        return "atencao", (
            f"{pct:.0f}% do plano de {plano:.0f} Mbps — acima do piso "
            "instantâneo de 40%, mas abaixo da média de 80% que a Anatel "
            "exige. Meça em horários diferentes antes de acionar o "
            "provedor; se cair de novo, há caso.")
    return "erro", (
        f"{pct:.0f}% do plano de {plano:.0f} Mbps — abaixo do piso "
        "instantâneo de 40%. Confirme por cabo antes de reclamar: no "
        "Wi-Fi a perda pode ser do ambiente, e aí o roteador é o "
        "responsável, não o provedor.")
