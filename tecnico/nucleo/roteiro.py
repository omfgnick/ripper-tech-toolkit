"""Roteiro de atendimento: a sequencia inteira num clique.

O tecnico faz quase sempre a mesma ordem de coisas, e a parte cansativa e
lembrar de todas em cada maquina - principalmente de marcar o estado
inicial ANTES de limpar, que e o que da a prova do servico depois.

O roteiro executa tudo em uma tarefa so, em ordem fixa, e termina no PDF.

ETAPAS QUE ALTERAM A MAQUINA SAO OPCIONAIS
    Limpeza e reparo vem desmarcados. Um roteiro que apaga arquivo sem o
    tecnico ter pedido explicitamente seria armadilha, por mais comodo que
    fosse. As etapas de leitura vem marcadas porque nao custam nada.

ORDEM NAO E NEGOCIAVEL
    O estado inicial e medido antes de qualquer alteracao e o final depois
    de todas. Inverter isso produziria um relatorio que mostra zero de
    ganho - e foi por isso que a ordem virou codigo, e nao instrucao.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import (
    desempenho,
    entrega,
    historico,
    limpeza,
    otimizacao,
    pdf,
    reparo,
)


@dataclass
class Etapa:
    chave: str
    titulo: str
    descricao: str
    altera: bool = False
    padrao: bool = True
    marcada: bool = True


def etapas() -> list[Etapa]:
    return [
        Etapa("antes", "Marcar estado inicial",
              "Fotografa disco, lixo, inicialização e memória."),
        Etapa("diagnostico", "Varredura completa",
              "Sistema, saúde do hardware, rede, temporários e inicialização."),
        Etapa("limpeza", "Limpar temporários",
              "Apaga o que foi encontrado na varredura.",
              altera=True, padrao=False, marcada=False),
        Etapa("sfc", "Reparar arquivos do sistema (SFC)",
              "Demorado. Cria ponto de restauração antes.",
              altera=True, padrao=False, marcada=False),
        Etapa("depois", "Marcar estado final",
              "Fecha a comparação antes/depois que entra no PDF."),
        # Depois do fechamento de proposito: o teste escreve e le 192 MB,
        # o que move o uso de memoria. Rodando antes do "depois" ele
        # sujava a comparacao com uma piora causada pela propria medicao.
        Etapa("disco", "Medir velocidade do disco",
              "Leitura e escrita sem cache. Cerca de meio minuto."),
        # O checklist e o fecho do atendimento e precisa vir antes do PDF,
        # que o inclui como ultima secao. O roteiro foi escrito antes da
        # tela de Entrega existir e por isso nao o tinha.
        Etapa("entrega", "Conferir a entrega",
              "Roda as verificações automáticas do checklist: áudio, rede, "
              "Wi-Fi, câmera e bateria."),
        Etapa("pdf", "Gerar o relatório em PDF",
              "Junta tudo num documento para entregar ao cliente."),
    ]


@dataclass
class Resultado:
    concluidas: list[str] = field(default_factory=list)
    puladas: list[tuple[str, str]] = field(default_factory=list)
    varredura: otimizacao.Varredura | None = None
    medida_disco: desempenho.Medida | None = None
    mudancas: list = field(default_factory=list)
    caminho_pdf: str = ""
    liberado: int = 0
    antes: historico.Instantaneo | None = None
    checklist: list = field(default_factory=list)


def executar(marcadas: set[str], destino_pdf: str = "",
             relatar=lambda _: None, percentual=lambda _: None,
             cancelado=lambda: False) -> Resultado:
    """Roda as etapas marcadas, na ordem fixa de `etapas()`."""
    lista = [e for e in etapas() if e.chave in marcadas]
    r = Resultado()
    if not lista:
        return r

    total = len(lista)

    def avancar(indice: int, etapa: Etapa) -> None:
        relatar(f"[{indice + 1}/{total}] {etapa.titulo}")
        percentual(int(indice / total * 100))

    for i, etapa in enumerate(lista):
        if cancelado():
            r.puladas.append((etapa.titulo, "cancelado pelo técnico"))
            break
        avancar(i, etapa)

        if etapa.chave == "antes":
            r.antes = historico.capturar("antes")
            historico.registrar(r.antes)

        elif etapa.chave == "diagnostico":
            r.varredura = otimizacao.varrer_tudo(relatar=relatar)

        elif etapa.chave == "disco":
            # A varredura completa ja mede o disco. Medir de novo custaria
            # outro meio minuto e escreveria mais 192 MB sem ganho nenhum.
            if r.varredura is not None and r.varredura.medida_disco:
                r.medida_disco = r.varredura.medida_disco
                relatar("Reaproveitando a medição da varredura.")
            else:
                r.medida_disco = desempenho.medir(cancelado=cancelado)
            if r.medida_disco.erro:
                r.puladas.append((etapa.titulo, r.medida_disco.erro))
                continue

        elif etapa.chave == "limpeza":
            # Reaproveita os achados da varredura. Sem ela nao ha o que
            # limpar, e varrer de novo aqui dobraria o tempo do roteiro.
            achados = r.varredura.achados if r.varredura else None
            if not achados:
                r.puladas.append(
                    (etapa.titulo, "a varredura não foi executada"))
                continue
            resultado = limpeza.limpar(achados, relatar=relatar,
                                       cancelado=cancelado)
            r.liberado = resultado.bytes_liberados

        elif etapa.chave == "sfc":
            reparo.executar("sfc", relatar=relatar, cancelado=cancelado)

        elif etapa.chave == "depois":
            anterior = r.antes
            if anterior is None:
                r.puladas.append(
                    (etapa.titulo, "o estado inicial não foi marcado"))
                continue
            achados = r.varredura.achados if r.varredura else None
            # Depois da limpeza os achados antigos estao vencidos: passar
            # eles daria um "depois" identico ao "antes" no item de lixo.
            if "limpeza" in marcadas:
                achados = None
            final = historico.capturar("depois", achados=achados)
            historico.registrar(final)
            r.mudancas = historico.comparar(anterior, final)

        elif etapa.chave == "entrega":
            r.checklist = entrega.verificar(entrega.carregar(),
                                            relatar=relatar)
            entrega.salvar(r.checklist)

        elif etapa.chave == "pdf":
            if r.varredura is None:
                r.puladas.append(
                    (etapa.titulo, "não há varredura para relatar"))
                continue
            v = r.varredura
            html = pdf.montar_html(
                grupos=v.grupos,
                rede_testes=v.rede.testes if v.rede else None,
                sugestoes=v.sugestoes,
                achados=v.achados,
                inicializacao=v.inicializacao,
                comparacao=r.mudancas or None,
                checklist=r.checklist or None,
            )
            caminho = destino_pdf or pdf.nome_sugerido()
            try:
                r.caminho_pdf = str(pdf.salvar(html, caminho))
            except OSError as erro:
                r.puladas.append((etapa.titulo, str(erro)))
                continue

        r.concluidas.append(etapa.titulo)

    percentual(100)
    relatar(f"Roteiro concluído — {len(r.concluidas)} etapa(s), "
            f"{len(r.puladas)} pulada(s).")
    return r
