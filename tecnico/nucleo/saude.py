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
    significado: str = ""
    verificar: str = ""


# Codigos do Gerenciador de Dispositivos (CM_PROB_*). O Windows ja devolve
# uma descricao, mas em ingles e generica: "reinstall the drivers". Aqui a
# traducao vem com a acao que resolve na bancada, e a distincao que
# importa - codigo 43 e hardware relatando defeito, 28 e so driver
# faltando, e a conta do cliente muda conforme.
PROBLEMAS_DE_DISPOSITIVO = {
    1: ("Não configurado corretamente",
        "Instale o driver do fabricante. O genérico do Windows não serviu."),
    3: ("Driver corrompido ou memória insuficiente",
        "Reinstale o driver; se repetir em vários dispositivos, teste a "
        "memória."),
    10: ("Não conseguiu iniciar",
         "Driver errado para o modelo, ou o hardware não responde. Troque o "
         "driver primeiro; persistindo, suspeite da peça."),
    12: ("Sem recursos livres suficientes",
         "Conflito de IRQ ou endereço. Desative um dispositivo que não use "
         "ou mude o slot."),
    14: ("Precisa reiniciar",
         "Só reiniciar a máquina resolve."),
    18: ("Drivers precisam ser reinstalados",
         "Desinstale marcando 'excluir o software do driver' e instale de "
         "novo, do site do fabricante."),
    19: ("Registro danificado",
         "A configuração no registro está incompleta. Desinstale o "
         "dispositivo e deixe o Windows redetectar no boot."),
    22: ("Desativado",
         "Alguém desativou pelo Gerenciador de Dispositivos. Botão direito "
         "e Ativar — se voltar sozinho a desativar, é política de grupo."),
    24: ("Ausente ou com driver incompleto",
         "O dispositivo não está presente ou o driver ficou pela metade. "
         "Confirme se a peça está conectada antes de mexer em software."),
    28: ("Driver não instalado",
         "Falta o driver. É o código clássico de pós-formatação — use a "
         "restauração de drivers na aba Pré-formatação."),
    31: ("Windows não conseguiu carregar o driver",
         "Driver incompatível com a versão do Windows. Procure o driver "
         "específico da build instalada."),
    37: ("Driver retornou falha na inicialização",
         "O driver carregou e recusou o dispositivo. Quase sempre é versão "
         "errada do driver."),
    39: ("Driver corrompido ou ausente",
         "Arquivo do driver danificado. Reinstale; se repetir, rode o SFC."),
    43: ("O próprio hardware relatou defeito",
         "O dispositivo informou falha ao Windows. Este é o código que "
         "aponta a PEÇA, não o software — teste em outra máquina antes de "
         "orçar a troca."),
    45: ("Não conectado agora",
         "Não é defeito: é um dispositivo já usado que não está plugado. "
         "Aparece para pendrive, dock e impressora removidos."),
    52: ("Assinatura do driver não verificada",
         "Driver sem assinatura digital válida. Em Windows 64 bits ele não "
         "carrega sem desativar a verificação — prefira um driver assinado."),
}


@dataclass
class Dispositivo:
    nome: str
    classe: str
    situacao: str
    problema: str = ""
    codigo: int = 0
    significado: str = ""
    resolver: str = ""


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
@dataclass(frozen=True)
class TipoDeEvento:
    """O que o evento significa e o que fazer com ele.

    O ID sozinho nao ajuda ninguem: "Erro de controladora de disco" nao
    diz se o culpado e o cabo, a porta ou o disco - e essa diferenca vale
    a troca de uma peca de dez reais ou de uma de quinhentos. A causa
    provavel e a verificacao ficam aqui, ao lado do numero.
    """
    titulo: str
    gravidade: str
    significado: str
    verificar: str


EVENTOS_CHAVE = {
    41: TipoDeEvento(
        "Desligamento inesperado", "erro",
        "A máquina perdeu energia ou travou por completo, sem passar pelo "
        "desligamento normal do Windows.",
        "Fonte, tomada e temperatura. Se vier junto de tela azul, o "
        "problema é software; sozinho e repetido, quase sempre é fonte."),
    1001: TipoDeEvento(
        "Tela azul (BugCheck)", "erro",
        "O Windows parou com erro fatal e reiniciou. O código do erro fica "
        "no despejo de memória.",
        "Driver instalado nos últimos dias e teste de memória. Estas duas "
        "causas respondem pela maioria."),
    6008: TipoDeEvento(
        "Encerramento sujo", "erro",
        "Registro de que o desligamento anterior não foi concluído. "
        "Costuma acompanhar o evento 41.",
        "Tratar junto com o 41; sozinho, raramente significa algo novo."),
    7: TipoDeEvento(
        "Bloco defeituoso no disco", "erro",
        "O disco tentou ler um setor e não conseguiu. É defeito físico da "
        "mídia, não do sistema de arquivos.",
        "Backup AGORA e SMART. Este evento costuma preceder a perda do "
        "disco em semanas."),
    11: TipoDeEvento(
        "Erro de controladora de disco", "erro",
        "A controladora relatou falha de leitura ou escrita. O culpado "
        "pode ser o cabo, a porta da placa-mãe ou o próprio disco.",
        "Trocar o cabo SATA e a porta antes de condenar o disco — é a "
        "causa mais barata e a mais comum."),
    51: TipoDeEvento(
        "Erro no arquivo de paginação", "atencao",
        "O Windows falhou ao usar o arquivo de paginação. Pode ser disco "
        "com defeito ou disco sem espaço.",
        "Espaço livre em C: e saúde do disco. Abaixo de 10% livres, o "
        "arquivo de paginação sofre."),
    98: TipoDeEvento(
        "Inconsistência no volume", "atencao",
        "O NTFS encontrou estrutura corrompida. Diferente do bloco "
        "defeituoso: aqui o problema é lógico, não físico.",
        "CHKDSK com correção agendada, disponível no painel de Reparo."),
    129: TipoDeEvento(
        "Reset de controladora", "atencao",
        "A controladora não respondeu a tempo e foi reiniciada pelo "
        "driver. Costuma vir de cabo ruim ou economia de energia do link.",
        "Cabo SATA, firmware do SSD e a política de energia do link "
        "(LPM) no plano de energia."),
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
        tipo = EVENTOS_CHAVE.get(ident)
        lista.append(Evento(
            quando=str(e.get("quando") or ""),
            origem=str(e.get("origem") or ""),
            identificador=ident,
            descricao=tipo.titulo if tipo else "Evento do sistema",
            gravidade=tipo.gravidade if tipo else "atencao",
            significado=tipo.significado if tipo else "",
            verificar=tipo.verificar if tipo else "",
        ))
    return lista


def dispositivos_com_problema(relatar=lambda _: None) -> list[Dispositivo]:
    relatar("Verificando dispositivos...")
    script = (
        "Get-PnpDevice -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Status -ne 'OK' -and $_.Status -ne 'Unknown' } | "
        "Select-Object FriendlyName, Class, Status, Problem, "
        "ProblemDescription | "
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
        codigo = int(d.get("Problem") or 0)
        titulo, resolver = PROBLEMAS_DE_DISPOSITIVO.get(codigo, ("", ""))
        lista.append(Dispositivo(
            nome=nome,
            classe=str(d.get("Class") or "").strip(),
            situacao=str(d.get("Status") or "").strip(),
            problema=str(d.get("ProblemDescription") or "").strip(),
            codigo=codigo,
            significado=titulo,
            resolver=resolver,
        ))
    return lista


def _referencia_do_disco(d) -> str:
    """O que os numeros do disco significam para a idade e o tipo dele.

    "8760h ligado" nao diz nada sozinho: e um ano de uso continuo, rotina
    num HD de servidor e muito num notebook domestico. O desgaste tambem
    so tem sentido contra o tempo - 12% em seis meses e outra conversa que
    12% em cinco anos.
    """
    partes = []
    mecanico = (d.tipo or "").upper().startswith("HDD")

    if d.horas_ligado:
        anos = d.horas_ligado / 8760
        if mecanico:
            # HD mecanico tem peca girando; acima de 5 anos a falha deixa
            # de ser azar e vira estatistica.
            if anos >= 5:
                partes.append(f"{anos:.1f} anos ligado — acima da vida útil "
                              "típica de um HD mecânico, programe a troca")
            elif anos >= 3:
                partes.append(f"{anos:.1f} anos ligado — dentro do esperado, "
                              "mas já vale ter backup em dia")
            else:
                partes.append(f"{anos:.1f} anos ligado — disco novo")
        else:
            # SSD nao tem peca movel: horas importam pouco, o que gasta e
            # a escrita, e isso o desgaste mede.
            partes.append(f"{anos:.1f} anos ligado — em SSD as horas pesam "
                          "pouco; o que gasta é a escrita")

    if d.desgaste is not None:
        anos = (d.horas_ligado / 8760) if d.horas_ligado else 0
        if d.desgaste >= 90:
            partes.append(f"{d.desgaste}% consumido — troque agora, o "
                          "controlador pode passar a somente leitura")
        elif d.desgaste >= 70:
            partes.append(f"{d.desgaste}% consumido — programe a troca")
        elif anos and d.desgaste / max(anos, 0.1) > 15:
            partes.append(f"{d.desgaste}% em {anos:.1f} anos — ritmo de "
                          "escrita alto para uso doméstico")
        else:
            partes.append(f"{d.desgaste}% consumido — dentro do normal")

    if d.erros_leitura:
        partes.append(f"{d.erros_leitura} erros de leitura — qualquer número "
                      "acima de zero pede backup imediato")

    return " · ".join(partes)


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
            # A leitura dos numeros vem em linha propria: os contadores
            # crus so ajudam quem ja sabe o que e normal.
            leitura = _referencia_do_disco(d)
            if leitura:
                g.itens.append(Item("", leitura))

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
        g.itens.append(Item(
            "Nenhuma falha crítica",
            "nenhum desligamento inesperado, tela azul ou erro de disco "
            "nos últimos 30 dias"))
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

            # Significado e verificacao entram como linhas proprias, sem
            # rotulo: o numero do evento sozinho nao diz se o culpado e o
            # cabo ou o disco, e essa diferenca decide a peca que se troca.
            tipo = EVENTOS_CHAVE.get(ident)
            if tipo:
                g.itens.append(Item("", f"O que é: {tipo.significado}"))
                g.itens.append(Item("", f"Verificar: {tipo.verificar}"))
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
            resumo = f"{d.classe or '—'} · {d.situacao}"
            if d.codigo:
                resumo += f" · código {d.codigo}"
            if d.significado:
                resumo += f" — {d.significado}"
            g.itens.append(Item(d.nome, resumo, "erro"))
            if d.resolver:
                g.itens.append(Item("", f"Resolver: {d.resolver}"))
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
