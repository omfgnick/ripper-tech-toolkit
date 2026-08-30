"""Checklist de entrega e exportacao da pasta do cliente.

O que o tecnico confere de cabeca antes de devolver a maquina, virando
lista - e, no fim, uma secao assinavel do PDF. A pesquisa sobre dores de
suporte aponta documentacao manual como um dos dois maiores atritos; esta
e a parte do atendimento que hoje so existe na memoria de quem atendeu.

METADE VERIFICA SOZINHA, METADE NAO
    Audio, rede, Wi-Fi, camera e bateria da para conferir por software.
    Tela, teclado, USB e as portas fisicas nao - alguem precisa olhar e
    tocar. Marcar automaticamente um item que ninguem testou seria pior
    que nao ter checklist, entao esses ficam manuais e em branco.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import win


@dataclass
class Item:
    chave: str
    titulo: str
    automatico: bool = False
    marcado: bool = False
    resultado: str = ""       # o que a verificacao encontrou
    situacao: str = ""        # "" | "ok" | "atencao" | "erro"


def modelo() -> list[Item]:
    return [
        Item("audio", "Áudio sai pelo alto-falante", automatico=True),
        Item("rede", "Internet responde", automatico=True),
        Item("wifi", "Adaptador Wi-Fi presente", automatico=True),
        Item("camera", "Câmera reconhecida", automatico=True),
        Item("bateria", "Bateria em condição de uso", automatico=True),
        Item("tela", "Tela sem pixel morto nem mancha"),
        Item("teclado", "Todas as teclas respondem"),
        Item("usb", "Portas USB da frente e de trás"),
        Item("carregador", "Carregador e cabo devolvidos"),
        Item("dados", "Arquivos do cliente conferidos com ele"),
        Item("senha", "Senha de acesso informada ao cliente"),
    ]


def _json(consulta: str, tempo_limite: int = 120):
    saida = win.powershell(consulta, tempo_limite=tempo_limite)
    if not saida.ok or not saida.texto.strip():
        return []
    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []
    return [dados] if isinstance(dados, dict) else dados


def verificar(itens: list[Item], relatar=lambda _: None,
              percentual=lambda _: None) -> list[Item]:
    """Preenche os itens automaticos. Os manuais ficam intactos."""
    from . import rede as nucleo_rede
    from . import saude, wifi

    por_chave = {i.chave: i for i in itens}

    def marcar(chave, ok, texto, situacao=None):
        item = por_chave.get(chave)
        if item is None:
            return
        item.resultado = texto
        item.situacao = situacao or ("ok" if ok else "erro")
        item.marcado = bool(ok)

    relatar("Conferindo áudio...")
    percentual(15)
    audio = _json("Get-CimInstance Win32_SoundDevice "
                  "| Select-Object Name,Status | ConvertTo-Json -Compress")
    ativos = [d for d in audio if (d.get("Status") or "").lower() == "ok"]
    marcar("audio", bool(ativos),
           f"{len(ativos)} dispositivo(s) de áudio ativo(s)" if ativos
           else "nenhum dispositivo de áudio funcional")

    relatar("Testando a internet...")
    percentual(40)
    try:
        diagnostico = nucleo_rede.diagnosticar()
        falhas = [t for t in diagnostico.testes if t.situacao == "erro"]
        marcar("rede", not falhas,
               "todas as camadas responderam" if not falhas
               else f"{len(falhas)} camada(s) falharam")
    except OSError as erro:
        marcar("rede", False, str(erro))

    relatar("Procurando Wi-Fi...")
    percentual(60)
    tem_wifi, motivo = wifi.disponibilidade()
    # Desktop sem Wi-Fi nao e defeito: fica como observacao, nao como erro.
    marcar("wifi", tem_wifi, "adaptador presente" if tem_wifi else motivo,
           None if tem_wifi else "atencao")

    relatar("Procurando câmera...")
    percentual(75)
    camera = _json(
        "Get-CimInstance Win32_PnPEntity "
        "| Where-Object { $_.PNPClass -eq 'Camera' -or "
        "$_.PNPClass -eq 'Image' } | Select-Object Name,Status "
        "| ConvertTo-Json -Compress")
    marcar("camera", bool(camera),
           camera[0].get("Name", "reconhecida") if camera
           else "nenhuma câmera encontrada",
           None if camera else "atencao")

    relatar("Lendo a bateria...")
    percentual(90)
    b = saude.bateria()
    if not b.presente:
        marcar("bateria", True, "máquina sem bateria (desktop)", "ok")
    else:
        bom = b.saude_pct >= 50 if b.saude_pct else True
        marcar("bateria", bom,
               f"{b.saude_pct}% da capacidade original" if b.saude_pct
               else f"carga {b.carga_pct}%",
               "ok" if bom else "atencao")

    percentual(100)
    automaticos = [i for i in itens if i.automatico]
    relatar(f"{sum(1 for i in automaticos if i.marcado)} de "
            f"{len(automaticos)} verificações automáticas passaram.")
    return itens


# ---------------------------------------------------------------------
# PASTA DO CLIENTE
# ---------------------------------------------------------------------
@dataclass
class ResultadoExportacao:
    destino: str = ""
    copiados: list[str] = field(default_factory=list)
    falharam: list[str] = field(default_factory=list)


def exportar_pasta(destino, pdf_gerado: str = "", relatar=lambda _: None,
                   percentual=lambda _: None) -> ResultadoExportacao:
    """Junta num lugar so tudo que o cliente leva.

    A pesquisa sobre suporte aponta fragmentacao de ferramentas como uma
    das duas maiores dores: o PDF fica numa pasta, o backup em outra, os
    drivers num pendrive. Aqui vira uma pasta com nome do cliente e data,
    pronta para gravar em midia ou mandar por e-mail.
    """
    import shutil
    from datetime import date
    from pathlib import Path

    from . import dados, ficha, historico

    f = ficha.carregar()
    nome_cliente = "".join(
        c if c.isalnum() or c in " -_" else "_"
        for c in (f.cliente or historico.identidade()[0])).strip()

    raiz = Path(destino) / f"{nome_cliente} - {date.today():%Y-%m-%d}"
    r = ResultadoExportacao()
    try:
        raiz.mkdir(parents=True, exist_ok=True)
    except OSError as erro:
        r.destino = str(raiz)
        r.falharam.append(f"criar a pasta: {erro}")
        return r
    r.destino = str(raiz)

    def copiar(origem: Path, rotulo: str) -> None:
        try:
            if origem.is_dir():
                shutil.copytree(origem, raiz / origem.name, dirs_exist_ok=True)
            else:
                shutil.copy2(origem, raiz / origem.name)
            r.copiados.append(rotulo)
        except OSError as erro:
            r.falharam.append(f"{rotulo}: {erro}")

    percentual(15)
    if pdf_gerado:
        caminho = Path(pdf_gerado)
        if caminho.is_file():
            relatar("Copiando o relatório...")
            copiar(caminho, "relatório em PDF")

    percentual(40)
    relatar("Copiando o histórico desta máquina...")
    _nome, serie, _marca = historico.identidade()
    arquivo_historico = historico.pasta() / f"{serie}.jsonl"
    # O nome no disco passa pelo mesmo saneamento do historico.
    for candidato in historico.pasta().glob("*.jsonl"):
        if candidato.stem in serie or serie.replace(" ", "_") in candidato.stem:
            arquivo_historico = candidato
            break
    if arquivo_historico.is_file():
        copiar(arquivo_historico, "histórico de atendimentos")

    percentual(60)
    registro = dados.registro_da_sessao()
    if registro.is_file():
        relatar("Copiando o registro do dia...")
        copiar(registro, "registro da sessão")

    percentual(80)
    ficha_arquivo = dados.pasta("fichas")
    for candidato in ficha_arquivo.glob("*.json"):
        if candidato.stem in serie or serie.replace(" ", "_") in candidato.stem:
            copiar(candidato, "ficha de ordem de serviço")
            break

    percentual(100)
    relatar(f"{len(r.copiados)} item(ns) em {raiz}")
    return r


# ---------------------------------------------------------------------
# PERSISTENCIA
# ---------------------------------------------------------------------
def _arquivo():
    from . import dados, historico

    _nome, serie, _marca = historico.identidade()
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in serie)
    return dados.pasta("entregas") / f"{seguro or 'desconhecida'}.json"


def salvar(itens: list[Item]):
    """Grava o checklist para o PDF poder incluir sem acoplar os paineis.

    A tela de Entrega e a de Relatorios sao separadas, e passar o estado
    de uma para a outra por referencia amarraria as duas. O disco ja e o
    ponto de encontro de tudo o mais nesta ferramenta.
    """
    from dataclasses import asdict

    arquivo = _arquivo()
    arquivo.write_text(
        json.dumps([asdict(i) for i in itens], ensure_ascii=False, indent=2),
        encoding="utf-8")
    return arquivo


def carregar() -> list[Item]:
    arquivo = _arquivo()
    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return modelo()
    try:
        return [Item(**d) for d in bruto]
    except TypeError:
        return modelo()
