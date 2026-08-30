"""Varredura completa e sugestoes de otimizacao.

Junta o que os outros modulos ja sabem e transforma em recomendacao
acionavel. Nada aqui altera a maquina: so le e opina.

As regras de corte sao explicitas de proposito. "Disco cheio" nao e
opiniao - abaixo de 10% livre o Windows comeca a falhar em atualizacao e
a nao conseguir crescer o arquivo de paginacao. Cada limiar abaixo tem um
motivo escrito, para quem mexer depois saber o que esta mudando.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psutil

from . import (
    desempenho,
    licenca,
    limpeza,
    persistencia,
    programas,
    rede,
    saude,
    sistema,
    wifi,
)
from .win import formatar_bytes


@dataclass
class Sugestao:
    titulo: str
    detalhe: str
    gravidade: str          # "alta" | "media" | "baixa"
    painel: str = ""        # para onde levar o tecnico


@dataclass
class Varredura:
    grupos: list[sistema.Grupo] = field(default_factory=list)
    discos: list = field(default_factory=list)
    eventos: list = field(default_factory=list)
    dispositivos: list = field(default_factory=list)
    rede: rede.Diagnostico | None = None
    achados: list[limpeza.Achado] = field(default_factory=list)
    inicializacao: list = field(default_factory=list)
    licencas: list = field(default_factory=list)
    chave_bios: str = ""
    tarefas: list = field(default_factory=list)
    extensoes: list = field(default_factory=list)
    bateria: object | None = None
    medida_disco: object | None = None
    redes_wifi: list = field(default_factory=list)
    sugestoes: list[Sugestao] = field(default_factory=list)


def _analisar(v: Varredura) -> list[Sugestao]:
    sugestoes: list[Sugestao] = []

    # --- saude fisica do disco ---
    # Vem antes de tudo: espaco cheio se resolve limpando, disco morrendo
    # nao. Se ha risco de perda de dados, e essa a primeira conversa.
    for d in v.discos:
        if d.alerta == "erro":
            sugestoes.append(Sugestao(
                f"Disco em risco: {d.modelo}",
                f"Estado relatado: {d.saude or 'desconhecido'}"
                + (f", desgaste {d.desgaste}%" if d.desgaste is not None else "")
                + ". Faça backup antes de qualquer outra intervenção.",
                "alta", "diagnostico"))
        elif d.alerta == "atencao":
            sugestoes.append(Sugestao(
                f"Disco pedindo atenção: {d.modelo}",
                "Contadores fora do confortável. Programe a substituição.",
                "media", "diagnostico"))

    # --- falhas registradas ---
    graves = [e for e in v.eventos if e.gravidade == "erro"]
    if graves:
        from collections import Counter
        tipo = Counter(e.descricao for e in graves).most_common(1)[0]
        # A verificacao do evento mais frequente vai junto: mandar o
        # tecnico "ver em Diagnostico" sem dizer o que procurar so
        # transfere a duvida de tela.
        onde_olhar = ""
        for e in graves:
            if e.descricao == tipo[0] and e.verificar:
                onde_olhar = f" Verificar: {e.verificar}"
                break
        sugestoes.append(Sugestao(
            "Falhas registradas no sistema",
            f"{len(graves)} evento(s) crítico(s) em 30 dias. Mais frequente: "
            f"{tipo[0]} ({tipo[1]}x).{onde_olhar}",
            "alta", "diagnostico"))

    if v.dispositivos:
        sugestoes.append(Sugestao(
            "Dispositivos com problema",
            f"{len(v.dispositivos)} item(ns) sem driver ou com falha: "
            + ", ".join(d.nome for d in v.dispositivos[:3]) + ".",
            "media", "diagnostico"))

    # --- disco ---
    for part in psutil.disk_partitions(all=False):
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        livre = 100 - uso.percent
        # Abaixo de 10% o Windows degrada de verdade: Update falha e o
        # arquivo de paginacao para de crescer.
        if livre < 10:
            sugestoes.append(Sugestao(
                f"Disco {part.device} quase cheio",
                f"Apenas {livre:.0f}% livres ({formatar_bytes(uso.free)}). "
                "Abaixo de 10% o Windows falha em atualizar e o arquivo de "
                "paginação para de crescer.",
                "alta", "limpeza"))
        elif livre < 20:
            sugestoes.append(Sugestao(
                f"Disco {part.device} com pouco espaço",
                f"{livre:.0f}% livres. Ainda funciona, mas convém liberar.",
                "media", "limpeza"))

    # --- lixo acumulado ---
    total_lixo = sum(a.bytes_total for a in v.achados)
    # 1 GB e o ponto em que a limpeza compensa o tempo do atendimento.
    if total_lixo > 1024 ** 3:
        sugestoes.append(Sugestao(
            "Volume alto de temporários",
            f"{formatar_bytes(total_lixo)} podem ser liberados sem risco.",
            "media", "limpeza"))

    # --- memoria ---
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        sugestoes.append(Sugestao(
            "Memória sob pressão",
            f"{mem.percent:.0f}% em uso. Verifique processos e itens de "
            "inicialização.",
            "media", "programas"))

    # --- inicializacao ---
    # Acima de 8 itens o tempo de boot ja e perceptivel para o usuario.
    if len(v.inicializacao) > 8:
        sugestoes.append(Sugestao(
            "Muitos programas na inicialização",
            f"{len(v.inicializacao)} itens sobem com o Windows. Cada um "
            "atrasa o boot e consome memória em segundo plano.",
            "media", "programas"))

    # --- rede ---
    if v.rede and v.rede.situacao_geral == "erro":
        falhas = [t.rotulo for t in v.rede.testes if t.situacao == "erro"]
        sugestoes.append(Sugestao(
            "Falha na rede",
            "Não passou em: " + ", ".join(falhas) + ".",
            "alta", "rede"))
    elif v.rede and v.rede.situacao_geral == "atencao":
        sugestoes.append(Sugestao(
            "Rede instável",
            "Há perda de pacotes ou latência alta. Verifique cabo, "
            "Wi-Fi e o roteador.",
            "media", "rede"))

    # --- tempo ligado ---
    tempo = (psutil.time.time() - psutil.boot_time()) / 86400
    if tempo > 7:
        sugestoes.append(Sugestao(
            "Máquina sem reiniciar há muito tempo",
            f"{tempo:.0f} dias ligada. Atualizações pendentes e vazamentos "
            "de memória só se resolvem no reinício.",
            "baixa", ""))

    if not sugestoes:
        sugestoes.append(Sugestao(
            "Nenhum problema encontrado",
            "Disco, memória, rede e inicialização dentro do esperado.",
            "baixa", ""))

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    return sorted(sugestoes, key=lambda s: ordem[s.gravidade])


def varrer_tudo(relatar=lambda _: None, percentual=lambda _: None,
                cancelado=lambda: False) -> Varredura:
    v = Varredura()

    etapas = [
        ("Lendo o sistema...", lambda: sistema.coletar()),
        ("Lendo saúde do hardware...", lambda: (
            saude.discos(), saude.eventos(30), saude.dispositivos_com_problema())),
        ("Testando a rede...", lambda: rede.diagnosticar()),
        ("Medindo arquivos temporários...", lambda: limpeza.varrer()),
        ("Lendo a inicialização...", lambda: programas.listar_inicializacao()),
        ("Lendo licenciamento...", lambda: licenca.resumo()),
        ("Procurando persistência...", lambda: (
            persistencia.tarefas(), persistencia.extensoes())),
        ("Varrendo redes Wi-Fi...", lambda: wifi.redes()),
        # O teste de disco entra na varredura e nao num botao a
        # parte: sem ele, apontar_disco nunca tinha o que analisar
        # e a recomendacao de troca por SSD jamais aparecia.
        ("Medindo o disco...", lambda: desempenho.medir()),
    ]

    resultados = []
    for i, (mensagem, funcao) in enumerate(etapas):
        if cancelado():
            return v
        relatar(mensagem)
        percentual(int(i / len(etapas) * 90))
        resultados.append(funcao())

    (v.grupos, fisico, v.rede, v.achados, v.inicializacao,
     licencas, persistente, redes, v.medida_disco) = resultados
    v.redes_wifi = redes[0] if redes else []
    v.discos, v.eventos, v.dispositivos = fisico
    v.licencas, v.chave_bios = licencas
    v.tarefas, v.extensoes = persistente
    v.bateria = saude.bateria()

    relatar("Analisando...")
    percentual(95)
    v.sugestoes = _analisar(v)
    v.sugestoes += apontar_licenca(v.licencas, v.chave_bios)
    v.sugestoes += apontar_bateria(v.bateria)
    v.sugestoes += apontar_persistencia(v.tarefas, v.extensoes)
    v.sugestoes += apontar_disco(v.medida_disco)
    v.sugestoes += apontar_wifi(v.redes_wifi,
                                wifi.canais_disputados(v.redes_wifi))
    # Ordem por gravidade: o tecnico le de cima para baixo e o
    # que exige acao tem que estar no topo, venha de onde vier.
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    v.sugestoes.sort(key=lambda x: ordem.get(x.gravidade, 3))

    percentual(100)
    graves = sum(1 for s in v.sugestoes if s.gravidade == "alta")
    relatar(f"Varredura concluída — {len(v.sugestoes)} apontamento(s), "
            f"{graves} de gravidade alta.")
    return v


# ---------------------------------------------------------------------
# APONTAMENTOS DOS MODULOS DE LEITURA PROFUNDA
# ---------------------------------------------------------------------
# Estes vivem separados de _analisar porque dependem de coletas mais
# lentas e opcionais. A varredura completa chama todos; o roteiro pode
# pular os que nao rodou.
def apontar_licenca(produtos, chave_bios: str = "") -> list[Sugestao]:
    sugestoes = []
    for p in produtos:
        if p.alerta == "erro":
            sugestoes.append(Sugestao(
                f"Licença não ativa: {p.nome.split(',')[0]}",
                f"{p.situacao} — canal {p.canal or 'desconhecido'}. "
                + (p.observacao or "Verifique antes de entregar a máquina."),
                "alta", "diagnostico"))
        elif p.alerta == "atencao":
            sugestoes.append(Sugestao(
                f"Licença em carência: {p.nome.split(',')[0]}",
                f"{p.situacao}. A ativação vence e volta a pedir chave.",
                "media", "diagnostico"))
    return sugestoes


def apontar_bateria(b) -> list[Sugestao]:
    if not b.presente or not b.saude_pct:
        return []
    if b.alerta == "erro":
        return [Sugestao(
            "Bateria no fim da vida",
            f"Guarda {b.saude_pct}% da capacidade de fábrica "
            f"({b.cheia_mwh:,} de {b.projeto_mwh:,} mWh)".replace(",", ".")
            + ". Autonomia não volta com software; é troca de peça.",
            "alta", "diagnostico")]
    if b.alerta == "atencao":
        return [Sugestao(
            "Bateria desgastada",
            f"Guarda {b.saude_pct}% da capacidade original. "
            "Avise o cliente antes que ele reclame da autonomia.",
            "media", "diagnostico")]
    return []


def apontar_persistencia(tarefas, extensoes) -> list[Sugestao]:
    sugestoes = []
    suspeitas = [t for t in tarefas if t.suspeita]
    if suspeitas:
        sugestoes.append(Sugestao(
            "Tarefas agendadas suspeitas",
            f"{len(suspeitas)} tarefa(s) com indício: "
            + "; ".join(f"{t.nome} ({t.motivo.rstrip('.')})"
                        for t in suspeitas[:2])
            + ". Confira antes de descartar.",
            "media", "programas"))
    # Extensao nao tem como ser julgada por heuristica honesta, entao o
    # apontamento so aparece quando o numero por si ja pede revisao.
    if len(extensoes) >= 12:
        sugestoes.append(Sugestao(
            "Muitas extensões de navegador",
            f"{len(extensoes)} instaladas. Cada uma lê as páginas visitadas "
            "e pesa na memória. Vale revisar uma a uma.",
            "baixa", "programas"))
    return sugestoes


def apontar_wifi(redes, disputa: dict) -> list[Sugestao]:
    congestionados = {c: n for c, n in disputa.items() if n >= 4}
    if not congestionados:
        return []
    pior = max(congestionados.items(), key=lambda p: p[1])
    return [Sugestao(
        "Canal de Wi-Fi congestionado",
        f"{pior[1]} redes dividem o canal {pior[0]}. Trocar o canal do "
        "roteador costuma resolver lentidão que o teste de velocidade "
        "sozinho não explica.",
        "media", "rede")]


def apontar_disco(medida) -> list[Sugestao]:
    """Desempenho medido vira recomendacao de upgrade.

    O cruzamento que mais vende: sistema moderno em disco mecanico. O
    numero da leitura aleatoria e a prova anexa, e nao opiniao.
    """
    if medida is None or medida.erro or not medida.leitura_aleatoria:
        return []

    mecanico = (medida.tipo or "").upper().startswith("HDD")
    if medida.leitura_aleatoria < 1.5:
        return [Sugestao(
            "Disco muito lento" + (" — HD mecânico" if mecanico else ""),
            f"{medida.leitura_aleatoria:.1f} MB/s em leitura aleatória de "
            f"4 KB ({medida.iops:,} IOPS).".replace(",", ".")
            + " Um SSD faz dezenas de vezes isso. Trocar muda a experiência "
              "de uso mais que qualquer outro upgrade.",
            "alta", "diagnostico")]
    if medida.leitura_aleatoria < 5:
        return [Sugestao(
            "Disco abaixo do esperado",
            f"{medida.leitura_aleatoria:.1f} MB/s em leitura aleatória. "
            + ("Compatível com SSD saturado ou de entrada."
               if not mecanico else "Compatível com HD mecânico."),
            "media", "diagnostico")]
    return []
