"""Ferramentas de reparo do Windows.

TODA acao aqui altera o sistema. Por isso:

  - nenhuma roda sozinha: a interface exige confirmacao explicita;
  - o comando exato aparece na tela antes de executar - o tecnico precisa
    poder dizer ao cliente o que foi feito na maquina dele;
  - `exige_admin` e `exige_reinicio` sao declarados aqui, e nao decididos
    pela tela, para nao existir versao "sem aviso" em outro lugar.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import win


@dataclass
class Acao:
    chave: str
    titulo: str
    descricao: str
    comando: list[str]
    exige_admin: bool = True
    exige_reinicio: bool = False
    demorada: bool = False
    tempo_limite: int = 900


ACOES: list[Acao] = [
    Acao("sfc", "Verificar arquivos do sistema (SFC)",
         "Procura arquivos do Windows corrompidos e repara pelo cache local. "
         "Costuma levar de 5 a 15 minutos.",
         ["sfc", "/scannow"], demorada=True),

    Acao("dism", "Reparar imagem do Windows (DISM)",
         "Corrige o próprio cache que o SFC usa. Rode antes do SFC quando o "
         "SFC falhar. Precisa de internet.",
         ["dism", "/online", "/cleanup-image", "/restorehealth"], demorada=True),

    Acao("chkdsk", "Verificar disco (CHKDSK)",
         "Procura erros no sistema de arquivos do C:. Somente leitura — não "
         "corrige nada sem /f.",
         ["chkdsk", "C:"], demorada=True, tempo_limite=1800),

    Acao("chkdsk_corrigir", "Agendar correção do disco (CHKDSK /F)",
         "Marca o C: para verificação COM correção no próximo boot. O "
         "Windows não consegue corrigir o disco do sistema em uso, então a "
         "checagem roda antes de ele carregar. Pode demorar bastante.",
         ["powershell", "-NoProfile", "-Command",
          # `echo S` responde a pergunta de agendamento. O chkdsk pergunta
          # em portugues (S) e em ingles (Y); mandar as duas letras cobre
          # os dois casos sem depender do idioma da maquina.
          "cmd /c \"echo S&echo Y| chkdsk C: /F\""],
         exige_reinicio=True, tempo_limite=300),

    Acao("limpar_spooler", "Limpar fila de impressão",
         "Para o spooler, descarta TODOS os trabalhos pendentes de todas as "
         "impressoras e religa. Resolve fila travada por documento com erro.",
         ["powershell", "-NoProfile", "-Command",
          "Stop-Service Spooler -Force; "
          r'Remove-Item "$env:WINDIR\System32\spool\PRINTERS\*" -Recurse '
          "-Force -ErrorAction SilentlyContinue; Start-Service Spooler"],
         tempo_limite=180),

    Acao("ponto_restauracao", "Criar ponto de restauração",
         "Salva o estado atual do sistema. Faça isto ANTES de qualquer "
         "alteração grande.",
         ["powershell", "-NoProfile", "-Command",
          "Checkpoint-Computer -Description 'Atendimento tecnico' "
          "-RestorePointType MODIFY_SETTINGS"], tempo_limite=300),

    Acao("reset_rede", "Redefinir toda a pilha de rede",
         "Winsock, TCP/IP, cache DNS e IP. Use quando nada de rede funciona.",
         ["powershell", "-NoProfile", "-Command",
          "netsh winsock reset; netsh int ip reset; ipconfig /flushdns; "
          "ipconfig /release; ipconfig /renew"],
         exige_reinicio=True, tempo_limite=300),

    Acao("reset_windows_update", "Redefinir o Windows Update",
         "Para os serviços, limpa o cache de downloads e religa. Resolve "
         "atualização travada em porcentagem.",
         ["powershell", "-NoProfile", "-Command",
          "Stop-Service wuauserv,bits -Force -ErrorAction SilentlyContinue; "
          r'Remove-Item "$env:WINDIR\SoftwareDistribution\Download\*" '
          "-Recurse -Force -ErrorAction SilentlyContinue; "
          "Start-Service wuauserv,bits -ErrorAction SilentlyContinue"],
         tempo_limite=600),

    Acao("reindexar", "Reconstruir índice de busca",
         "Recria o índice do Windows Search. Resolve busca do menu Iniciar "
         "que não encontra nada.",
         ["powershell", "-NoProfile", "-Command",
          "Stop-Service WSearch -Force -ErrorAction SilentlyContinue; "
          r'Remove-Item "$env:ProgramData\Microsoft\Search\Data" -Recurse '
          "-Force -ErrorAction SilentlyContinue; "
          "Start-Service WSearch -ErrorAction SilentlyContinue"],
         tempo_limite=300),
]


def por_chave(chave: str) -> Acao:
    for a in ACOES:
        if a.chave == chave:
            return a
    raise KeyError(chave)


def executar(chave: str, relatar=lambda _: None, percentual=lambda _: None,
             cancelado=lambda: False) -> str:
    acao = por_chave(chave)

    if chave in COM_PONTO_AUTOMATICO:
        feito, motivo = criar_ponto(f"Ripper - antes de {acao.titulo}", relatar)
        if not feito:
            # Segue mesmo assim: o tecnico pediu o reparo. Mas fica escrito
            # no registro que a volta atras nao esta garantida.
            relatar(f"AVISO: sem ponto de restauração ({motivo}).")

    relatar(f"Comando: {' '.join(acao.comando)}")
    if acao.demorada:
        relatar("Esta operação é demorada. Não feche o aplicativo.")
    # Indeterminado: sfc e dism nao reportam progresso de forma legivel,
    # e uma barra que finge saber a porcentagem seria mentira.
    percentual(-1)

    saida = win.rodar(acao.comando, acao.tempo_limite)
    texto = (saida.texto or "").strip()
    if saida.erro.strip():
        texto += ("\n\n" if texto else "") + saida.erro.strip()

    relatar(f"{acao.titulo}: {'concluído' if saida.ok else 'terminou com erro'}")
    if acao.exige_reinicio:
        relatar("REINICIE a máquina para que a alteração tenha efeito.")

    return texto or "(sem saída)"


# ---------------------------------------------------------------------
# PONTO DE RESTAURACAO AUTOMATICO
# ---------------------------------------------------------------------
# Acoes que mexem no sistema e merecem uma rede de seguranca antes.
# chkdsk sem /f e so leitura, e criar ponto antes de criar ponto seria
# recursao boba - por isso a lista e explicita.
COM_PONTO_AUTOMATICO = {
    "sfc", "dism", "reset_rede", "reset_windows_update", "reindexar",
    "chkdsk_corrigir",
}


def _ultimo_ponto() -> str:
    """Assinatura do ponto mais recente: "sequencia|data", ou vazia.

    Devolve vazio tambem quando falta permissao - Get-ComputerRestorePoint
    nao enxerga nada sem elevacao e nao reclama. Por isso quem usa isto
    precisa ter checado admin antes, ou vai concluir que a maquina nao tem
    ponto nenhum quando na verdade so nao pode ver.
    """
    saida = win.powershell(
        "Get-ComputerRestorePoint | Select-Object -Last 1 "
        "| ForEach-Object { \"$($_.SequenceNumber)|$($_.CreationTime)\" }",
        tempo_limite=120)
    return saida.texto.strip() if saida.ok else ""


def _horas_desde(assinatura: str) -> float | None:
    """Idade do ponto, em horas, a partir da assinatura do WMI.

    A data vem no formato CIM_DATETIME: 20260829055936.969312-000, que e
    AAAAMMDDhhmmss seguido de fracao e fuso. Sem parsear isso nao da para
    distinguir "protecao desligada" de "ja teve ponto hoje".
    """
    from datetime import datetime

    if "|" not in (assinatura or ""):
        return None
    bruto = assinatura.split("|", 1)[1].strip()
    carimbo = bruto.split(".")[0]
    if len(carimbo) < 14 or not carimbo[:14].isdigit():
        return None
    try:
        quando = datetime.strptime(carimbo[:14], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return (datetime.now() - quando).total_seconds() / 3600


def protecao_ativa() -> bool | None:
    """Se ha unidade com Protecao do Sistema ligada.

    None significa "nao deu para saber": esta consulta tambem exige
    elevacao, e responder False sem poder ver seria afirmar que a protecao
    esta desligada quando ela pode estar perfeitamente ativa.
    """
    saida = win.powershell(
        r"(Get-CimInstance -Namespace root\default -ClassName SystemRestore "
        r"-ErrorAction SilentlyContinue | Measure-Object).Count",
        tempo_limite=120)
    if not saida.ok or not saida.texto.strip().isdigit():
        return None
    return int(saida.texto.strip()) > 0


def criar_ponto(descricao: str = "Ripper - antes do reparo",
                relatar=lambda _: None) -> tuple[bool, str]:
    """Cria um ponto e CONFERE se ele existe mesmo.

    Checkpoint-Computer devolve sucesso mesmo quando nao cria nada: o
    Windows ignora pedidos se ja houve um ponto nas ultimas 24 horas, e
    faz o mesmo silenciosamente quando a Protecao do Sistema esta
    desligada - o que e o padrao em boa parte das maquinas de fabrica.

    Confiar no codigo de retorno faria o app prometer uma rede de
    seguranca que nao existe. Por isso comparamos o ultimo ponto antes e
    depois: se nao mudou, nao houve ponto, e o tecnico precisa saber.
    """
    from . import admin

    if not admin.e_administrador():
        return False, "sem privilégio de administrador"

    antes = _ultimo_ponto()
    relatar("Criando ponto de restauração...")
    win.powershell(
        f"Checkpoint-Computer -Description '{descricao}' "
        "-RestorePointType MODIFY_SETTINGS", tempo_limite=300)
    depois = _ultimo_ponto()

    if depois and depois != antes:
        relatar("Ponto de restauração criado.")
        return True, "criado"

    # Sem isto a mensagem oferecia as duas hipoteses sem distinguir, e o
    # tecnico ia caçar uma protecao desativada que estava ligada o tempo
    # todo. O autoteste elevado mostrou exatamente esse caso: ponto de
    # ontem as 05:59 e o Windows recusando criar outro no mesmo dia.
    idade = _horas_desde(depois or antes)
    if idade is not None and idade < 24:
        return False, (f"já existe um ponto de {idade:.0f}h atrás. O Windows "
                       "cria no máximo um por dia — a rede de segurança "
                       "existe, só não é de agora")

    ativa = protecao_ativa()
    if ativa is False:
        return False, ("a Proteção do Sistema está desativada nesta máquina. "
                       "Ligue em Sistema › Proteção do sistema")
    if not (depois or antes):
        return False, ("nenhum ponto encontrado e a proteção não respondeu. "
                       "Verifique se a Proteção do Sistema está ligada")
    return False, "o Windows recusou criar o ponto e não informou o motivo"
