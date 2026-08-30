"""Ativacao legitima do Windows: chave do cliente, ativacao e diagnostico.

O QUE ESTE MODULO FAZ
    Instala uma chave que o cliente forneceu, dispara a ativacao contra os
    servidores da Microsoft, le o detalhe da licenca e explica por que a
    ativacao falhou. Tudo com `slmgr`, que e a ferramenta oficial.

O QUE ELE NAO FAZ
    Nao contorna licenciamento. Nao emula servidor KMS, nao aplica HWID
    forjado, nao instala chave generica de volume. O caso que ele resolve
    e o honesto e o mais comum na bancada: maquina que TEM licenca e
    perdeu a ativacao depois de formatar ou trocar placa-mae.

CHAVE DIGITAL E O CASO MAIS FREQUENTE
    Desde o Windows 10, a maioria das maquinas de varejo tem licenca
    digital atrelada a conta Microsoft ou ao hardware. Nesses casos nao ha
    chave para digitar: a ativacao volta sozinha ao conectar a internet,
    ou pelo solucionador de problemas apos troca de peca. Por isso o
    diagnostico vem antes dos botoes - digitar chave numa maquina de
    licenca digital e o erro mais comum e so atrasa o atendimento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import win

# Formato da chave: cinco grupos de cinco. Validar antes de mandar evita
# uma ida ao servidor e uma mensagem de erro que nao explica nada.
FORMATO_CHAVE = re.compile(r"^[A-Z0-9]{5}(-[A-Z0-9]{5}){4}$")

CODIGOS = {
    "0xC004F034": "A chave não foi aceita pelo servidor de licenças.",
    "0xC004C003": "A chave já foi usada em outra máquina ou foi bloqueada.",
    "0xC004F074": "Nenhum servidor de ativação respondeu. Sem internet?",
    "0xC004E016": "Chave inválida para esta edição do Windows.",
    "0xC004F050": "Chave inválida.",
    "0x803FA067": "A licença digital não foi encontrada para este hardware.",
    "0x8007232B": "O nome do servidor de ativação não resolveu (DNS).",
}


@dataclass
class Situacao:
    edicao: str = ""
    canal: str = ""
    estado: str = ""
    alerta: str = ""
    chave_parcial: str = ""
    digital: bool = False
    dias_restantes: int | None = None
    detalhe_bruto: str = ""
    orientacao: list[str] = field(default_factory=list)


def _slmgr(argumento: str, tempo_limite: int = 180):
    """Roda slmgr via cscript, que devolve texto no console.

    O slmgr.vbs sozinho abre caixa de dialogo grafica; com cscript e
    //nologo ele escreve na saida padrao, que e o que da para ler aqui.
    """
    return win.rodar(
        ["cscript", "//nologo", r"C:\Windows\System32\slmgr.vbs", argumento],
        tempo_limite=tempo_limite)


def _codigo_do_erro(texto: str) -> str:
    achado = re.search(r"0x[0-9A-Fa-f]{8}", texto or "")
    return achado.group(0).upper() if achado else ""


def explicar(texto: str) -> str:
    codigo = _codigo_do_erro(texto)
    if not codigo:
        return ""
    return CODIGOS.get(codigo, f"O Windows devolveu o código {codigo}.")


def situacao(relatar=lambda _: None) -> Situacao:
    """Le o estado da licenca do Windows e monta a orientacao."""
    from . import licenca

    relatar("Lendo a licença do Windows...")
    s = Situacao()

    produtos = licenca.produtos()
    janela = next((p for p in produtos if "windows" in p.nome.lower()), None)
    if janela is not None:
        s.edicao = janela.nome
        s.canal = janela.canal
        s.estado = janela.situacao
        s.alerta = janela.alerta
        s.chave_parcial = janela.chave_parcial

    # O detalhe traz canal, data de expiracao e o motivo real da falha.
    saida = _slmgr("/dlv")
    s.detalhe_bruto = (saida.texto or saida.erro or "").strip()

    dias = re.search(r"(\d+)\s*minute", s.detalhe_bruto)
    if dias:
        s.dias_restantes = int(dias.group(1)) // (60 * 24)

    # Licenca digital nao tem chave para digitar. Detectar isso primeiro
    # evita o erro mais comum: pedir chave a quem nao precisa de chave.
    s.digital = bool(re.search(r"digital|automa", s.detalhe_bruto, re.I))

    s.orientacao = _orientar(s)
    return s


def _orientar(s: Situacao) -> list[str]:
    """Passos concretos para esta maquina, em ordem."""
    # licenca.SITUACOES devolve "ok" para licenciado, nao string vazia.
    # Comparar so com "" fazia a orientacao mandar pedir chave numa
    # maquina ja ativada - exatamente o oposto do util.
    if s.alerta in ("", "ok") and s.estado.lower().startswith("ativ"):
        return ["Windows ativado. Nada a fazer."]

    passos = []
    canal = (s.canal or "").upper()

    if "OEM" in canal:
        passos.append(
            "Licença OEM: presa a esta placa-mãe. Costuma reativar sozinha "
            "com internet. Se não voltar, use a chave da BIOS (aba "
            "Diagnóstico) com 'Instalar chave'.")
    elif s.digital or not canal:
        passos.append(
            "Provavelmente licença digital: não há chave para digitar. "
            "Conecte a internet e use 'Ativar agora'.")
        passos.append(
            "Se trocou placa-mãe, entre com a conta Microsoft do cliente em "
            "Configurações › Sistema › Ativação › Solução de problemas.")
    elif "RETAIL" in canal:
        passos.append(
            "Licença de varejo: peça ao cliente a chave (nota fiscal, "
            "e-mail de compra ou etiqueta) e use 'Instalar chave'.")
    elif "VOLUME" in canal:
        passos.append(
            "Licença corporativa: depende do servidor de ativação da "
            "empresa. Fora da rede dela, não ativa. Fale com o TI do "
            "cliente.")

    passos.append("Sem licença própria, a saída é comprar uma chave. "
                  "Esta ferramenta não contorna ativação.")
    return passos


@dataclass
class Resultado:
    ok: bool = False
    mensagem: str = ""
    detalhe: str = ""


def instalar_chave(chave: str, relatar=lambda _: None) -> Resultado:
    """Instala uma chave fornecida pelo cliente (`slmgr /ipk`)."""
    from . import admin

    chave = (chave or "").strip().upper().replace(" ", "")
    if not FORMATO_CHAVE.match(chave):
        return Resultado(mensagem="Formato inválido. A chave tem cinco "
                                  "grupos de cinco caracteres, separados "
                                  "por hífen.")
    if not admin.e_administrador():
        return Resultado(mensagem="Instalar chave exige executar como "
                                  "administrador.")

    relatar("Instalando a chave...")
    saida = _slmgr(f"/ipk {chave}")
    texto = (saida.texto or saida.erro or "").strip()
    motivo = explicar(texto)
    if motivo:
        return Resultado(mensagem=motivo, detalhe=texto)
    return Resultado(True, "Chave instalada. Use 'Ativar agora' em seguida.",
                     texto)


def ativar(relatar=lambda _: None, percentual=lambda _: None) -> Resultado:
    """Dispara a ativacao contra os servidores da Microsoft."""
    from . import admin

    if not admin.e_administrador():
        return Resultado(mensagem="Ativar exige executar como administrador.")

    relatar("Contatando o servidor de ativação...")
    percentual(-1)
    saida = _slmgr("/ato", tempo_limite=300)
    percentual(100)

    texto = (saida.texto or saida.erro or "").strip()
    motivo = explicar(texto)
    if motivo:
        return Resultado(mensagem=motivo, detalhe=texto)
    return Resultado(True, "Ativação concluída.", texto)
