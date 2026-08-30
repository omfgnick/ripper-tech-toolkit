"""Coleta de informacoes da maquina.

Somente leitura. Nada aqui altera o sistema.
"""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import psutil

from . import win


@dataclass
class Item:
    rotulo: str
    valor: str
    alerta: str = ""      # "" | "atencao" | "erro"


@dataclass
class Grupo:
    titulo: str
    itens: list[Item] = field(default_factory=list)


def _tempo_ligado() -> str:
    delta = timedelta(seconds=int(psutil.time.time() - psutil.boot_time()))
    dias = delta.days
    horas, resto = divmod(delta.seconds, 3600)
    minutos = resto // 60
    if dias:
        return f"{dias}d {horas}h {minutos}min"
    return f"{horas}h {minutos}min"


def _identificacao() -> Grupo:
    g = Grupo("Identificação")
    so = win.consultar("Win32_OperatingSystem",
                       ["Caption", "Version", "OSArchitecture", "InstallDate"])
    cs = win.consultar("Win32_ComputerSystem",
                       ["Manufacturer", "Model", "TotalPhysicalMemory"])
    bios = win.consultar("Win32_BIOS", ["SerialNumber", "SMBIOSBIOSVersion"])

    g.itens.append(Item("Nome da máquina", socket.gethostname()))
    if so:
        g.itens.append(Item("Sistema", str(so[0].get("Caption", "—")).strip()))
        g.itens.append(Item("Versão", f'{so[0].get("Version", "—")} '
                                      f'({so[0].get("OSArchitecture", "—")})'))
    if cs:
        fabricante = str(cs[0].get("Manufacturer", "")).strip()
        modelo = str(cs[0].get("Model", "")).strip()
        if fabricante or modelo:
            g.itens.append(Item("Equipamento", f"{fabricante} {modelo}".strip()))
    if bios:
        serie = str(bios[0].get("SerialNumber", "")).strip()
        if serie and serie.lower() not in ("", "default string", "to be filled by o.e.m."):
            g.itens.append(Item("Número de série", serie))
        g.itens.append(Item("BIOS", str(bios[0].get("SMBIOSBIOSVersion", "—")).strip()))

    g.itens.append(Item("Ligada há", _tempo_ligado()))
    return g


def _processador() -> Grupo:
    g = Grupo("Processador e memória")
    cpu = win.consultar("Win32_Processor",
                        ["Name", "NumberOfCores", "NumberOfLogicalProcessors",
                         "MaxClockSpeed"])
    if cpu:
        c = cpu[0]
        g.itens.append(Item("Processador", str(c.get("Name", "—")).strip()))
        g.itens.append(Item(
            "Núcleos",
            f'{c.get("NumberOfCores", "?")} físicos / '
            f'{c.get("NumberOfLogicalProcessors", "?")} lógicos'))
        if c.get("MaxClockSpeed"):
            g.itens.append(Item("Frequência", f'{c["MaxClockSpeed"]} MHz'))
    else:
        g.itens.append(Item("Processador", platform.processor() or "—"))

    uso = psutil.cpu_percent(interval=0.4)
    g.itens.append(Item("Uso de CPU", f"{uso:.0f}%",
                        "atencao" if uso > 85 else ""))

    mem = psutil.virtual_memory()
    g.itens.append(Item("Memória total", win.formatar_bytes(mem.total)))
    g.itens.append(Item(
        "Memória em uso",
        f"{win.formatar_bytes(mem.used)} ({mem.percent:.0f}%)",
        "atencao" if mem.percent > 85 else ""))
    return g


def _discos() -> Grupo:
    g = Grupo("Armazenamento")
    for part in psutil.disk_partitions(all=False):
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            # Leitor de cartao vazio ou unidade de rede caida: nao e erro
            # do app, so nao ha o que medir.
            continue

        # Abaixo de 10% livre o Windows comeca a degradar de verdade -
        # Update falha, arquivo de paginacao nao cresce.
        livre_pct = 100 - uso.percent
        alerta = "erro" if livre_pct < 5 else ("atencao" if livre_pct < 12 else "")
        g.itens.append(Item(
            f"{part.device} ({part.fstype or '—'})",
            f"{win.formatar_bytes(uso.free)} livres de "
            f"{win.formatar_bytes(uso.total)} ({livre_pct:.0f}% livre)",
            alerta))

    for d in win.consultar("Win32_DiskDrive", ["Model", "Size", "MediaType"]):
        modelo = str(d.get("Model", "")).strip()
        if modelo:
            g.itens.append(Item("Unidade física", 
                                f'{modelo} — {win.formatar_bytes(d.get("Size"))}'))
    return g


def _video() -> Grupo:
    g = Grupo("Vídeo")
    for v in win.consultar("Win32_VideoController",
                           ["Name", "AdapterRAM", "DriverVersion"]):
        nome = str(v.get("Name", "")).strip()
        if not nome:
            continue
        g.itens.append(Item(nome, f'Driver {v.get("DriverVersion", "—")}'))
    if not g.itens:
        g.itens.append(Item("Adaptador", "não identificado"))
    return g


def _energia() -> Grupo | None:
    from . import saude

    b = saude.bateria()
    if not b.presente:
        return None

    g = Grupo("Energia")
    g.itens.append(Item("Carga", f"{b.carga_pct}%",
                        "atencao" if b.carga_pct < 20 and not b.na_tomada else ""))
    g.itens.append(Item("Na tomada", "sim" if b.na_tomada else "não"))

    if b.saude_pct:
        # A saude e o numero que decide troca de bateria; a carga so diz
        # quanto falta para acabar hoje.
        g.itens.append(Item(
            "Saúde da bateria",
            f"{b.saude_pct}% da capacidade original "
            f"({b.cheia_mwh:,} de {b.projeto_mwh:,} mWh)".replace(",", "."),
            b.alerta))
    if b.ciclos:
        g.itens.append(Item("Ciclos de carga", str(b.ciclos)))

    bat = psutil.sensors_battery()
    if bat and bat.secsleft not in (psutil.POWER_TIME_UNLIMITED,
                                    psutil.POWER_TIME_UNKNOWN):
        g.itens.append(Item("Autonomia estimada",
                            str(timedelta(seconds=int(bat.secsleft)))))
    return g


def _licenca() -> Grupo | None:
    """Ativacao do Windows e do Office, e a chave gravada na BIOS."""
    from . import licenca

    produtos, chave = licenca.resumo()
    if not produtos and not chave:
        return None

    g = Grupo("Licenciamento")
    for p in produtos:
        valor = p.situacao
        if p.canal:
            valor += f" — canal {p.canal}"
        if p.chave_parcial:
            valor += f" (final {p.chave_parcial})"
        g.itens.append(Item(p.nome, valor, p.alerta))
        if p.observacao:
            g.itens.append(Item("", p.observacao))

    # Chave OEM completa: e um segredo do cliente, mas e exatamente o que
    # o tecnico precisa anotar antes de formatar.
    g.itens.append(Item("Chave OEM na BIOS", chave or "nenhuma (sem licença de fábrica)"))
    return g


def _seguranca() -> Grupo | None:
    """Antivirus, servicos essenciais e idade das atualizacoes."""
    from . import seguranca

    q = seguranca.levantar()
    if not (q.antivirus or q.servicos):
        return None

    g = Grupo("Segurança e serviços")

    if not q.antivirus:
        g.itens.append(Item("Antivírus", "nenhum registrado", "erro"))
    for a in q.antivirus:
        estado = "ativo" if a.ativo else "instalado, mas desligado"
        if not a.atualizado:
            estado += " — assinaturas vencidas"
        g.itens.append(Item(a.nome, estado,
                            "" if a.ativo and a.atualizado else "erro"))
    # Dois ou mais em tempo real disputam os mesmos arquivos e derrubam o
    # desempenho; e a causa que o cliente nunca associa sozinho.
    ativos = [a for a in q.antivirus if a.ativo]
    if len(ativos) > 1:
        g.itens.append(Item(
            "Conflito de antivírus",
            f"{len(ativos)} em tempo real ao mesmo tempo", "erro"))

    suspeitos = [s for s in q.servicos if s.suspeito]
    if suspeitos:
        for s in suspeitos:
            g.itens.append(Item(s.rotulo, s.motivo, "erro"))
    else:
        g.itens.append(Item("Serviços essenciais",
                            f"{len(q.servicos)} conferidos, nenhum alterado"))

    u = q.atualizacoes
    if u.ultima:
        alerta = "atencao" if (u.dias or 0) > 60 else ""
        g.itens.append(Item(
            "Última atualização",
            f"{u.ultima}" + (f" ({u.dias} dias atrás)" if u.dias is not None
                             else ""), alerta))
    if u.compilacao:
        g.itens.append(Item("Compilação do Windows", u.compilacao))
    return g


def _impressoras() -> Grupo | None:
    """Impressoras e fila. O reparo do spooler vive no painel de Reparo."""
    from . import impressoras

    lista = impressoras.listar()
    if not lista:
        return None

    g = Grupo("Impressoras")
    for imp in lista:
        detalhes = []
        if imp.padrao:
            detalhes.append("padrão")
        if imp.offline:
            detalhes.append("OFFLINE")
        if imp.fila:
            detalhes.append(f"{len(imp.fila)} na fila")
        alerta = "erro" if imp.travada else ("atencao" if imp.offline else "")
        g.itens.append(Item(imp.nome, ", ".join(detalhes) or "pronta", alerta))

        for t in imp.fila:
            if t.problema:
                g.itens.append(Item(
                    "", f"travado: {t.documento} ({t.estado})", "erro"))
    return g


def _inventario() -> Grupo | None:
    """Slots livres, tipo de memoria e oportunidades de upgrade."""
    from . import inventario

    inv = inventario.levantar()
    m = inv.memoria
    if not m.slots_totais and not inv.oportunidades:
        return None

    g = Grupo("Espaço para upgrade")
    if m.slots_totais:
        g.itens.append(Item(
            "Slots de memória",
            f"{m.slots_usados} de {m.slots_totais} ocupados"
            + (f" · {m.slots_livres} livre(s)" if m.slots_livres else "")))
        if m.tipo:
            g.itens.append(Item("Tipo instalado", m.tipo + (
                f" · {m.pentes[0].velocidade} MHz"
                if m.pentes and m.pentes[0].velocidade else "")))
        if m.maximo_bytes:
            g.itens.append(Item("Máximo da placa",
                                win.formatar_bytes(m.maximo_bytes)))
    # Oportunidade e frase de venda, nao alerta: marcar como atencao faria
    # o relatorio parecer que ha algo errado com a maquina.
    for texto in inv.oportunidades:
        g.itens.append(Item("Oportunidade", texto))
    return g


def coletar(relatar=lambda _: None, percentual=lambda _: None,
            cancelado=lambda: False) -> list[Grupo]:
    """Monta o diagnostico completo. Assinatura compativel com Tarefa."""
    etapas = [
        ("Identificando o sistema...", _identificacao),
        ("Lendo processador e memória...", _processador),
        ("Medindo armazenamento...", _discos),
        ("Consultando vídeo...", _video),
        ("Verificando energia...", _energia),
        ("Lendo licenciamento...", _licenca),
        ("Conferindo segurança...", _seguranca),
        ("Lendo impressoras...", _impressoras),
        ("Avaliando upgrade...", _inventario),
    ]

    grupos: list[Grupo] = []
    for i, (mensagem, funcao) in enumerate(etapas):
        if cancelado():
            break
        relatar(mensagem)
        percentual(int(i / len(etapas) * 100))
        resultado = funcao()
        if resultado is not None:
            grupos.append(resultado)

    # Saude vem por ultimo: e a parte lenta (consulta o log de eventos)
    # e a que mais depende de privilegio.
    if not cancelado():
        from . import saude
        grupos.extend(saude.como_grupos(relatar=relatar))

    percentual(100)
    relatar("Diagnóstico concluído.")
    return grupos


def resumo_data() -> str:
    return datetime.now().strftime("%d/%m/%Y às %H:%M")
