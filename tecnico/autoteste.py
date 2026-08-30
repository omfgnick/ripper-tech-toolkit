"""Exercita os caminhos que exigem administrador e grava um relatorio.

Existe porque a maquina de desenvolvimento roda sem elevacao: exportar
drivers, ler senhas de Wi-Fi, criar ponto de restauracao e consultar
contadores SMART sempre pararam na guarda de permissao, e o caminho de
sucesso nunca foi executado.

    Ripper.exe --autoteste     (abrir como administrador)

O QUE NAO E EXERCITADO, E POR QUE
    Limpar a fila de impressao descarta TODOS os trabalhos pendentes, de
    todas as impressoras e de todos os usuarios. Nao ha versao inofensiva
    disso. O autoteste confere se o servico existe e se seria possivel
    para-lo, e para ai - um teste que apaga o trabalho de alguem nao e
    teste, e acidente.

    Restaurar drivers instala pacotes no repositorio do Windows e pode
    pedir reinicio. Tambem so e verificado ate a validacao da pasta.

Tudo que escreve em disco escreve numa pasta temporaria e apaga no fim.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Passo:
    nome: str
    resultado: str = ""
    detalhe: str = ""

    @property
    def marca(self) -> str:
        return {"ok": "OK   ", "falhou": "FALHA",
                "pulado": "PULOU"}.get(self.resultado, "?    ")


def _drivers(passos: list[Passo]) -> None:
    from .nucleo import drivers

    lista = drivers.listar()
    passos.append(Passo("Listar drivers de terceiros",
                        "ok" if lista else "falhou",
                        f"{len(lista)} pacote(s)"))

    pasta = Path(tempfile.mkdtemp(prefix="ripper_autoteste_"))
    try:
        r = drivers.exportar(pasta)
        passos.append(Passo("Exportar drivers",
                            "ok" if r.ok else "falhou",
                            r.mensagem))
        if r.ok:
            # Restaurar de verdade instalaria os pacotes de volta; aqui so
            # se confirma que a pasta gerada e aceita como origem valida.
            achou = list(Path(r.destino).rglob("*.inf"))
            passos.append(Passo(
                "Pasta de restauração válida",
                "ok" if achou else "falhou",
                f"{len(achou)} arquivo(s) .inf encontrados"))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def _wifi(passos: list[Passo]) -> None:
    from .nucleo import wifi

    tem, motivo = wifi.disponibilidade()
    if not tem:
        passos.append(Passo("Senhas de Wi-Fi", "pulado", motivo))
        return

    perfis, aviso = wifi.perfis()
    com_senha = sum(1 for p in perfis if p.senha)
    passos.append(Passo(
        "Exportar perfis de Wi-Fi",
        "ok" if perfis else "falhou",
        f"{len(perfis)} perfil(is), {com_senha} com senha em claro"
        + (f" — {aviso}" if aviso else "")))

    redes, motivo = wifi.redes()
    passos.append(Passo("Varrer redes ao alcance",
                        "ok" if redes else "falhou",
                        f"{len(redes)} rede(s)" if redes else motivo))


def _restauracao(passos: list[Passo]) -> None:
    from .nucleo import reparo

    antes = reparo._ultimo_ponto()
    feito, motivo = reparo.criar_ponto("Ripper - autoteste")
    depois = reparo._ultimo_ponto()
    passos.append(Passo(
        "Criar ponto de restauração",
        "ok" if feito else "falhou",
        motivo + (f" | antes={antes or 'nenhum'} depois={depois or 'nenhum'}"
                  if not feito else "")))


def _smart(passos: list[Passo]) -> None:
    from .nucleo import saude

    discos = saude.discos()
    com_contador = [d for d in discos if d.horas_ligado is not None
                    or d.desgaste is not None]
    passos.append(Passo(
        "Contadores SMART",
        "ok" if com_contador else "falhou",
        f"{len(com_contador)} de {len(discos)} disco(s) com contadores"))


def _spooler(passos: list[Passo]) -> None:
    from .nucleo import impressoras, win

    lista = impressoras.listar()
    pendentes = sum(len(i.fila) for i in lista)
    saida = win.powershell(
        "(Get-Service Spooler -ErrorAction SilentlyContinue).Status.ToString()")
    estado = saida.texto.strip() if saida.ok else "desconhecido"
    passos.append(Passo(
        "Limpar fila de impressão",
        "pulado",
        f"não executado por ser destrutivo — spooler {estado}, "
        f"{len(lista)} impressora(s), {pendentes} trabalho(s) na fila"))


def executar(dizer=print) -> int:
    """Roda todos os passos e grava o relatorio. 0 = nenhuma falha."""
    from PySide6.QtGui import QGuiApplication

    from .nucleo import admin

    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv[:1])

    elevado = admin.e_administrador()
    passos: list[Passo] = []

    for etapa in (_drivers, _wifi, _restauracao, _smart, _spooler):
        try:
            etapa(passos)
        except Exception as erro:  # noqa: BLE001
            # Um passo que estoura nao pode derrubar os outros: o objetivo
            # do autoteste e justamente descobrir o que quebra.
            passos.append(Passo(etapa.__name__.strip("_"), "falhou",
                                f"{type(erro).__name__}: {erro}"))

    falhas = sum(1 for p in passos if p.resultado == "falhou")
    linhas = [
        "AUTOTESTE DO RIPPER",
        "=" * 62,
        f"Administrador : {'sim' if elevado else 'NAO - resultados limitados'}",
        f"Python        : {sys.version.split()[0]}",
        "",
    ]
    for p in passos:
        linhas.append(f"  {p.marca} {p.nome}")
        if p.detalhe:
            linhas.append(f"        {p.detalhe}")
    linhas += ["", f"Resultado: {falhas} falha(s) em {len(passos)} passo(s)"]

    if not elevado:
        linhas.append("")
        linhas.append("Reabra como administrador para exercitar os caminhos "
                      "que exigem elevacao.")

    texto = "\n".join(linhas)
    destino = Path(sys.executable).parent if getattr(sys, "_MEIPASS", None) \
        else Path(__file__).resolve().parent.parent
    arquivo = destino / "autoteste.txt"
    try:
        arquivo.write_text(texto, encoding="utf-8")
    except OSError:
        arquivo = None

    dizer(texto)
    if arquivo:
        dizer(f"\nRelatorio salvo em: {arquivo}")
    return 1 if falhas else 0
