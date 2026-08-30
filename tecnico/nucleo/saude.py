"""Saude do hardware e sinais de problema que o usuario nao ve.

Tres leituras que separam "PC lento" de "PC com defeito":

  SMART       - o disco esta morrendo?
  Eventos     - a maquina ja travou, e quando?
  Dispositivos- algo esta sem driver ou com falha?

Tudo somente leitura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import win
from .sistema import Grupo, Item


@dataclass
class Disco:
    modelo: str
    tipo: str = ""
    saude: str = ""
    tamanho: int = 0
    horas_ligado: int | None = None
    desgaste: int | None = None        # % consumido (SSD)
    temperatura: int | None = None
    erros_leitura: int | None = None

    @property
    def alerta(self) -> str:
        if self.saude and self.saude.lower() not in ("healthy", "saudável", "ok"):
            return "erro"
        # 90% de desgaste num SSD ja e hora de programar a troca, nao de
        # esperar parar.
        if self.desgaste is not None and self.desgaste >= 90:
            return "erro"
        if self.desgaste is not None and self.desgaste >= 70:
            return "atencao"
        if self.erros_leitura:
            return "atencao"
        # 45 mil horas sao ~5 anos ligado direto; disco mecanico nessa
        # faixa merece ser vigiado.
        if self.horas_ligado and self.horas_ligado > 45000:
            return "atencao"
        return ""


@dataclass
class Evento:
    quando: str
    origem: str
    identificador: int
    descricao: str
    gravidade: str = "atencao"


@dataclass
class Dispositivo:
    nome: str
    classe: str
    situacao: str
    problema: str = ""


def discos(relatar=lambda _: None) -> list[Disco]:
    """Le SMART pelo subsistema de armazenamento do Windows.

    Get-PhysicalDisk + Get-StorageReliabilityCounter em vez de ler SMART
    cru: o driver ja normaliza os atributos, que variam de fabricante
    para fabricante e sao um campo minado quando lidos direto.
    """
    relatar("Lendo saúde dos discos...")
    script = (
        "Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object { "
        "$c = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{ "
        "modelo=$_.FriendlyName; tipo=$_.MediaType; saude=$_.HealthStatus; "
        "tamanho=$_.Size; horas=$c.PowerOnHours; desgaste=$c.Wear; "
        "temp=$c.Temperature; erros=$c.ReadErrorsTotal } } | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    saida = win.powershell(script, 60)
    if not saida.texto.strip():
        return []

    import json
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    def inteiro(v):
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    resultado = []
    for d in dados:
        resultado.append(Disco(
            modelo=str(d.get("modelo") or "—").strip(),
            tipo=str(d.get("tipo") or "").strip(),
            saude=str(d.get("saude") or "").strip(),
            tamanho=inteiro(d.get("tamanho")) or 0,
            horas_ligado=inteiro(d.get("horas")),
            desgaste=inteiro(d.get("desgaste")),
            temperatura=inteiro(d.get("temp")),
            erros_leitura=inteiro(d.get("erros")),
        ))
    return resultado


# Eventos que importam num atendimento. Fora desta lista o log do Windows
# vira ruido: ha erro de rotina o tempo todo em maquina saudavel.
EVENTOS_CHAVE = {
    41: ("Desligamento inesperado", "erro"),
    1001: ("Tela azul (BugCheck)", "erro"),
    6008: ("Encerramento inesperado", "erro"),
    7: ("Erro de bloco no disco", "erro"),
    11: ("Erro de controladora de disco", "erro"),
    51: ("Erro de paginação no disco", "atencao"),
    98: ("Erro de volume", "atencao"),
    129: ("Reset de controladora", "atencao"),
}


def eventos(dias: int = 30, relatar=lambda _: None) -> list[Evento]:
    relatar(f"Procurando falhas nos últimos {dias} dias...")
    ids = ",".join(str(i) for i in EVENTOS_CHAVE)
    script = (
        f"$inicio = (Get-Date).AddDays(-{dias}); "
        f"Get-WinEvent -FilterHashtable @{{LogName='System'; "
        f"ID={ids}; StartTime=$inicio}} -MaxEvents 40 "
        f"-ErrorAction SilentlyContinue | "
        f"Select-Object @{{n='quando';e={{$_.TimeCreated.ToString('dd/MM/yyyy HH:mm')}}}}, "
        f"@{{n='origem';e={{$_.ProviderName}}}}, Id | "
        f"ConvertTo-Json -Compress -Depth 3"
    )
    saida = win.powershell(script, 90)
    if not saida.texto.strip():
        return []

    import json
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    lista = []
    for e in dados:
        ident = int(e.get("Id", 0) or 0)
        descricao, gravidade = EVENTOS_CHAVE.get(ident, ("Evento do sistema", "atencao"))
        lista.append(Evento(
            quando=str(e.get("quando") or ""),
            origem=str(e.get("origem") or ""),
            identificador=ident,
            descricao=descricao,
            gravidade=gravidade,
        ))
    return lista


def dispositivos_com_problema(relatar=lambda _: None) -> list[Dispositivo]:
    relatar("Verificando dispositivos...")
    script = (
        "Get-PnpDevice -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Status -ne 'OK' -and $_.Status -ne 'Unknown' } | "
        "Select-Object FriendlyName, Class, Status, ProblemDescription | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    saida = win.powershell(script, 60)
    if not saida.texto.strip():
        return []

    import json
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    lista = []
    for d in dados:
        nome = str(d.get("FriendlyName") or "").strip()
        if not nome:
            continue
        lista.append(Dispositivo(
            nome=nome,
            classe=str(d.get("Class") or "").strip(),
            situacao=str(d.get("Status") or "").strip(),
            problema=str(d.get("ProblemDescription") or "").strip(),
        ))
    return lista


def como_grupos(relatar=lambda _: None, percentual=lambda _: None,
                cancelado=lambda: False) -> list[Grupo]:
    """Converte as tres leituras em grupos para a tela de diagnostico."""
    from . import admin
    from .win import formatar_bytes

    grupos: list[Grupo] = []

    # ---------- discos ----------
    percentual(10)
    lista = discos(relatar)
    if lista:
        g = Grupo("Saúde dos discos")
        for d in lista:
            detalhes = [f"{d.tipo or '—'} · {formatar_bytes(d.tamanho)}",
                        f"estado {d.saude or '—'}"]
            if d.horas_ligado is not None:
                anos = d.horas_ligado / 8760
                detalhes.append(f"{d.horas_ligado}h ligado (~{anos:.1f} anos)")
            if d.desgaste is not None:
                detalhes.append(f"desgaste {d.desgaste}%")
            if d.temperatura:
                detalhes.append(f"{d.temperatura} °C")
            if d.erros_leitura:
                detalhes.append(f"{d.erros_leitura} erros de leitura")
            g.itens.append(Item(d.modelo, " · ".join(detalhes), d.alerta))

        # Sem elevacao o Windows devolve os contadores vazios. Dizer isso e
        # melhor que exibir um disco "sem dados" e deixar o tecnico achar
        # que o disco nao responde.
        sem_contadores = all(d.horas_ligado is None for d in lista)
        if sem_contadores and not admin.e_administrador():
            g.itens.append(Item(
                "Contadores detalhados",
                "indisponíveis — reabra como administrador para ver horas, "
                "desgaste e temperatura",
                "atencao"))
        grupos.append(g)

    if cancelado():
        return grupos

    # ---------- eventos ----------
    percentual(50)
    evs = eventos(30, relatar)
    g = Grupo("Falhas registradas (30 dias)")
    if not evs:
        g.itens.append(Item("Nenhuma falha crítica", "sistema sem registros"))
    else:
        # Agrupa por tipo: 40 linhas iguais nao ajudam ninguem; o que
        # importa e "isto aconteceu 12 vezes, a ultima ontem".
        from collections import Counter
        contagem = Counter((e.identificador, e.descricao, e.gravidade)
                           for e in evs)
        mais_recente: dict[int, str] = {}
        for e in evs:
            mais_recente.setdefault(e.identificador, e.quando)

        for (ident, descricao, gravidade), n in contagem.most_common():
            g.itens.append(Item(
                f"{descricao} (ID {ident})",
                f"{n}x · último em {mais_recente.get(ident, '—')}",
                gravidade))
    grupos.append(g)

    if cancelado():
        return grupos

    # ---------- dispositivos ----------
    percentual(85)
    ds = dispositivos_com_problema(relatar)
    g = Grupo("Dispositivos")
    if not ds:
        g.itens.append(Item("Nenhum problema", "todos operando normalmente"))
    else:
        for d in ds:
            g.itens.append(Item(
                d.nome,
                f"{d.classe or '—'} · {d.situacao}"
                + (f" · {d.problema}" if d.problema else ""),
                "erro"))
    grupos.append(g)

    percentual(100)
    relatar("Verificação de saúde concluída.")
    return grupos


# ---------------------------------------------------------------------
# BATERIA
# ---------------------------------------------------------------------
CONSULTA_BATERIA = r"""
$e = @{}
try { $e.projeto = (Get-CimInstance -Namespace root\wmi -ClassName BatteryStaticData -ErrorAction Stop).DesignedCapacity } catch { $e.projeto = $null }
try { $e.cheia = (Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity -ErrorAction Stop).FullChargedCapacity } catch { $e.cheia = $null }
try { $e.ciclos = (Get-CimInstance -Namespace root\wmi -ClassName BatteryCycleCount -ErrorAction Stop).CycleCount } catch { $e.ciclos = $null }
$e | ConvertTo-Json -Compress
"""


@dataclass
class Bateria:
    presente: bool = False
    projeto_mwh: int = 0
    cheia_mwh: int = 0
    ciclos: int | None = None
    carga_pct: int = 0
    na_tomada: bool = False

    @property
    def saude_pct(self) -> int:
        """Capacidade atual sobre a de fabrica.

        E o numero que interessa, e nao a porcentagem de carga: uma
        bateria pode marcar 100% carregada e ainda assim guardar so um
        terco do que guardava nova.
        """
        if not (self.projeto_mwh and self.cheia_mwh):
            return 0
        return round(self.cheia_mwh / self.projeto_mwh * 100)

    @property
    def alerta(self) -> str:
        saude = self.saude_pct
        if not saude:
            return ""
        if saude < 50:
            return "erro"
        if saude < 80:
            return "atencao"
        return ""


def bateria() -> Bateria:
    """Desgaste da bateria, ou `presente=False` em desktop."""
    import json

    import psutil

    b = Bateria()
    estado = psutil.sensors_battery()
    if estado is None:
        return b

    b.presente = True
    b.carga_pct = int(estado.percent)
    b.na_tomada = bool(estado.power_plugged)

    saida = win.powershell(CONSULTA_BATERIA, tempo_limite=120)
    if not saida.ok or not saida.texto.strip():
        return b
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return b

    def inteiro(valor):
        # As classes WMI devolvem lista quando ha mais de uma bateria
        # (notebook com duas celulas). Somar e o comportamento certo.
        if isinstance(valor, list):
            return sum(int(v) for v in valor if v)
        return int(valor) if valor else 0

    b.projeto_mwh = inteiro(dados.get("projeto"))
    b.cheia_mwh = inteiro(dados.get("cheia"))
    ciclos = inteiro(dados.get("ciclos"))
    b.ciclos = ciclos or None
    return b
