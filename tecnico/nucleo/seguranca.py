"""Antivirus, servicos essenciais e idade das atualizacoes.

Tres perguntas que o tecnico faz de cabeca e o app nao respondia:

    Quantos antivirus estao rodando?  Dois ou tres brigando e causa
    classica de lentidao, e o cliente costuma nem saber que instalou.

    O que foi desligado?  Malware para o Windows Update, o BITS e o
    Defender para se manter instalado. Servico parado que deveria estar
    rodando e sinal, nao detalhe.

    Ha quanto tempo nao atualiza?  Em vez de cravar data de fim de
    suporte - que muda e envelhece dentro do codigo - o app mede o que e
    verificavel na hora: quando entrou a ultima correcao.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from . import win

# Servicos que, parados, indicam problema. Nome interno e o que o Windows
# usa; o rotulo e nosso, porque o DisplayName vem traduzido e muda.
# nome interno: (rotulo, o que faz, o que significa estar parado)
#
# O nome interno e o que o Windows usa; o DisplayName vem traduzido e muda
# entre versoes. O terceiro campo e o que faltava: "wscsvc desabilitado"
# nao diz nada, "malware costuma desligar este para esconder que o
# antivirus sumiu" diz tudo.
ESSENCIAIS = {
    "wuauserv": ("Windows Update",
                 "baixa e instala as atualizações de segurança",
                 "a máquina para de receber correção de falha crítica; "
                 "desligar isto é a assinatura de quem quer manter uma "
                 "brecha aberta"),
    "bits": ("Transferência inteligente (BITS)",
             "faz os downloads em segundo plano do Update e da Store",
             "o Windows Update fica travado em 0% sem explicar por quê"),
    "WinDefend": ("Microsoft Defender",
                  "é o antivírus do Windows",
                  "a máquina fica sem proteção em tempo real; se não há "
                  "outro antivírus instalado, está desprotegida agora"),
    "wscsvc": ("Central de Segurança",
               "monitora antivírus, firewall e atualizações",
               "some o aviso de que a proteção caiu — malware desliga este "
               "justamente para o usuário não perceber"),
    "Audiosrv": ("Áudio do Windows",
                 "processa todo o som do sistema",
                 "nenhum som sai, e o ícone de volume aparece com um X"),
    "Spooler": ("Spooler de impressão",
                "enfileira os trabalhos até a impressora aceitar",
                "nada imprime, e as impressoras somem das configurações"),
    "Dhcp": ("Cliente DHCP",
             "pede o endereço IP ao roteador",
             "a máquina não recebe IP e cai em 169.254.x.x, sem rede"),
    "Dnscache": ("Cliente DNS",
                 "guarda a tradução de nome para IP",
                 "navegação lenta e sites que não abrem por nome"),
    "EventLog": ("Log de eventos",
                 "registra falhas do sistema",
                 "o diagnóstico de falhas fica cego — sem histórico de tela "
                 "azul, desligamento ou erro de disco"),
    "Themes": ("Temas",
               "desenha a aparência das janelas",
               "a interface volta ao visual básico e alguns programas "
               "ficam com desenho quebrado"),
}


@dataclass
class Antivirus:
    nome: str
    ativo: bool = False
    atualizado: bool = True
    caminho: str = ""


@dataclass
class Servico:
    chave: str
    rotulo: str
    estado: str = ""
    inicializacao: str = ""
    # Campos novos vao no FIM de proposito: inseri-los no meio remapeia
    # todo construtor posicional em silencio. A suite pegou justamente
    # isso quando tentei coloca-los antes de `estado`.
    faz: str = ""
    risco: str = ""

    @property
    def parado(self) -> bool:
        return self.estado.lower() != "running"

    @property
    def suspeito(self) -> bool:
        """Se o estado deste servico merece explicacao.

        Parado NAO e sinonimo de problema: no Windows 10 e 11 o Windows
        Update e o BITS ficam com inicializacao Manual e sobem sob
        demanda - marca-los seria alarme falso em toda maquina saudavel.

        O que de fato indica interferencia e:
            - Desabilitado, que ninguem faz sem querer;
            - Parado apesar de estar como Automatico.
        """
        inicio = self.inicializacao.lower()
        if inicio.startswith("disabled"):
            return True
        return self.parado and inicio.startswith("automatic")

    @property
    def motivo(self) -> str:
        if not self.suspeito:
            return ""
        if self.inicializacao.lower().startswith("disabled"):
            return "desabilitado"
        return "parado apesar de estar como automático"


@dataclass
class Atualizacoes:
    ultima: str = ""
    dias: int | None = None
    total: int = 0
    versao: str = ""
    compilacao: str = ""


@dataclass
class Quadro:
    antivirus: list[Antivirus] = field(default_factory=list)
    servicos: list[Servico] = field(default_factory=list)
    atualizacoes: Atualizacoes = field(default_factory=Atualizacoes)


def _json(consulta: str, tempo_limite: int = 120):
    saida = win.powershell(consulta, tempo_limite=tempo_limite)
    if not saida.ok or not saida.texto.strip():
        return []
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    return [dados] if isinstance(dados, dict) else dados


def antivirus(relatar=lambda _: None) -> list[Antivirus]:
    r"""Antivirus registrados na Central de Seguranca.

    O campo productState e um bitfield, nao um texto - e por isso funciona
    em Windows de qualquer idioma. Bit 0x1000 ligado significa protecao em
    tempo real ativa; bit 0x10 ligado significa assinaturas VENCIDAS.
    """
    relatar("Lendo antivírus registrados...")
    dados = _json(
        r"Get-CimInstance -Namespace root\SecurityCenter2 "
        r"-ClassName AntiVirusProduct -ErrorAction SilentlyContinue "
        r"| Select-Object displayName,productState,pathToSignedProductExe "
        r"| ConvertTo-Json -Compress")

    lista = []
    for d in dados:
        estado = int(d.get("productState") or 0)
        lista.append(Antivirus(
            nome=(d.get("displayName") or "?").strip(),
            ativo=bool(estado & 0x1000),
            atualizado=not (estado & 0x10),
            caminho=(d.get("pathToSignedProductExe") or "").strip(),
        ))
    return lista


def servicos(relatar=lambda _: None) -> list[Servico]:
    relatar("Conferindo serviços essenciais...")
    nomes = ",".join(f"'{n}'" for n in ESSENCIAIS)
    dados = _json(
        f"Get-Service -Name {nomes} -ErrorAction SilentlyContinue "
        "| Select-Object Name,Status,StartType | ConvertTo-Json -Compress")

    por_nome = {}
    for d in dados:
        por_nome[(d.get("Name") or "").lower()] = d

    lista = []
    for chave, (rotulo, faz, risco) in ESSENCIAIS.items():
        d = por_nome.get(chave.lower())
        if d is None:
            continue
        # Status e StartType chegam como numero em PowerShell 5 e como
        # texto em versoes novas. Normalizar aqui evita ter que adivinhar
        # depois, na tela.
        estado = d.get("Status")
        estado = {1: "Stopped", 4: "Running"}.get(estado, estado)
        inicio = d.get("StartType")
        inicio = {2: "Automatic", 3: "Manual", 4: "Disabled"}.get(inicio, inicio)
        lista.append(Servico(chave, rotulo, faz=faz, risco=risco,
                             estado=str(estado or ""),
                             inicializacao=str(inicio or "")))
    return lista


def atualizacoes(relatar=lambda _: None) -> Atualizacoes:
    """Idade da ultima correcao instalada e versao do Windows.

    Nao ha tabela de fim de suporte no codigo de proposito: essas datas
    mudam e envelheceriam aqui dentro sem ninguem perceber. O que o app
    afirma e o que ele mede - quando entrou a ultima correcao.
    """
    relatar("Lendo histórico de atualizações...")
    a = Atualizacoes()

    so = _json("Get-CimInstance Win32_OperatingSystem "
               "| Select-Object Caption,Version,BuildNumber "
               "| ConvertTo-Json -Compress")
    if so:
        a.versao = (so[0].get("Caption") or "").strip()
        a.compilacao = f"{so[0].get('Version', '')} ({so[0].get('BuildNumber', '')})"

    correcoes = _json(
        "Get-CimInstance Win32_QuickFixEngineering "
        "| Where-Object { $_.InstalledOn } "
        "| Sort-Object InstalledOn "
        "| Select-Object HotFixID,@{n='Quando';e={"
        "$_.InstalledOn.ToString('yyyy-MM-dd')}} | ConvertTo-Json -Compress",
        tempo_limite=180)
    a.total = len(correcoes)
    if correcoes:
        a.ultima = (correcoes[-1].get("Quando") or "").strip()
        try:
            quando = datetime.strptime(a.ultima, "%Y-%m-%d")
            a.dias = (datetime.now() - quando).days
        except ValueError:
            a.dias = None
    return a


def levantar(relatar=lambda _: None, percentual=lambda _: None) -> Quadro:
    q = Quadro()
    percentual(10)
    q.antivirus = antivirus(relatar)
    percentual(45)
    q.servicos = servicos(relatar)
    percentual(70)
    q.atualizacoes = atualizacoes(relatar)
    percentual(100)
    return q
