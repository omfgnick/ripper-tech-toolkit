"""Execucao em segundo plano.

Toda operacao que toca disco, rede ou processo do sistema roda aqui. A
interface nunca chama essas funcoes direto: um unico `sfc /scannow` que
demore 4 minutos na thread da UI congela a janela inteira, e o tecnico
acha que o app travou.
"""

from __future__ import annotations

import inspect
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class Sinais(QObject):
    """Sinais emitidos por uma tarefa.

    Precisam viver num QObject separado porque QRunnable nao herda de
    QObject e, portanto, nao pode declarar Signal.
    """

    progresso = Signal(str)          # linha de andamento legivel
    percentual = Signal(int)         # 0-100, ou -1 para indeterminado
    medida = Signal(float)           # leitura numerica ao vivo (ex.: Mbps)
    concluido = Signal(object)       # resultado
    falhou = Signal(str)             # mensagem de erro


class Tarefa(QRunnable):
    """Roda uma funcao no pool de threads e devolve o resultado por sinal.

    A funcao recebe `relatar` como primeiro argumento quando aceita - e
    assim que ela reporta andamento sem conhecer o Qt.
    """

    def __init__(self, funcao: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.funcao = funcao
        self.args = args
        self.kwargs = kwargs
        self.sinais = Sinais()
        self._cancelado = False

    def cancelar(self) -> None:
        self._cancelado = True

    @property
    def cancelado(self) -> bool:
        return self._cancelado

    @Slot()
    def run(self) -> None:  # noqa: D102 (assinatura do Qt)
        # Cada funcao recebe SO os callbacks que declara. Passar todos
        # incondicionalmente quebraria as que ainda nao conhecem `medida`,
        # e obrigaria a editar oito modulos para acrescentar um callback.
        disponiveis = {
            "relatar": self.sinais.progresso.emit,
            "percentual": self.sinais.percentual.emit,
            "medida": self.sinais.medida.emit,
            "cancelado": lambda: self._cancelado,
        }
        try:
            aceitos = inspect.signature(self.funcao).parameters
            injetados = {k: v for k, v in disponiveis.items() if k in aceitos}
        except (TypeError, ValueError):
            injetados = disponiveis

        try:
            resultado = self.funcao(*self.args, **injetados, **self.kwargs)
        except Exception as erro:  # noqa: BLE001
            # Um erro numa tarefa nao pode derrubar o app: o tecnico esta
            # na maquina do cliente e precisa continuar usando as outras
            # funcoes. O traceback vai para o log, a mensagem para a tela.
            detalhe = traceback.format_exc(limit=3)
            self.sinais.falhou.emit(f"{erro}\n\n{detalhe}")
        else:
            if not self._cancelado:
                self.sinais.concluido.emit(resultado)


def executar(funcao: Callable[..., Any], *args: Any, **kwargs: Any) -> Tarefa:
    """Atalho: cria a tarefa, enfileira e devolve para ligar os sinais."""
    tarefa = Tarefa(funcao, *args, **kwargs)
    QThreadPool.globalInstance().start(tarefa)
    return tarefa
