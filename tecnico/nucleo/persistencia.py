r"""Onde adware se esconde depois de Programas e Inicializacao.

O painel de Programas cobre o que aparece em "Adicionar ou remover" e o
que esta nas chaves Run do registro. Adware moderno evita os dois: cria
uma tarefa agendada que roda um script a cada logon, ou instala uma
extensao de navegador que sequestra a busca. Nenhuma das duas aparece
onde o tecnico costuma olhar.

SOBRE OS AVISOS
    O app aponta indicios, nao veredictos. "Roda um script do %TEMP%" e
    um fato observavel e digno de olhar; chamar de virus seria chute. A
    decisao continua sendo do tecnico, com o motivo escrito ao lado.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import win

ESTADOS = {0: "desconhecido", 1: "desabilitada", 2: "na fila",
           3: "pronta", 4: "em execução"}

# Interpretadores que aparecem em tarefa legitima, mas quase sempre com
# caminho de programa. Combinados com pasta de usuario, merecem olhada.
INTERPRETADORES = (".vbs", ".js", ".jse", ".vbe", ".ps1", ".bat", ".cmd", ".hta")

CONSULTA_TAREFAS = (
    r"Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } "
    "| Select-Object TaskName,TaskPath,State,"
    "@{n='Acao';e={($_.Actions | Select-Object -First 1).Execute}},"
    "@{n='Args';e={($_.Actions | Select-Object -First 1).Arguments}},"
    "@{n='Autor';e={$_.Author}} | ConvertTo-Json -Compress"
)


@dataclass
class Tarefa:
    nome: str
    caminho: str = ""
    estado: str = ""
    acao: str = ""
    argumentos: str = ""
    autor: str = ""
    motivo: str = ""          # preenchido quando ha indicio
    resolver: str = ""        # como confirmar e como desativar

    @property
    def suspeita(self) -> bool:
        return bool(self.motivo)


# Cada indicio com o que fazer a seguir. Apontar sem dizer como confirmar
# transfere a duvida em vez de resolver: o tecnico fica com uma lista de
# nomes estranhos e nenhum criterio para decidir o que desativar.
COMO_RESOLVER = {
    "Tarefa sem programa definido.":
        "Tarefa órfã — o programa que a criou foi desinstalado sem limpar. "
        "Não faz nada e pode ser removida sem risco.",
    "Executa script a partir de pasta de usuário.":
        "Abra o arquivo num editor de texto antes de decidir: script de "
        "instalador legítimo é legível; ofuscado ou com URL estranha, "
        "desative a tarefa e leve o arquivo para análise.",
    "Executa script em vez de programa.":
        "Verifique quem assina o script e o que ele faz. Atualizador de "
        "fabricante costuma ser assim; conteúdo ilegível, não.",
    "Programa dentro da pasta de temporários.":
        "Programa legítimo não mora no %TEMP%, que é apagado por limpeza. "
        "Trate como suspeito até provar o contrário.",
    "PowerShell com janela oculta ou comando codificado.":
        "É o padrão mais usado por malware sem arquivo. Decodifique o "
        "argumento -enc (Base64) antes de qualquer coisa; se não "
        "reconhecer o conteúdo, desative e faça varredura completa.",
}


def _avaliar(acao: str, argumentos: str) -> str:
    """Devolve o motivo de desconfianca, ou string vazia."""
    alvo = f"{acao} {argumentos}".lower()
    if not acao.strip():
        return "Tarefa sem programa definido."

    pastas_moveis = (r"\appdata" "\\", r"\temp" "\\",
                     r"\downloads" "\\", r"\programdata" "\\")
    em_pasta_movel = any(p in acao.lower() for p in pastas_moveis)
    e_script = any(alvo.count(ext) for ext in INTERPRETADORES)

    if em_pasta_movel and e_script:
        return "Executa script a partir de pasta de usuário."
    if e_script:
        return "Executa script em vez de programa."
    if r"\temp" "\\" in acao.lower():
        return "Programa dentro da pasta de temporários."
    if "powershell" in alvo and ("-enc" in alvo or "hidden" in alvo):
        return "PowerShell com janela oculta ou comando codificado."
    return ""


def tarefas(relatar=lambda _: None) -> list[Tarefa]:
    relatar("Lendo tarefas agendadas...")
    saida = win.powershell(CONSULTA_TAREFAS, tempo_limite=180)
    if not saida.ok or not saida.texto.strip():
        return []
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    if isinstance(dados, dict):
        dados = [dados]

    lista = []
    for d in dados:
        acao = (d.get("Acao") or "").strip()
        argumentos = (d.get("Args") or "").strip()
        motivo = _avaliar(acao, argumentos)
        lista.append(Tarefa(
            nome=(d.get("TaskName") or "").strip(),
            caminho=(d.get("TaskPath") or "").strip(),
            estado=ESTADOS.get(d.get("State"), ""),
            acao=acao,
            argumentos=argumentos,
            autor=(d.get("Autor") or "").strip(),
            motivo=motivo,
            resolver=COMO_RESOLVER.get(motivo, ""),
        ))
    lista.sort(key=lambda t: (not t.suspeita, t.nome.lower()))
    relatar(f"{len(lista)} tarefa(s) fora do catálogo da Microsoft.")
    return lista


# ---------------------------------------------------------------------
# EXTENSOES DE NAVEGADOR
# ---------------------------------------------------------------------
# Categorias de extensao que merecem conversa com o cliente. Nao sao
# malware por definicao - varias sao de empresas conhecidas - mas todas
# leem o que a pessoa navega para funcionar, e o cliente costuma nao saber
# disso quando instala.
CATEGORIAS_DE_RISCO = [
    (("cashback", "cupom", "coupon", "desconto", "promo", "shopping",
      "honey", "rakuten"),
     "Cashback e cupom",
     "Para achar oferta, precisa ler cada página de loja que você abre, "
     "incluindo o carrinho e o checkout. Vale confirmar com o cliente se "
     "ele instalou de propósito."),
    (("search", "busca", "newtab", "nova aba", "homepage"),
     "Altera busca ou página inicial",
     "É a categoria mais usada por sequestrador de navegador. Confirme se "
     "a busca padrão continua sendo a que o cliente escolheu."),
    (("vpn", "proxy", "unblock", "desbloquе"),
     "VPN ou proxy",
     "Todo o tráfego do navegador passa por um servidor de terceiro. "
     "Gratuito costuma se pagar vendendo esse tráfego."),
    (("download", "video downloader", "converter", "mp3"),
     "Baixador de vídeo",
     "Categoria com histórico de troca de dono e injeção de anúncio "
     "depois de instalada."),
    (("pdf", "converter", "editor online"),
     "Conversor online",
     "Envia o arquivo para um servidor. Documento de cliente não deveria "
     "sair da máquina sem ele saber."),
]


def classificar(nome: str, descricao: str = "") -> tuple[str, str]:
    """(categoria, por que merece atencao). Vazio quando nao se aplica."""
    alvo = f"{nome} {descricao}".lower()
    for termos, categoria, motivo in CATEGORIAS_DE_RISCO:
        if any(t in alvo for t in termos):
            return categoria, motivo
    return "", ""


@dataclass
class Extensao:
    navegador: str
    perfil: str
    identificador: str
    nome: str = ""
    versao: str = ""
    descricao: str = ""
    categoria: str = ""
    atencao: str = ""


def _navegadores() -> list[tuple[str, Path]]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming = Path(os.environ.get("APPDATA", ""))
    return [
        ("Chrome", local / "Google" / "Chrome" / "User Data"),
        ("Edge", local / "Microsoft" / "Edge" / "User Data"),
        ("Brave", local / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("Vivaldi", local / "Vivaldi" / "User Data"),
        # Opera guarda o perfil no Roaming, nao no Local, ao contrario dos
        # outros navegadores baseados em Chromium.
        ("Opera", roaming / "Opera Software" / "Opera Stable"),
        ("Opera GX", roaming / "Opera Software" / "Opera GX Stable"),
    ]


def _resolver(pasta: Path, manifesto: dict, valor: str) -> str:
    """Traduz valores no formato __MSG_chave__ lendo os _locales.

    Vale para `name` e para `description`: as duas vem tokenizadas em
    extensao internacionalizada, e mostrar "__MSG_extDesc__" na tela do
    tecnico nao ajuda ninguem.
    """
    valor = (valor or "").strip()
    if not (valor.startswith("__MSG_") and valor.endswith("__")):
        return valor

    chave = valor[6:-2]
    idiomas = [manifesto.get("default_locale") or "en", "pt_BR", "pt", "en",
               "en_US"]
    vistos = set()
    for idioma in idiomas:
        if idioma in vistos:
            continue
        vistos.add(idioma)
        arquivo = pasta / "_locales" / idioma / "messages.json"
        try:
            mensagens = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        # As chaves dos _locales nao diferenciam maiuscula de minuscula em
        # parte das extensoes; comparar em minusculo evita falso negativo.
        for nome_chave, entrada in mensagens.items():
            if nome_chave.lower() == chave.lower() and entrada.get("message"):
                return entrada["message"].strip()
    # Sem traducao, devolver vazio e melhor que mostrar o token cru.
    return ""


def extensoes(relatar=lambda _: None) -> list[Extensao]:
    relatar("Lendo extensões de navegador...")
    achadas: list[Extensao] = []

    for navegador, base in _navegadores():
        if not base.is_dir():
            continue
        for pasta_perfil in base.iterdir():
            diretorio = pasta_perfil / "Extensions"
            if not diretorio.is_dir():
                continue
            for pasta_ext in diretorio.iterdir():
                if not pasta_ext.is_dir():
                    continue
                # Cada extensao guarda uma pasta por versao instalada; a
                # mais recente e a que vale.
                versoes = sorted(p for p in pasta_ext.iterdir() if p.is_dir())
                if not versoes:
                    continue
                alvo = versoes[-1]
                try:
                    manifesto = json.loads(
                        (alvo / "manifest.json").read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    continue
                achadas.append(Extensao(
                    navegador=navegador,
                    perfil=pasta_perfil.name,
                    identificador=pasta_ext.name,
                    nome=_resolver(alvo, manifesto,
                                   manifesto.get("name")),
                    versao=(manifesto.get("version") or "").strip(),
                    descricao=_resolver(
                        alvo, manifesto,
                        manifesto.get("description"))[:120],
                ))
                categoria, motivo = classificar(
                    achadas[-1].nome, achadas[-1].descricao)
                achadas[-1].categoria = categoria
                achadas[-1].atencao = motivo

    achadas.sort(key=lambda e: (e.navegador, e.nome.lower()))
    relatar(f"{len(achadas)} extensão(ões) encontrada(s).")
    return achadas
