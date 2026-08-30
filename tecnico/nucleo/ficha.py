"""Ficha de ordem de servico: o lado humano do atendimento.

O historico identifica a maquina pelo numero de serie e os instantaneos
dizem o que mudou. Falta quem trouxe, o que reclamou e o que foi feito -
e e isso que o cliente le no PDF.

FICA GRAVADA JUNTO COM O HISTORICO
    Reaberta na proxima visita, ela responde "o que ele reclamou da outra
    vez", que costuma ser a mesma coisa. Uma ficha por maquina, sempre a
    ultima: guardar todas viraria arquivo morto sem tela para navegar.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date

from . import dados, historico


@dataclass
class Ficha:
    cliente: str = ""
    telefone: str = ""
    equipamento: str = ""
    defeito: str = ""          # o que o cliente relatou
    executado: str = ""        # o que o tecnico fez
    observacoes: str = ""
    tecnico: str = ""
    # Velocidade contratada, em Mbps. Fica na ficha por ser dado do
    # cliente, nao da maquina: o mesmo notebook em outra casa tem outro
    # plano, e o numero precisa acompanhar quem paga a conta.
    plano_mbps: float = 0.0
    abertura: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def vazia(self) -> bool:
        return not any((self.cliente, self.telefone, self.equipamento,
                        self.defeito, self.executado, self.observacoes))


def _arquivo() -> "object":
    _nome, serie, _marca = historico.identidade()
    seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in serie)
    return dados.pasta("fichas") / f"{seguro or 'desconhecida'}.json"


def carregar() -> Ficha:
    """A ultima ficha desta maquina, ou uma em branco."""
    arquivo = _arquivo()
    try:
        dados_ = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Ficha()
    try:
        return Ficha(**dados_)
    except TypeError:
        # Ficha gravada por uma versao com outros campos. Melhor comecar
        # limpa do que estourar na abertura do painel.
        return Ficha()


def salvar(ficha: Ficha) -> "object":
    arquivo = _arquivo()
    arquivo.write_text(json.dumps(asdict(ficha), ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return arquivo
