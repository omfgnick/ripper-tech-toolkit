"""Painel de rede: diagnostico e correcoes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QTreeWidget, QTreeWidgetItem

from ...nucleo import ficha as nucleo_ficha
from ...nucleo import rede, wifi
from ...tema import Cor
from ..velocimetro import Velocimetro
from ..widgets import Botao
from .base import PainelBase

# Funcao e nao constante: dicionario no topo do modulo congela as
# cores da paleta ativa na IMPORTACAO, e a troca de tema depois
# nao chega ate ele. Foi assim que o texto do botao sumiu no tema
# claro - continuava branco.
def cores() -> dict[str, str]:
    return {"ok": Cor.OK, "atencao": Cor.ATENCAO, "erro": Cor.ERRO}
SIMBOLOS = {"ok": "OK", "atencao": "!", "erro": "X"}


class PainelRede(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Rede",
            "Testa a conexão em camadas: adaptador, gateway, internet e "
            "resolução de nomes. Onde parar indica onde está o problema.",
            parent,
        )
        self.btn_testar = Botao("Testar conexão", "primario")
        self.btn_testar.clicked.connect(self.testar)
        self.acoes.addWidget(self.btn_testar)

        self.btn_velocidade = Botao("Medir velocidade")
        self.btn_velocidade.setToolTip(
            "Baixa 25 MB e cronometra. Consome dados do plano do cliente."
        )
        self.btn_velocidade.clicked.connect(self.medir_velocidade)
        self.acoes.addWidget(self.btn_velocidade)

        self.btn_wifi = Botao("Redes Wi-Fi")
        self.btn_wifi.setToolTip(
            "Mostra as redes ao alcance, o sinal de cada uma e quantas "
            "dividem o mesmo canal.")
        self.btn_wifi.clicked.connect(self.varrer_wifi)
        self.acoes.addWidget(self.btn_wifi)

        # O plano fica na ficha, junto do resto dos dados do cliente: e
        # dado de quem paga a conta, nao da maquina.
        from PySide6.QtWidgets import QLabel, QLineEdit

        rotulo_plano = QLabel("Plano (Mbps):")
        rotulo_plano.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.acoes.addWidget(rotulo_plano)

        self.campo_plano = QLineEdit()
        self.campo_plano.setFixedWidth(70)
        self.campo_plano.setPlaceholderText("300")
        self.campo_plano.setToolTip(
            "Velocidade contratada. Com ela o app compara o medido contra "
            "os pisos que a Anatel exige.")
        plano = nucleo_ficha.carregar().plano_mbps
        if plano:
            self.campo_plano.setText(f"{plano:.0f}")
        self.campo_plano.editingFinished.connect(self._guardar_plano)
        self.acoes.addWidget(self.campo_plano)

        self.acoes.addStretch(1)

        # Tabela e velocimetro lado a lado: a leitura ao vivo precisa
        # estar visivel enquanto a tabela vai sendo preenchida.
        meio = QHBoxLayout()
        meio.setSpacing(14)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(["", "Verificação", "Resultado"])
        self.arvore.setColumnWidth(0, 40)
        self.arvore.setColumnWidth(1, 220)
        meio.addWidget(self.arvore, 1)

        self.velocimetro = Velocimetro()
        # Tamanho fixo e alinhado ao topo: deixado esticar, o widget se
        # espalha pela coluna inteira e o rotulo de situacao desgruda do
        # mostrador.
        self.velocimetro.setFixedSize(264, 244)
        meio.addWidget(self.velocimetro, 0, Qt.AlignTop)

        self.conteudo.addLayout(meio)

        # ---- acoes que alteram a configuracao ----
        linha = QHBoxLayout()
        linha.setSpacing(8)
        for chave, (titulo, descricao, _cmd, exige_reinicio) in rede.ACOES.items():
            b = Botao(titulo, "perigo" if exige_reinicio else "normal")
            b.setToolTip(descricao)
            b.clicked.connect(lambda _=False, c=chave: self.aplicar(c))
            linha.addWidget(b)
        linha.addStretch(1)
        self.conteudo.addLayout(linha)

    def testar(self) -> None:
        if self.ocupado:
            return
        self.arvore.clear()
        self.btn_testar.setEnabled(False)
        self.rodar(rede.diagnosticar, self._pronto)

    def _pronto(self, diagnostico) -> None:
        self.btn_testar.setEnabled(True)
        for t in diagnostico.testes:
            item = QTreeWidgetItem(self.arvore,
                                   [SIMBOLOS.get(t.situacao, ""), t.rotulo, t.valor])
            cor = QBrush(QColor(cores().get(t.situacao, Cor.TEXTO)))
            item.setForeground(0, cor)
            if t.situacao != "ok":
                item.setForeground(2, cor)
            # A camada que falhou explica o que a falha DELA isola. Sem
            # isso o tecnico ve onde parou, mas nao o que ja pode excluir.
            if t.isola:
                filho = QTreeWidgetItem(item, ["", "", t.isola])
                filho.setForeground(2, QBrush(QColor(Cor.TEXTO_SUAVE)))
                item.setExpanded(True)

    def medir_velocidade(self) -> None:
        if self.ocupado:
            return
        self.btn_velocidade.setEnabled(False)
        self.velocimetro.iniciar("baixando...")
        self.anotar("Medindo velocidade (25 MB de download)...")
        tarefa = self.rodar(rede.testar_velocidade, self._velocidade_pronta)
        if tarefa is not None:
            # A funcao declara o callback `medida`; a Tarefa injeta so o
            # que a assinatura pede, entao as outras seguem intactas.
            tarefa.sinais.medida.connect(self.velocimetro.definir_valor)

    def _guardar_plano(self) -> None:
        """Grava na ficha da maquina, para nao redigitar no reatendimento."""
        try:
            valor = float(self.campo_plano.text().strip().replace(",", "."))
        except ValueError:
            return
        f = nucleo_ficha.carregar()
        if f.plano_mbps == valor:
            return
        f.plano_mbps = valor
        try:
            nucleo_ficha.salvar(f)
        except OSError:
            pass

    def _plano_atual(self) -> float:
        try:
            return float(self.campo_plano.text().strip().replace(",", "."))
        except ValueError:
            return 0.0

    def _velocidade_pronta(self, v) -> None:
        self.btn_velocidade.setEnabled(True)

        if v.erro:
            self.velocimetro.encerrar("falhou")
        else:
            self.velocimetro.definir_valor(v.download_mbps)
            self.velocimetro.encerrar(
                f"upload {v.upload_mbps:.0f} Mbps" if v.upload_mbps
                else "concluído")

        # Numero solto nao decide nada: 40 Mbps e otimo num plano de 50 e
        # pessimo num de 500. Com o plano informado, vira veredito.
        situacao, leitura = rede.avaliar_velocidade(
            v.download_mbps, self._plano_atual())
        if leitura:
            item = QTreeWidgetItem(
                self.arvore, [SIMBOLOS.get(situacao, ""),
                              "Entrega do provedor", leitura])
            cor = QBrush(QColor(cores().get(situacao, Cor.TEXTO)))
            item.setForeground(0, cor)
            item.setForeground(2, cor)

        if v.erro:
            item = QTreeWidgetItem(self.arvore, ["X", "Velocidade", v.erro])
            item.setForeground(0, QBrush(QColor(Cor.ERRO)))
            item.setForeground(2, QBrush(QColor(Cor.ERRO)))
            return

        # Abaixo de 10 Mbps a maioria das queixas de "internet lenta" se
        # explica sozinha; acima disso o problema costuma ser outro.
        situacao = "ok" if v.download_mbps >= 10 else "atencao"
        for rotulo, valor, sit in (
            ("Download", f"{v.download_mbps:.1f} Mbps", situacao),
            ("Upload", f"{v.upload_mbps:.1f} Mbps" if v.upload_mbps else "não medido", "ok"),
            ("Latência", f"{v.latencia_ms:.0f} ms" if v.latencia_ms else "—", "ok"),
        ):
            item = QTreeWidgetItem(self.arvore, [SIMBOLOS.get(sit, ""), rotulo, valor])
            cor = QBrush(QColor(cores().get(sit, Cor.TEXTO)))
            item.setForeground(0, cor)
            if sit != "ok":
                item.setForeground(2, cor)

    def aplicar(self, chave: str) -> None:
        if self.ocupado:
            return
        titulo, descricao, comando, exige_reinicio = rede.ACOES[chave]

        # O comando exato aparece na confirmacao: o tecnico precisa poder
        # dizer ao cliente o que foi rodado na maquina dele.
        aviso = "\n\nA máquina precisará ser REINICIADA." if exige_reinicio else ""
        if QMessageBox.question(
            self, titulo,
            f"{descricao}\n\nComando:\n  {' '.join(comando)}{aviso}\n\nExecutar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return

        self.rodar(rede.executar_acao, self._acao_pronta, chave)

    def _acao_pronta(self, saida: str) -> None:
        for linha in saida.splitlines()[:8]:
            if linha.strip():
                self.anotar("  " + linha.strip())

    # ------------------------------------------------------------------
    def varrer_wifi(self) -> None:
        if self.ocupado:
            return
        self.btn_wifi.setEnabled(False)
        self.rodar(wifi.redes, self._wifi_pronto)

    def _wifi_pronto(self, resultado) -> None:
        self.btn_wifi.setEnabled(True)
        lista, motivo = resultado

        if motivo:
            self.anotar(motivo)
            return
        if not lista:
            self.anotar("Nenhuma rede ao alcance.")
            return

        disputa = wifi.canais_disputados(lista)
        raiz = QTreeWidgetItem(
            self.arvore, ["", f"Wi-Fi — {len(lista)} rede(s)", ""])
        raiz.setForeground(1, QBrush(QColor(Cor.DESTAQUE)))

        for r in lista:
            vizinhas = disputa.get(r.canal, 1)
            detalhe = f"{r.sinal}%"
            if r.canal:
                detalhe += f" · canal {r.canal}"
                if r.faixa:
                    detalhe += f" ({r.faixa})"
            if r.autenticacao:
                detalhe += f" · {r.autenticacao}"

            item = QTreeWidgetItem(raiz, ["", r.ssid, detalhe])
            # Canal com quatro ou mais redes ja degrada de forma
            # perceptivel; e a explicacao mais comum para "internet lenta"
            # que o teste de velocidade sozinho nao revela.
            if vizinhas >= 4:
                item.setForeground(2, QBrush(QColor(Cor.ATENCAO)))
                item.setToolTip(
                    2, f"{vizinhas} redes dividindo o canal {r.canal}.")
        raiz.setExpanded(True)

        congestionados = [f"canal {c}: {n} redes"
                          for c, n in disputa.items() if n >= 4]
        if congestionados:
            self.anotar("Canais disputados — " + "; ".join(congestionados))
