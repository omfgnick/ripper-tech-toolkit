"""Modo linha de comando: varre e gera o PDF sem abrir janela.

Serve para duas coisas que a interface nao resolve bem:

    - Rodar de um pendrive num script de atendimento padrao, junto com as
      outras ferramentas da bancada.
    - Marcar o estado inicial no comeco do servico e comparar no fim, sem
      depender do tecnico lembrar de clicar no botao certo.

CONSOLE NO EXECUTAVEL EMPACOTADO
    O .exe e compilado com --windowed, ou seja, sem console proprio: um
    print() aqui cairia no vazio. AttachConsole(-1) pega emprestado o
    console de quem chamou (o cmd ou PowerShell aberto) e reabre os fluxos
    ali. Sem isso o modo linha de comando funcionaria, mas em silencio
    absoluto - o tecnico nao veria nem o caminho do PDF gerado.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AJUDA = "Ripper - utilitario de atendimento tecnico"


def _prender_console() -> None:
    if sys.stdout is not None and sys.stdout.isatty():
        return
    try:
        import ctypes
        # -1 = ATTACH_PARENT_PROCESS
        if not ctypes.windll.kernel32.AttachConsole(-1):
            return
        for fluxo, arquivo in (("stdout", "w"), ("stderr", "w")):
            try:
                setattr(sys, fluxo, open("CONOUT$", arquivo, encoding="utf-8",
                                         errors="replace", buffering=1))
            except OSError:
                pass
    except (AttributeError, OSError):
        # Sem console ao qual se prender (duplo clique no explorador).
        # Nao e erro: o PDF continua sendo gerado.
        pass


def _dizer(mensagem: str) -> None:
    try:
        print(mensagem, flush=True)
    except (OSError, ValueError):
        pass


def montar_analisador() -> argparse.ArgumentParser:
    a = argparse.ArgumentParser(prog="Ripper", description=AJUDA)
    a.add_argument("--relatorio", action="store_true",
                   help="varre a máquina e gera o PDF, sem abrir a janela")
    a.add_argument("--marcar-antes", action="store_true",
                   help="registra o estado inicial e sai (use no começo)")
    a.add_argument("--comparar", action="store_true",
                   help="inclui no PDF a comparação com o último estado inicial")
    a.add_argument("--saida", metavar="CAMINHO", default="",
                   help="arquivo ou pasta de destino do PDF")
    a.add_argument("--roteiro", action="store_true",
                   help="executa o roteiro completo (sem as etapas que alteram)")
    a.add_argument("--com-limpeza", action="store_true",
                   help="inclui a limpeza de temporários no roteiro")
    a.add_argument("--autoteste", action="store_true",
                   help="exercita os caminhos que exigem admin e grava um relatório")
    a.add_argument("--verificar", action="store_true",
                   help="confere se os recursos do executável estão íntegros")
    return a


def _destino(saida: str) -> Path:
    from .nucleo import pdf

    if not saida:
        base = (Path(sys.executable).parent if getattr(sys, "_MEIPASS", None)
                else Path.cwd())
        return base / pdf.nome_sugerido()

    caminho = Path(saida)
    # Aceitar uma pasta e conveniencia real: em script de atendimento o
    # tecnico passa a pasta do cliente e deixa o nome com carimbo de hora.
    if caminho.is_dir() or saida.endswith(("\\", "/")):
        return caminho / pdf.nome_sugerido()
    return caminho if caminho.suffix else caminho.with_suffix(".pdf")


def _marcar_antes() -> int:
    from .nucleo import historico

    inst = historico.capturar("antes", relatar=_dizer)
    arquivo = historico.registrar(inst)
    _dizer(f"Estado inicial registrado em {inst.momento}.")
    _dizer(f"Histórico: {arquivo}")
    return 0


def _comparacao_disponivel():
    """Ultimo 'antes' desta maquina que ainda nao virou comparacao."""
    from .nucleo import historico

    registros = historico.carregar()
    for inst in reversed(registros):
        if inst.rotulo == "antes":
            return inst
        if inst.rotulo == "depois":
            # Ja houve um fechamento depois deste ponto: o par anterior
            # esta completo e nao deve ser reaproveitado.
            return None
    return None


def _relatorio(argumentos) -> int:
    from .nucleo import historico, otimizacao, pdf

    _dizer("Varrendo a máquina...")
    varredura = otimizacao.varrer_tudo(relatar=_dizer)

    comparacao = None
    if argumentos.comparar:
        antes = _comparacao_disponivel()
        if antes is None:
            _dizer("Aviso: nenhum estado inicial pendente. "
                   "Rode --marcar-antes antes do serviço.")
        else:
            depois = historico.capturar("depois", achados=varredura.achados)
            historico.registrar(depois)
            comparacao = historico.comparar(antes, depois)
            _dizer(f"Comparado com o estado de {antes.momento}.")

    html = pdf.montar_html(
        grupos=varredura.grupos,
        rede_testes=varredura.rede.testes if varredura.rede else None,
        sugestoes=varredura.sugestoes,
        achados=varredura.achados,
        inicializacao=varredura.inicializacao,
        comparacao=comparacao,
    )

    destino = _destino(argumentos.saida)
    try:
        caminho = pdf.salvar(html, destino)
    except OSError as erro:
        _dizer(f"ERRO ao gravar o PDF: {erro}")
        return 2

    graves = sum(1 for s in varredura.sugestoes if s.gravidade == "alta")
    _dizer("")
    for s in varredura.sugestoes:
        _dizer(f"  [{s.gravidade:5}] {s.titulo} — {s.detalhe}")
    _dizer("")
    _dizer(f"PDF: {caminho}")
    # Codigo de saida util em script: 1 sinaliza que algo grave apareceu, e
    # o .bat do atendimento pode parar para o tecnico olhar.
    return 1 if graves else 0


def _roteiro(argumentos) -> int:
    from .nucleo import roteiro

    marcadas = {e.chave for e in roteiro.etapas() if e.marcada}
    if argumentos.com_limpeza:
        # Etapa destrutiva so entra por pedido explicito, igual na tela.
        # Um roteiro de linha de comando que apaga por padrao seria
        # armadilha em script de atendimento.
        marcadas.add("limpeza")

    r = roteiro.executar(marcadas, destino_pdf=str(_destino(argumentos.saida)),
                         relatar=_dizer)
    _dizer("")
    for titulo, motivo in r.puladas:
        _dizer(f"  pulada: {titulo} — {motivo}")
    for m in r.mudancas:
        _dizer(f"  {m.rotulo}: {m.antes} -> {m.depois} "
               f"{m.variacao or '(sem mudança)'}")
    if r.caminho_pdf:
        _dizer("")
        _dizer(f"PDF: {r.caminho_pdf}")

    graves = 0
    if r.varredura:
        graves = sum(1 for s in r.varredura.sugestoes if s.gravidade == "alta")
    return 1 if graves else 0


def executar(argv: list[str] | None = None) -> int:
    analisador = montar_analisador()
    argumentos = analisador.parse_args(argv)

    if not (argumentos.relatorio or argumentos.marcar_antes
            or argumentos.roteiro or argumentos.autoteste
            or argumentos.verificar):
        return -1      # nada de linha de comando: quem chamou abre a janela

    _prender_console()

    # QPdfWriter e QTextDocument precisam de uma instancia de aplicacao,
    # mas nao de janela nenhuma. QGuiApplication basta e nao cria interface.
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv[:1])

    if argumentos.autoteste:
        from .autoteste import executar as rodar_autoteste
        return rodar_autoteste(_dizer)

    if argumentos.marcar_antes:
        return _marcar_antes()
    if argumentos.roteiro:
        return _roteiro(argumentos)
    return _relatorio(argumentos)
