import pathlib

# 1. sistema.coletar passa a incluir a saude
p = pathlib.Path("tecnico/nucleo/sistema.py")
s = p.read_text(encoding="utf-8")
antes = s
s = s.replace(
    '''        ("Verificando energia...", _energia),
    ]''',
    '''        ("Verificando energia...", _energia),
    ]''',
)
s = s.replace(
    '''    percentual(100)
    relatar("Diagnóstico concluído.")
    return grupos''',
    '''    # Saude vem por ultimo: e a parte lenta (consulta o log de eventos)
    # e a que mais depende de privilegio.
    if not cancelado():
        from . import saude
        grupos.extend(saude.como_grupos(relatar=relatar))

    percentual(100)
    relatar("Diagnóstico concluído.")
    return grupos''',
)
if s == antes:
    raise SystemExit("sistema.py nao alterado")
p.write_text(s, encoding="utf-8")

# 2. A analise de otimizacao passa a considerar disco doente e falhas
p = pathlib.Path("tecnico/nucleo/otimizacao.py")
s = p.read_text(encoding="utf-8")
s = s.replace(
    "from . import limpeza, programas, rede, sistema",
    "from . import limpeza, programas, rede, saude, sistema",
)
s = s.replace(
    '''@dataclass
class Varredura:
    grupos: list[sistema.Grupo] = field(default_factory=list)''',
    '''@dataclass
class Varredura:
    grupos: list[sistema.Grupo] = field(default_factory=list)
    discos: list = field(default_factory=list)
    eventos: list = field(default_factory=list)
    dispositivos: list = field(default_factory=list)''',
)
s = s.replace(
    '''    # --- disco ---''',
    '''    # --- saude fisica do disco ---
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
        sugestoes.append(Sugestao(
            "Falhas registradas no sistema",
            f"{len(graves)} evento(s) crítico(s) em 30 dias. Mais frequente: "
            f"{tipo[0]} ({tipo[1]}x). Ver detalhes em Diagnóstico.",
            "alta", "diagnostico"))

    if v.dispositivos:
        sugestoes.append(Sugestao(
            "Dispositivos com problema",
            f"{len(v.dispositivos)} item(ns) sem driver ou com falha: "
            + ", ".join(d.nome for d in v.dispositivos[:3]) + ".",
            "media", "diagnostico"))

    # --- disco ---''',
)
s = s.replace(
    '''    etapas = [
        ("Lendo o sistema...", lambda: sistema.coletar()),''',
    '''    etapas = [
        ("Lendo o sistema...", lambda: sistema.coletar()),
        ("Lendo saúde do hardware...", lambda: (
            saude.discos(), saude.eventos(30), saude.dispositivos_com_problema())),''',
)
s = s.replace(
    "    v.grupos, v.rede, v.achados, v.inicializacao = resultados",
    "    v.grupos, fisico, v.rede, v.achados, v.inicializacao = resultados\n"
    "    v.discos, v.eventos, v.dispositivos = fisico",
)
p.write_text(s, encoding="utf-8")
print("saude ligada ao diagnostico e a analise")
