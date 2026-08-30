"""Geracao do relatorio em PDF.

Usa QPdfWriter + QTextDocument, ambos do proprio Qt - nenhuma biblioteca
nova entra no executavel por causa disto.

TEMA CLARO DE PROPOSITO
A janela e escura, o relatorio nao. PDF escuro imprime mal, gasta toner e
fica ilegivel em impressora simples. O documento sai para ser anexado em
chamado, impresso e assinado.

O QTextDocument aceita um subconjunto de HTML/CSS: tabela, cor, fonte,
margem e alinhamento funcionam; flexbox, grid e pseudo-elemento nao. Por
isso o layout abaixo e montado com tabelas.
"""

from __future__ import annotations

import socket
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

TINTA = "#16212e"
SUAVE = "#5a6b7d"
FRACO = "#8a99a8"
LINHA = "#d8dfe6"
FUNDO_CAB = "#16212e"
DESTAQUE = "#1f7a8c"

CORES_GRAVIDADE = {
    "alta": ("#b3261e", "#fdeceb"),
    "media": ("#8a5a00", "#fff5e0"),
    "baixa": ("#1f6b45", "#eaf6ef"),
}
ROTULO_GRAVIDADE = {"alta": "PRIORIDADE", "media": "ATENÇÃO", "baixa": "OBSERVAÇÃO"}
CORES_ALERTA = {"": TINTA, "atencao": "#8a5a00", "erro": "#b3261e"}
CORES_SITUACAO = {"ok": "#1f6b45", "atencao": "#8a5a00", "erro": "#b3261e"}


def _esc(texto: object) -> str:
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _cabecalho(subtitulo: str) -> str:
    agora = datetime.now()
    return f"""
    <table width="100%" cellspacing="0" cellpadding="14"
           style="background-color:{FUNDO_CAB};">
      <tr>
        <td>
          <div style="color:#ffffff; font-size:18pt; font-weight:bold;">
            Relatório de atendimento
          </div>
          <div style="color:#9fb3c8; font-size:9pt;">{_esc(subtitulo)}</div>
        </td>
        <td align="right" style="color:#9fb3c8; font-size:8pt;">
          {agora.strftime('%d/%m/%Y')}<br/>{agora.strftime('%H:%M')}
        </td>
      </tr>
    </table>
    """


def _secao(texto: str) -> str:
    return (f'<p style="margin-top:20px; margin-bottom:5px; color:{DESTAQUE};'
            f' font-size:10pt; font-weight:bold;">{_esc(texto).upper()}</p>')


def _tabela_itens(itens) -> str:
    linhas = []
    for i, item in enumerate(itens):
        fundo = "#f6f8fa" if i % 2 else "#ffffff"
        cor = CORES_ALERTA.get(item.alerta, TINTA)
        marca = ""
        if item.alerta == "atencao":
            marca = ' <b>(atenção)</b>'
        elif item.alerta == "erro":
            marca = ' <b>(crítico)</b>'
        linhas.append(
            f'<tr bgcolor="{fundo}">'
            f'<td width="38%" style="color:{SUAVE};">&nbsp;{_esc(item.rotulo)}</td>'
            f'<td style="color:{cor};">{_esc(item.valor)}{marca}&nbsp;</td></tr>')
    return (f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
            f' style="font-size:9pt;">' + "".join(linhas) + "</table>")


def _tabela_rede(testes) -> str:
    linhas = []
    for i, t in enumerate(testes):
        fundo = "#f6f8fa" if i % 2 else "#ffffff"
        cor = CORES_SITUACAO.get(t.situacao, TINTA)
        simbolo = {"ok": "OK", "atencao": "!", "erro": "X"}.get(t.situacao, "")
        linhas.append(
            f'<tr bgcolor="{fundo}">'
            f'<td width="8%" align="center" style="color:{cor}; font-weight:bold;">'
            f'{simbolo}</td>'
            f'<td width="34%" style="color:{SUAVE};">{_esc(t.rotulo)}</td>'
            f'<td style="color:{cor};">{_esc(t.valor)}&nbsp;</td></tr>')
    return (f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
            f' style="font-size:9pt;">' + "".join(linhas) + "</table>")


CORES_MUDANCA = {"melhorou": "#1f6b45", "piorou": "#b3261e", "neutro": SUAVE}


def _tabela_ficha(ficha) -> str:
    """Cabecalho de ordem de servico, em duas colunas."""
    campos = [
        ("Cliente", ficha.cliente),
        ("Telefone", ficha.telefone),
        ("Equipamento", ficha.equipamento),
        ("Abertura", ficha.abertura),
        ("Técnico", ficha.tecnico),
    ]
    linhas = []
    for i, (rotulo, valor) in enumerate([c for c in campos if c[1]]):
        fundo = "#f6f8fa" if i % 2 else "#ffffff"
        linhas.append(
            f'<tr bgcolor="{fundo}">'
            f'<td width="24%" style="color:{SUAVE};">&nbsp;{_esc(rotulo)}</td>'
            f'<td style="color:{TINTA};"><b>{_esc(valor)}</b>&nbsp;</td></tr>')

    # Relato e execucao vao em bloco proprio: sao texto corrido e ficariam
    # espremidos numa celula de tabela de duas colunas.
    blocos = []
    for titulo, texto in (("Defeito relatado", ficha.defeito),
                          ("Serviço executado", ficha.executado),
                          ("Observações", ficha.observacoes)):
        if not texto:
            continue
        corpo = _esc(texto).replace(chr(10), "<br/>")
        blocos.append(
            f'<p style="margin:8px 0 2px 0; color:{SUAVE}; font-size:8pt;">'
            f'{titulo.upper()}</p>'
            f'<p style="margin:0; color:{TINTA}; font-size:9pt;">{corpo}</p>')

    tabela = ""
    if linhas:
        tabela = (f'<table width="100%" cellspacing="0" cellpadding="5"'
                  f' border="0" style="font-size:9pt;">'
                  + "".join(linhas) + "</table>")
    return tabela + "".join(blocos)


def _tabela_checklist(itens) -> str:
    """Checklist de entrega, para o cliente conferir e assinar."""
    linhas = []
    for i, item in enumerate(itens):
        fundo = "#f6f8fa" if i % 2 else "#ffffff"
        marca = "X" if item.marcado else " "
        cor = TINTA if item.marcado else FRACO
        detalhe = _esc(item.resultado or "")
        linhas.append(
            f'<tr bgcolor="{fundo}">'
            f'<td width="6%" align="center" style="color:{TINTA};'
            f' font-family:Consolas,monospace;">&nbsp;[{marca}]</td>'
            f'<td width="48%" style="color:{cor};">{_esc(item.titulo)}</td>'
            f'<td style="color:{SUAVE}; font-size:8pt;">{detalhe}&nbsp;</td>'
            f'</tr>')

    feitos = sum(1 for i in itens if i.marcado)
    tabela = (f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
              f' style="font-size:9pt;">' + "".join(linhas) + "</table>")
    # Linha de assinatura: o checklist so vale como comprovante se alguem
    # puder assinar embaixo dele.
    assinatura = (
        f'<p style="margin-top:22px; color:{SUAVE}; font-size:8pt;">'
        f'{feitos} de {len(itens)} itens conferidos</p>'
        f'<table width="100%" cellspacing="0" cellpadding="0" border="0"'
        f' style="margin-top:26px; font-size:8pt; color:{SUAVE};">'
        f'<tr><td width="45%" style="border-top:1px solid {LINHA};">'
        f'&nbsp;Técnico responsável</td>'
        f'<td width="10%"></td>'
        f'<td style="border-top:1px solid {LINHA};">'
        f'&nbsp;Cliente — recebi o equipamento conferido</td></tr></table>')
    return tabela + assinatura


def _tabela_comparacao(mudancas) -> str:
    """Antes/depois em quatro colunas. E a prova do servico prestado."""
    linhas = [
        f'<tr bgcolor="{FUNDO_CAB}">'
        f'<td width="40%" style="color:#ffffff; font-size:8pt;">&nbsp;INDICADOR</td>'
        f'<td width="20%" align="right" style="color:#ffffff; font-size:8pt;">ANTES</td>'
        f'<td width="20%" align="right" style="color:#ffffff; font-size:8pt;">DEPOIS</td>'
        f'<td width="20%" align="right" style="color:#ffffff; font-size:8pt;">VARIAÇÃO&nbsp;</td>'
        f'</tr>'
    ]
    for i, m in enumerate(mudancas):
        fundo = "#f6f8fa" if i % 2 else "#ffffff"
        cor = CORES_MUDANCA.get(m.situacao, SUAVE)
        variacao = m.variacao or "sem mudança"
        linhas.append(
            f'<tr bgcolor="{fundo}">'
            f'<td style="color:{SUAVE};">&nbsp;{_esc(m.rotulo)}</td>'
            f'<td align="right" style="color:{FRACO};">{_esc(m.antes)}</td>'
            f'<td align="right" style="color:{TINTA};"><b>{_esc(m.depois)}</b></td>'
            f'<td align="right" style="color:{cor};">{_esc(variacao)}&nbsp;</td>'
            f'</tr>')
    return (f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
            f' style="font-size:9pt;">' + "".join(linhas) + "</table>")


def _blocos_sugestoes(sugestoes) -> str:
    partes = []
    for s in sugestoes:
        cor, fundo = CORES_GRAVIDADE.get(s.gravidade, (TINTA, "#ffffff"))
        partes.append(f"""
        <table width="100%" cellspacing="0" cellpadding="9" border="0"
               style="margin-bottom:7px;">
          <tr bgcolor="{fundo}">
            <td width="4" bgcolor="{cor}"></td>
            <td>
              <div style="color:{cor}; font-size:7.5pt; font-weight:bold;">
                {ROTULO_GRAVIDADE.get(s.gravidade, '')}
              </div>
              <div style="color:{TINTA}; font-size:10pt; font-weight:bold;">
                {_esc(s.titulo)}
              </div>
              <div style="color:{SUAVE}; font-size:9pt;">{_esc(s.detalhe)}</div>
            </td>
          </tr>
        </table>""")
    return "".join(partes)


def montar_html(grupos=None, rede_testes=None, sugestoes=None,
                achados=None, inicializacao=None, comparacao=None,
                ficha=None, checklist=None) -> str:
    """Monta o documento. Todo bloco e opcional: a tela de Diagnostico
    manda so `grupos`, a de Relatorios manda tudo."""
    from .win import formatar_bytes

    partes = [
        '<html><body style="font-family:Segoe UI, Arial; color:%s;">' % TINTA,
        _cabecalho(f"{socket.gethostname()}"),
    ]

    if ficha is not None and not ficha.vazia:
        # Primeira secao do documento: quem e a maquina de quem, e
        # o que foi pedido. Sem isso o PDF e um laudo sem dono.
        partes.append(_secao("Ordem de serviço"))
        partes.append(_tabela_ficha(ficha))

    if comparacao:
        # Vem antes dos apontamentos: o cliente abre o PDF querendo saber
        # o que melhorou, nao o que ainda falta.
        partes.append(_secao("Antes e depois do atendimento"))
        partes.append(_tabela_comparacao(comparacao))

    if sugestoes:
        graves = sum(1 for s in sugestoes if s.gravidade == "alta")
        partes.append(_secao("Apontamentos"))
        partes.append(
            f'<p style="color:{SUAVE}; font-size:9pt; margin-bottom:8px;">'
            f'{len(sugestoes)} item(ns), {graves} de prioridade.</p>')
        partes.append(_blocos_sugestoes(sugestoes))

    for g in (grupos or []):
        partes.append(_secao(g.titulo))
        partes.append(_tabela_itens(g.itens))

    if rede_testes:
        partes.append(_secao("Rede"))
        partes.append(_tabela_rede(rede_testes))

    if achados:
        total = sum(a.bytes_total for a in achados)
        partes.append(_secao("Espaço recuperável"))
        linhas = []
        for i, a in enumerate(achados):
            if not a.arquivos:
                continue
            fundo = "#f6f8fa" if i % 2 else "#ffffff"
            linhas.append(
                f'<tr bgcolor="{fundo}">'
                f'<td width="52%" style="color:{SUAVE};">&nbsp;{_esc(a.titulo)}</td>'
                f'<td width="20%" align="right" style="color:{FRACO};">'
                f'{a.arquivos} arq.</td>'
                f'<td align="right" style="color:{TINTA};">'
                f'{formatar_bytes(a.bytes_total)}&nbsp;</td></tr>')
        linhas.append(
            f'<tr><td style="color:{TINTA}; font-weight:bold;">&nbsp;Total</td>'
            f'<td></td><td align="right" style="color:{TINTA}; '
            f'font-weight:bold;">{formatar_bytes(total)}&nbsp;</td></tr>')
        partes.append(
            f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
            f' style="font-size:9pt;">' + "".join(linhas) + "</table>")

    if inicializacao:
        partes.append(_secao(f"Inicialização ({len(inicializacao)} itens)"))
        linhas = []
        for i, item in enumerate(inicializacao):
            fundo = "#f6f8fa" if i % 2 else "#ffffff"
            linhas.append(
                f'<tr bgcolor="{fundo}">'
                f'<td width="40%" style="color:{TINTA};">&nbsp;{_esc(item.nome)}</td>'
                f'<td style="color:{FRACO}; font-size:8pt;">'
                f'{_esc(item.origem)}&nbsp;</td></tr>')
        partes.append(
            f'<table width="100%" cellspacing="0" cellpadding="5" border="0"'
            f' style="font-size:9pt;">' + "".join(linhas) + "</table>")

    if checklist:
        # Antes do rodape, nao depois: o rodape fecha o documento, e uma
        # secao abaixo dele apareceria como se fosse anexo solto.
        partes.append(_secao("Checklist de entrega"))
        partes.append(_tabela_checklist(checklist))

    partes.append(
        f'<p style="margin-top:26px; color:{FRACO}; font-size:7.5pt;'
        f' border-top:1px solid {LINHA}; padding-top:8px;">'
        f'Gerado pelo Ripper em '
        f'{datetime.now().strftime("%d/%m/%Y às %H:%M")} · '
        f'máquina {_esc(socket.gethostname())}</p>')

    partes.append("</body></html>")
    return "".join(partes)


def salvar(html: str, destino: str | Path) -> Path:
    """Grava o HTML como PDF A4."""
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    escritor = QPdfWriter(str(caminho))
    escritor.setPageSize(QPageSize(QPageSize.A4))
    # 16 mm de margem: cabe em qualquer impressora e sobra espaco para
    # furador ou grampo no canto.
    escritor.setPageMargins(QMarginsF(16, 14, 16, 14), QPageLayout.Millimeter)
    # 150 dpi basta para texto e mantem o arquivo leve; 1200 (o padrao)
    # gera PDF grande sem ganho nenhum num documento sem imagem.
    escritor.setResolution(150)

    documento = QTextDocument()
    documento.setHtml(html)
    # Sem casar a largura do documento com a da pagina, o Qt quebra a
    # tabela na largura errada e o conteudo sai cortado a direita.
    documento.setPageSize(escritor.pageLayout().paintRectPixels(150).size())
    documento.print_(escritor)

    return caminho


def nome_sugerido() -> str:
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M")
    return f"ripper_{socket.gethostname()}_{carimbo}.pdf"
