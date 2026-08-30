"""Ponte com o Windows: executa comandos sem piscar console.

Todo subprocesso do app passa por aqui. Sem CREATE_NO_WINDOW, cada
consulta abre e fecha um console preto na frente do cliente - o app
parece estar fazendo algo escondido, que e exatamente a impressao que um
utilitario de suporte nao pode dar.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

SEM_JANELA = 0x08000000  # CREATE_NO_WINDOW


@dataclass
class Saida:
    codigo: int
    texto: str
    erro: str

    @property
    def ok(self) -> bool:
        return self.codigo == 0


def rodar(comando: list[str], tempo_limite: int = 60,
          codificacao: str = "oem") -> Saida:
    """Executa um comando e devolve a saida. Nunca levanta excecao por
    codigo de retorno - quem chama decide o que fazer com a falha.

    A codificacao padrao e "oem" e nao utf-8: ipconfig, ping e netsh
    escrevem na codepage do console (850 no Brasil). Decodificar como
    utf-8 embaralha todo acento e qualquer regex sobre o texto falha."""
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding=codificacao,
            errors="replace",
            timeout=tempo_limite,
            creationflags=SEM_JANELA,
        )
        return Saida(proc.returncode, proc.stdout or "", proc.stderr or "")
    except subprocess.TimeoutExpired:
        return Saida(-1, "", f"Tempo esgotado após {tempo_limite}s.")
    except FileNotFoundError:
        return Saida(-1, "", f"Comando não encontrado: {comando[0]}")
    except Exception as erro:  # noqa: BLE001
        return Saida(-1, "", str(erro))


def powershell(script: str, tempo_limite: int = 60) -> Saida:
    return rodar(
        [
            "powershell", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-Command", script,
        ],
        tempo_limite,
        codificacao="utf-8",
    )


def consultar(classe: str, campos: list[str], tempo_limite: int = 30) -> list[dict]:
    """Consulta CIM e devolve lista de dicionarios.

    Usa Get-CimInstance e nao o wmic: o wmic esta descontinuado e ja nao
    vem habilitado por padrao em instalacoes recentes do Windows 11.
    """
    selecao = ", ".join(campos)
    script = (
        f"Get-CimInstance -ClassName {classe} -ErrorAction SilentlyContinue | "
        f"Select-Object {selecao} | ConvertTo-Json -Compress -Depth 3"
    )
    saida = powershell(script, tempo_limite)
    if not saida.ok or not saida.texto.strip():
        return []

    try:
        dados = json.loads(saida.texto)
    except json.JSONDecodeError:
        return []

    # ConvertTo-Json devolve objeto solto quando ha um unico resultado.
    if isinstance(dados, dict):
        return [dados]
    return [d for d in dados if isinstance(d, dict)]


def formatar_bytes(n: float | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unidade == "TB":
            casas = 0 if unidade in ("B", "KB") else 1
            return f"{n:.{casas}f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"
