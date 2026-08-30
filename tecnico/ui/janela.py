"""Janela principal: barra lateral de navegacao e pilha de paineis."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QApplication,
    QHBoxLayout,
    QMessageBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..nucleo import admin
from ..tema import (
    Cor,
    Fonte,
    aplicar_tema,
    familia,
    folha_de_estilo,
    gravar_tema,
    tema_atual,
)
from .widgets import Botao
from .bandeja import Bandeja
from .efeitos import Sobreposicao
from .hud import Avisos, FaixaStatus
from .paineis.diagnostico import PainelDiagnostico
from .paineis.entrega import PainelEntrega
from .paineis.historico import PainelHistorico
from .paineis.inicio import PainelInicio
from .paineis.limpeza import PainelLimpeza
from .paineis.manutencao import PainelManutencao
from .paineis.programas import PainelProgramas
from .paineis.rede import PainelRede
from .paineis.relatorios import PainelRelatorios
from .paineis.reparo import PainelReparo
from .paineis.roteiro import PainelRoteiro

APLICATIVO = "Ripper"
VERSAO = "1.0"


class BotaoNavegacao(QPushButton):
    """Item da barra lateral.

    Selecionado vira bloco amarelo solido com texto preto - a inversao e
    a marca do menu do jogo, e resolve de longe qual tela esta aberta.
    """

    def __init__(self, texto: str, parent=None):
        super().__init__(texto.upper(), parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {Cor.TEXTO_SUAVE};
                border: none;
                border-left: 3px solid transparent;
                padding: 7px 14px;
                text-align: left;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: {Cor.PAINEL_ALTO};
                color: {Cor.DESTAQUE};
            }}
            QPushButton:checked {{
                background: {Cor.DESTAQUE_BLOCO};
                color: {Cor.SOBRE_DESTAQUE};
                border-left: 3px solid {Cor.DESTAQUE_FORTE};
            }}
            """
        )


class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APLICATIVO} {VERSAO}")
        self.resize(1080, 660)
        self.setMinimumSize(900, 580)
        self.setStyleSheet(folha_de_estilo())

        # Camada de efeito por cima de tudo. Criada aqui e nao no
        # final para existir antes do primeiro resizeEvent.
        self.sobreposicao: Sobreposicao | None = None
        # Fechar recolhe para a bandeja; so o menu do icone e a
        # troca de tema encerram de verdade.
        self.encerrar_de_verdade = False
        self.bandeja: Bandeja | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {Cor.FUNDO};")
        self.setCentralWidget(central)

        linha = QHBoxLayout(central)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)

        linha.addWidget(self._lateral())

        self.pilha = QStackedWidget()
        self.pilha.setStyleSheet(f"background: {Cor.FUNDO_ALTO};")
        # Faixa de status acima da pilha: ela vale para todos os paineis
        # e por isso mora na janela, nao dentro de cada tela.
        direita = QWidget()
        coluna_direita = QVBoxLayout(direita)
        coluna_direita.setContentsMargins(0, 0, 0, 0)
        coluna_direita.setSpacing(0)

        self.faixa = FaixaStatus()
        coluna_direita.addWidget(self.faixa)
        coluna_direita.addWidget(self.pilha, 1)
        linha.addWidget(direita, 1)

        self.avisos = Avisos(self)
        self._preencher_faixa()

        # Ordem da pilha acompanha a ordem dos botoes: o indice e o
        # contrato entre os dois, e trocar um sem o outro quebra a
        # navegacao de forma silenciosa.
        self.paineis = {
            "inicio": PainelInicio(),
            "roteiro": PainelRoteiro(),
            "diagnostico": PainelDiagnostico(),
            "limpeza": PainelLimpeza(),
            "rede": PainelRede(),
            "programas": PainelProgramas(),
            "reparo": PainelReparo(),
            "manutencao": PainelManutencao(),
            "relatorios": PainelRelatorios(),
            "entrega": PainelEntrega(),
            "historico": PainelHistorico(),
        }
        for painel in self.paineis.values():
            self.pilha.addWidget(painel)

        self.paineis["inicio"].ir_para.connect(self.mostrar)
        self.paineis["relatorios"].ir_para.connect(self.mostrar)
        self.mostrar("inicio")
        self._montar_bandeja()

    def _montar_bandeja(self) -> None:
        """Cria o icone da area de notificacao, se o sistema tiver uma.

        Windows Server sem shell grafico e sessao remota mal configurada
        nao tem bandeja. Sem a checagem, o icone some em silencio e o
        fechar recolheria a janela para lugar nenhum.
        """
        from PySide6.QtWidgets import QSystemTrayIcon

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.bandeja = Bandeja(self, APLICATIVO)
        self.bandeja.show()

    def _preencher_faixa(self) -> None:
        from ..nucleo import dados, historico

        try:
            nome, serie, marca = historico.identidade()
        except OSError:
            nome, serie, marca = "?", "", ""
        # Nome e serie bastam na faixa: o modelo completo ja aparece no
        # Diagnostico e no Historico, e aqui so roubaria espaco da
        # operacao em curso.
        self.faixa.definir_maquina(f"{nome}  ·  {serie[:20]}")
        self.faixa.definir_modo(
            ("admin" if admin.e_administrador() else "padrão")
            + ("  ·  pendrive" if dados.portatil() else ""))

    def notificar(self, texto: str, tipo: str = "info") -> None:
        self.avisos.mostrar(texto, tipo)

    def operacao(self, texto: str) -> None:
        self.faixa.definir_operacao(texto)

    # ------------------------------------------------------------------
    def _lateral(self) -> QWidget:
        barra = QFrame()
        barra.setFixedWidth(208)
        barra.setStyleSheet(
            f"background: {Cor.FUNDO}; border-right: 1px solid {Cor.BORDA_SUAVE};"
        )

        coluna = QVBoxLayout(barra)
        coluna.setContentsMargins(0, 18, 0, 14)
        coluna.setSpacing(2)

        marca = QLabel(f"  {APLICATIVO}")
        f = QFont(familia(), 13)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 3.0)
        marca.setFont(f)
        marca.setStyleSheet(f"color: {Cor.TEXTO}; padding: 0 14px 2px 14px;")
        coluna.addWidget(marca)

        situacao = QLabel(
            "  Modo administrador" if admin.e_administrador()
            else "  Modo padrão"
        )
        situacao.setFont(QFont(Fonte.FAMILIA, 8))
        situacao.setStyleSheet(
            f"color: {Cor.OK if admin.e_administrador() else Cor.ATENCAO};"
            f"padding: 0 14px 16px 14px;"
        )
        coluna.addWidget(situacao)

        # A funcao de elevar ja existia no nucleo e nao tinha como ser
        # acionada: o app so informava "Modo padrao" e o tecnico tinha de
        # fechar e reabrir na mao. Sem admin, exportar drivers, ler senhas
        # de Wi-Fi, ver SMART e criar ponto de restauracao falham.
        if not admin.e_administrador():
            self.btn_elevar = Botao("Reabrir como admin", "primario")
            self.btn_elevar.setToolTip(
                "Fecha esta janela e abre outra elevada, pedindo o UAC.")
            self.btn_elevar.clicked.connect(self.elevar)
            recuo = QHBoxLayout()
            recuo.setContentsMargins(12, 6, 12, 8)
            recuo.addWidget(self.btn_elevar)
            coluna.addLayout(recuo)

        self.botoes: dict[str, BotaoNavegacao] = {}
        itens = [
            ("inicio", "Início"),
            ("roteiro", "Roteiro"),
            ("diagnostico", "Diagnóstico"),
            ("limpeza", "Limpeza"),
            ("rede", "Rede"),
            ("programas", "Programas"),
            ("reparo", "Reparo"),
            ("manutencao", "Manutenção"),
            ("relatorios", "Relatórios"),
            ("entrega", "Entrega"),
            ("historico", "Histórico"),
        ]
        for chave, rotulo in itens:
            b = BotaoNavegacao(rotulo)
            b.clicked.connect(lambda _=False, c=chave: self.mostrar(c))
            coluna.addWidget(b)
            self.botoes[chave] = b

        coluna.addStretch(1)

        self.btn_tema = Botao(
            "Tema claro" if tema_atual() == "escuro" else "Tema escuro")
        self.btn_tema.setToolTip(
            "Troca entre claro e escuro. A janela é remontada, então "
            "resultados na tela se perdem.")
        self.btn_tema.clicked.connect(self.alternar_tema)
        recuo_tema = QHBoxLayout()
        recuo_tema.setContentsMargins(12, 6, 12, 6)
        recuo_tema.addWidget(self.btn_tema)
        coluna.addLayout(recuo_tema)

        rodape = QLabel(f"  versão {VERSAO}")
        rodape.setFont(QFont(Fonte.MONO, 8))
        rodape.setStyleSheet(f"color: {Cor.TEXTO_FRACO}; padding: 0 14px;")
        coluna.addWidget(rodape)

        return barra

    # ------------------------------------------------------------------
    def mostrar(self, chave: str) -> None:
        painel = self.paineis.get(chave)
        if painel is None:
            return
        trocou = self.pilha.currentWidget() is not painel
        self.pilha.setCurrentWidget(painel)
        for c, b in self.botoes.items():
            b.setChecked(c == chave)

        # Glitch so quando a tela muda de verdade. Clicar de novo no item
        # ja aberto nao e um evento, e piscar ali seria ruido gratuito.
        if trocou and self.sobreposicao is not None:
            self.sobreposicao.disparar_glitch()

    def _garantir_sobreposicao(self) -> None:
        if self.sobreposicao is None:
            self.sobreposicao = Sobreposicao(self)
        self.sobreposicao.setGeometry(self.centralWidget().geometry())
        self.sobreposicao.raise_()

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        self._garantir_sobreposicao()
        self.sobreposicao.show()

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        if self.sobreposicao is not None:
            self._garantir_sobreposicao()
        if getattr(self, "avisos", None) is not None:
            self.avisos._reposicionar()

    def paineis_ocupados(self) -> list:
        """Paineis com tarefa em andamento.

        getattr com padrao, e nao `p.ocupado` direto: PainelInicio nao
        herda de PainelBase e nao tem essa propriedade. Assumir interface
        uniforme derrubou o app ao clicar em trocar o tema, e o teste de
        fumaca nao pegou porque `alternar_tema` remonta a janela e por
        isso esta fora dele. Este metodo existe para ser testavel sem
        remontar nada.
        """
        return [p for p in self.paineis.values()
                if getattr(p, "ocupado", False)]

    def alternar_tema(self) -> None:
        """Troca a paleta e remonta a janela.

        Remontar em vez de repintar: 49 lugares fixam a cor num
        stylesheet no construtor, e religar todos custaria muito mais
        risco do que reconstruir uma tela que se troca uma vez por dia.
        """
        if self.paineis_ocupados():
            QMessageBox.information(
                self, "Trocar tema",
                "Há uma operação em andamento." + chr(10) + chr(10)
                + "Trocar o tema remonta a janela e o resultado se perderia. "
                "Espere terminar.")
            return

        novo = "claro" if tema_atual() == "escuro" else "escuro"
        aplicar_tema(novo)
        gravar_tema(novo)

        aplicacao = QApplication.instance()
        if aplicacao is not None:
            aplicacao.setStyleSheet("")
        # A janela nova nasce com a paleta ja trocada; a antiga sai depois
        # de a nova aparecer, para nao piscar a area de trabalho.
        nova = Janela()
        nova.resize(self.size())
        nova.move(self.pos())
        nova.show()
        self._substituta = nova
        aplicacao.setProperty("janela_ripper", nova)
        # Sem isto o fechar recolheria a janela velha para a bandeja e o
        # tecnico ficaria com duas, uma escondida.
        self.encerrar_de_verdade = True
        if self.bandeja is not None:
            self.bandeja.hide()
        self.close()

    def elevar(self) -> None:
        """Pede elevacao e fecha esta instancia se o UAC for aceito."""
        if admin.reabrir_como_administrador():
            # Fechar so depois do aceite: se o tecnico cancelar o UAC, a
            # janela atual continua util em vez de sumir sem aviso.
            self.close()
        else:
            QMessageBox.warning(
                self, "Elevação recusada",
                "O Windows não autorizou a abertura como administrador.")

    def closeEvent(self, evento) -> None:  # noqa: N802
        """Recolhe para a bandeja, ou encerra esperando as tarefas.

        O fechar padrao passou a recolher: numa bancada o app fica aberto
        entre um atendimento e outro, e reabrir a cada vez e uma chance de
        rodar duas copias por engano. Sair de verdade e escolha explicita
        no menu do icone.

        Sem isto, fechar a janela durante uma varredura faz a tarefa
        emitir sinal para um objeto ja destruido e o app termina com
        "Signal source has been deleted" - erro que o tecnico veria como
        travamento na maquina do cliente.
        """
        if self.bandeja is not None and not self.encerrar_de_verdade:
            evento.ignore()
            self.bandeja.recolher()
            return

        pool = QThreadPool.globalInstance()
        if pool.activeThreadCount():
            for painel in self.paineis.values():
                tarefa = getattr(painel, "_tarefa", None)
                if tarefa is not None:
                    tarefa.cancelar()
            # 5 s cobre o cancelamento; passar disso e melhor sair do que
            # deixar a janela presa na tela.
            pool.waitForDone(5000)
        super().closeEvent(evento)

    def iniciar_verificacao(self) -> None:
        """Chamado apos a janela aparecer: a verificacao da tela inicial
        so comeca com a interface ja visivel, senao o app fica alguns
        segundos em branco antes de desenhar."""
        self.paineis["inicio"].verificar()
