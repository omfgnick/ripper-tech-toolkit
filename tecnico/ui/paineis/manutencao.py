"""Painel de manutencao: instalacao em lote e backup de perfil."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ...nucleo import ativacao, drivers, manutencao, wifi
from ...nucleo.win import formatar_bytes
from ...tema import Cor
from ..widgets import Botao, colunas_mono
from .base import PainelBase


class PainelManutencao(PainelBase):
    def __init__(self, parent=None):
        super().__init__(
            "Manutenção",
            "Instalação em lote, cópia do perfil e o que precisa sair da "
            "máquina antes de formatar.",
            parent,
        )
        self._pastas: list[manutencao.Pasta] = []
        self._destino = ""

        self.abas = QTabWidget()
        self.abas.setStyleSheet(
            f"QTabBar::tab {{ background: {Cor.PAINEL}; color: {Cor.TEXTO_SUAVE};"
            f" padding: 7px 16px; border: none; }}"
            f"QTabBar::tab:selected {{ color: {Cor.TEXTO};"
            f" border-bottom: 2px solid {Cor.DESTAQUE}; }}"
            f"QTabWidget::pane {{ border: none; }}"
        )
        self.abas.addTab(self._aba_instalacao(), "Instalação")
        self.abas.addTab(self._aba_backup(), "Backup de perfil")
        self.abas.addTab(self._aba_preformatacao(), "Pré-formatação")
        self.abas.addTab(self._aba_ativacao(), "Ativação")
        self.conteudo.addWidget(self.abas)

    # ------------------------------------------------------------------
    def _aba_instalacao(self) -> QWidget:
        aba = QWidget()
        coluna = QHBoxLayout(aba)
        coluna.setContentsMargins(0, 12, 0, 0)

        self.lista_programas = QTreeWidget()
        self.lista_programas.setHeaderLabels(["Programa", "Categoria"])
        self.lista_programas.setColumnWidth(0, 320)

        for p in manutencao.CATALOGO:
            item = QTreeWidgetItem(self.lista_programas, [p.nome, p.categoria])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if p.padrao else Qt.Unchecked)
            item.setData(0, Qt.UserRole, p.id_winget)
            item.setToolTip(0, p.id_winget)

        coluna.addWidget(self.lista_programas)

        lado = QWidget()
        lado.setFixedWidth(210)
        from PySide6.QtWidgets import QVBoxLayout
        v = QVBoxLayout(lado)
        v.setContentsMargins(14, 0, 0, 0)
        v.setSpacing(8)

        self.aviso_winget = QLabel()
        self.aviso_winget.setWordWrap(True)
        v.addWidget(self.aviso_winget)

        self.btn_instalar = Botao("Instalar marcados", "primario")
        self.btn_instalar.clicked.connect(self.instalar)
        v.addWidget(self.btn_instalar)
        v.addStretch(1)
        coluna.addWidget(lado)

        # Checa uma vez na montagem: winget falta em Windows 10 antigo e em
        # imagem LTSC, e oferecer um botao que sempre falha e pior que
        # dizer de saida que a ferramenta nao esta ali.
        if manutencao.winget_disponivel():
            self.aviso_winget.setText("winget disponível.")
            self.aviso_winget.setStyleSheet(f"color: {Cor.OK};")
        else:
            self.aviso_winget.setText(
                "winget não encontrado. Instale o 'Instalador de Aplicativo' "
                "pela Microsoft Store para usar esta aba.")
            self.aviso_winget.setStyleSheet(f"color: {Cor.ATENCAO};")
            self.btn_instalar.setEnabled(False)

        return aba

    def _aba_backup(self) -> QWidget:
        from PySide6.QtWidgets import QVBoxLayout
        aba = QWidget()
        v = QVBoxLayout(aba)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        linha = QHBoxLayout()
        self.btn_medir = Botao("Medir pastas", "primario")
        self.btn_medir.clicked.connect(self.medir)
        linha.addWidget(self.btn_medir)

        self.btn_destino = Botao("Escolher destino")
        self.btn_destino.clicked.connect(self.escolher_destino)
        linha.addWidget(self.btn_destino)

        self.btn_copiar = Botao("Copiar", "perigo")
        self.btn_copiar.setEnabled(False)
        self.btn_copiar.clicked.connect(self.copiar)
        linha.addWidget(self.btn_copiar)
        linha.addStretch(1)
        v.addLayout(linha)

        self.resumo_backup = QLabel("Nenhuma medição feita.")
        self.resumo_backup.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
        self.resumo_backup.setWordWrap(True)
        v.addWidget(self.resumo_backup)

        self.lista_pastas = QTreeWidget()
        self.lista_pastas.setHeaderLabels(["Pasta", "Arquivos", "Tamanho"])
        self.lista_pastas.setColumnWidth(0, 300)
        colunas_mono(self.lista_pastas, 1, 2)
        self.lista_pastas.itemChanged.connect(self._marcacao_mudou)
        v.addWidget(self.lista_pastas)

        return aba

    # ------------------------------------------------------------------
    # INSTALACAO
    # ------------------------------------------------------------------
    def _marcados(self) -> list[str]:
        ids = []
        for i in range(self.lista_programas.topLevelItemCount()):
            item = self.lista_programas.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                ids.append(item.data(0, Qt.UserRole))
        return ids

    def instalar(self) -> None:
        if self.ocupado:
            return
        ids = self._marcados()
        if not ids:
            self.anotar("Nenhum programa marcado.")
            return

        # Mesma regra dos reparos: mostrar o comando exato antes de rodar.
        # O tecnico assina o que vai acontecer na maquina do cliente.
        exemplo = ("winget install --id <ID> --exact --silent "
                   "--accept-package-agreements --accept-source-agreements")
        nomes = "\n".join(f"  • {i}" for i in ids)
        resposta = QMessageBox.question(
            self, "Confirmar instalação",
            f"Serão instalados {len(ids)} programa(s):\n\n{nomes}\n\n"
            f"Comando por item:\n{exemplo}\n\n"
            "Pode demorar vários minutos. Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return

        self.btn_instalar.setEnabled(False)
        self.rodar(manutencao.instalar, self._instalacao_pronta, ids)

    def _instalacao_pronta(self, r) -> None:
        self.btn_instalar.setEnabled(True)
        self.anotar(f"Instalados: {len(r.instalados)} | "
                    f"Já tinha: {len(r.ja_tinha)} | Falhas: {len(r.falharam)}")
        for nome, motivo in r.falharam:
            self.anotar(f"  falhou: {nome} — {motivo}")

    # ------------------------------------------------------------------
    # BACKUP
    # ------------------------------------------------------------------
    def medir(self) -> None:
        if self.ocupado:
            return
        self.lista_pastas.clear()
        self.btn_medir.setEnabled(False)
        self.anotar("Medindo pastas do perfil...")
        self.rodar(manutencao.medir_perfil, self._medicao_pronta)

    def _medicao_pronta(self, pastas) -> None:
        self.btn_medir.setEnabled(True)
        self._pastas = pastas
        self.lista_pastas.blockSignals(True)
        for p in pastas:
            item = QTreeWidgetItem(
                self.lista_pastas,
                [p.titulo, f"{p.arquivos:,}".replace(",", "."),
                 formatar_bytes(p.bytes_total)])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked if p.marcada else Qt.Unchecked)
            item.setData(0, Qt.UserRole, p.chave)
            item.setToolTip(0, str(p.caminho))
        self.lista_pastas.blockSignals(False)
        self._atualizar_resumo()

    def _marcacao_mudou(self, item, _coluna) -> None:
        chave = item.data(0, Qt.UserRole)
        for p in self._pastas:
            if p.chave == chave:
                p.marcada = item.checkState(0) == Qt.Checked
        self._atualizar_resumo()

    def _atualizar_resumo(self) -> None:
        total = sum(p.bytes_total for p in self._pastas if p.marcada)
        texto = f"Marcado: {formatar_bytes(total)}"
        pode = bool(total)

        if self._destino:
            livre = manutencao.espaco_livre(self._destino)
            texto += f"  ·  destino: {self._destino}  ·  livre: {formatar_bytes(livre)}"
            # Margem de 5%: o calculo por soma de tamanhos ignora o
            # desperdicio de cluster, que em milhares de arquivos pequenos
            # deixa a copia maior que a conta.
            if livre < total * 1.05:
                texto += "  ·  ESPAÇO INSUFICIENTE"
                self.resumo_backup.setStyleSheet(f"color: {Cor.ERRO};")
                pode = False
            else:
                self.resumo_backup.setStyleSheet(f"color: {Cor.OK};")
        else:
            texto += "  ·  escolha um destino"
            self.resumo_backup.setStyleSheet(f"color: {Cor.TEXTO_SUAVE};")
            pode = False

        self.resumo_backup.setText(texto)
        self.btn_copiar.setEnabled(pode and not self.ocupado)

    def escolher_destino(self) -> None:
        caminho = QFileDialog.getExistingDirectory(
            self, "Onde salvar o backup", self._destino or "")
        if caminho:
            self._destino = caminho
            self._atualizar_resumo()

    def copiar(self) -> None:
        if self.ocupado or not self._destino:
            return
        marcadas = [p for p in self._pastas if p.marcada and p.arquivos]
        total = sum(p.bytes_total for p in marcadas)
        resposta = QMessageBox.question(
            self, "Confirmar backup",
            f"Copiar {formatar_bytes(total)} de "
            f"{len(marcadas)} pasta(s) para:\n{self._destino}\n\n"
            "Arquivos em uso podem falhar e serão contados no final. "
            "Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return

        self.btn_copiar.setEnabled(False)
        self.rodar(manutencao.copiar_perfil, self._copia_pronta,
                   self._pastas, self._destino)

    def _copia_pronta(self, r) -> None:
        self.btn_copiar.setEnabled(True)
        self.anotar(f"Backup em {r.destino}")
        if r.falharam:
            self.anotar(f"{r.falharam} arquivo(s) não puderam ser copiados "
                        "(em uso ou sem permissão).")

    # ------------------------------------------------------------------
    # PRE-FORMATACAO
    # ------------------------------------------------------------------
    def _aba_preformatacao(self) -> QWidget:
        from PySide6.QtWidgets import QVBoxLayout

        aba = QWidget()
        v = QVBoxLayout(aba)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        linha = QHBoxLayout()
        self.btn_drivers_ler = Botao("Listar drivers", "primario")
        self.btn_drivers_ler.clicked.connect(self.listar_drivers)
        linha.addWidget(self.btn_drivers_ler)

        self.btn_drivers_salvar = Botao("Exportar drivers")
        self.btn_drivers_salvar.setToolTip(
            "Copia os pacotes de terceiros para uma pasta. Exige "
            "administrador.")
        self.btn_drivers_salvar.clicked.connect(self.exportar_drivers)
        linha.addWidget(self.btn_drivers_salvar)

        self.btn_drivers_restaurar = Botao("Restaurar drivers", "perigo")
        self.btn_drivers_restaurar.clicked.connect(self.restaurar_drivers)
        linha.addWidget(self.btn_drivers_restaurar)

        self.btn_senhas = Botao("Senhas de Wi-Fi")
        self.btn_senhas.setToolTip(
            "Lê os perfis salvos. As senhas ficam apenas nesta tela e não "
            "entram no relatório.")
        self.btn_senhas.clicked.connect(self.ler_senhas)
        linha.addWidget(self.btn_senhas)
        linha.addStretch(1)
        v.addLayout(linha)

        self.arvore_pre = QTreeWidget()
        self.arvore_pre.setHeaderLabels(["Item", "Origem", "Detalhe"])
        self.arvore_pre.setColumnWidth(0, 300)
        self.arvore_pre.setColumnWidth(1, 150)
        v.addWidget(self.arvore_pre)

        return aba

    def _secao_pre(self, titulo: str) -> QTreeWidgetItem:
        raiz = QTreeWidgetItem(self.arvore_pre, [titulo, "", ""])
        raiz.setForeground(0, QBrush(QColor(Cor.DESTAQUE)))
        raiz.setExpanded(True)
        return raiz

    def listar_drivers(self) -> None:
        if self.ocupado:
            return
        self.btn_drivers_ler.setEnabled(False)
        self.rodar(drivers.listar, self._drivers_prontos)

    def _drivers_prontos(self, lista) -> None:
        self.btn_drivers_ler.setEnabled(True)
        raiz = self._secao_pre(
            f"Drivers de terceiros ({len(lista)} em uso agora)")
        # A exportacao costuma render mais que isto, e o tecnico precisa
        # saber antes de achar que exportou coisa demais.
        QTreeWidgetItem(raiz, [
            "", "",
            "A exportação inclui também drivers de periféricos "
            "desconectados, então o número final costuma ser maior."])
        for d in lista:
            QTreeWidgetItem(raiz, [d.dispositivo or d.inf, d.classe,
                                   f"{d.fornecedor} · v{d.versao} · {d.inf}"])

    def exportar_drivers(self) -> None:
        if self.ocupado:
            return
        destino = QFileDialog.getExistingDirectory(
            self, "Onde salvar os drivers", self._destino or "")
        if not destino:
            return
        self.btn_drivers_salvar.setEnabled(False)
        self.rodar(drivers.exportar, self._drivers_exportados, destino)

    def _drivers_exportados(self, r) -> None:
        self.btn_drivers_salvar.setEnabled(True)
        self.notificar(r.mensagem, "ok" if r.ok else "erro")

    def restaurar_drivers(self) -> None:
        if self.ocupado:
            return
        origem = QFileDialog.getExistingDirectory(
            self, "Pasta com os drivers salvos", "")
        if not origem:
            return
        resposta = QMessageBox.question(
            self, "Confirmar restauração",
            "Instalar todos os pacotes de driver de:" + chr(10)
            + f"{origem}" + chr(10) + chr(10) + "Comando:" + chr(10)
            + r'pnputil /add-driver "<pasta>\*.inf" /subdirs /install'
            + chr(10) + chr(10) + "Pode pedir reinício. Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return
        self.btn_drivers_restaurar.setEnabled(False)
        self.rodar(drivers.restaurar, self._drivers_restaurados, origem)

    def _drivers_restaurados(self, r) -> None:
        self.btn_drivers_restaurar.setEnabled(True)
        self.anotar(r.mensagem)

    def ler_senhas(self) -> None:
        if self.ocupado:
            return
        self.btn_senhas.setEnabled(False)
        self.rodar(wifi.perfis, self._senhas_prontas)

    def _senhas_prontas(self, resultado) -> None:
        self.btn_senhas.setEnabled(True)
        lista, aviso = resultado
        if aviso:
            self.anotar(aviso)
        if not lista:
            return

        raiz = self._secao_pre(f"Redes Wi-Fi salvas ({len(lista)})")
        for perfil in lista:
            QTreeWidgetItem(raiz, [perfil.nome, perfil.seguranca or "—",
                                   perfil.senha or "(senha não exportada)"])

    # ------------------------------------------------------------------
    # ATIVACAO
    # ------------------------------------------------------------------
    def _aba_ativacao(self) -> QWidget:
        from PySide6.QtWidgets import QLineEdit, QVBoxLayout

        aba = QWidget()
        v = QVBoxLayout(aba)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        linha = QHBoxLayout()
        self.btn_ativ_ler = Botao("Diagnosticar", "primario")
        self.btn_ativ_ler.clicked.connect(self.ler_ativacao)
        linha.addWidget(self.btn_ativ_ler)

        self.campo_chave = QLineEdit()
        self.campo_chave.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.campo_chave.setMaxLength(29)
        linha.addWidget(self.campo_chave, 1)

        self.btn_instalar_chave = Botao("Instalar chave")
        self.btn_instalar_chave.setToolTip(
            "Instala uma chave fornecida pelo cliente. Não gera chaves.")
        self.btn_instalar_chave.clicked.connect(self.instalar_chave)
        linha.addWidget(self.btn_instalar_chave)

        self.btn_ativar = Botao("Ativar agora")
        self.btn_ativar.clicked.connect(self.ativar)
        linha.addWidget(self.btn_ativar)
        v.addLayout(linha)

        self.arvore_ativ = QTreeWidget()
        self.arvore_ativ.setHeaderLabels(["Item", "Valor"])
        self.arvore_ativ.setColumnWidth(0, 260)
        v.addWidget(self.arvore_ativ)

        nota = QLabel(
            "Esta ferramenta não contorna licenciamento: ela instala chave "
            "que o cliente já tem e dispara a ativação oficial.")
        nota.setWordWrap(True)
        nota.setStyleSheet(f"color: {Cor.TEXTO_FRACO}; font-size: 11px;")
        v.addWidget(nota)
        return aba

    def ler_ativacao(self) -> None:
        if self.ocupado:
            return
        self.arvore_ativ.clear()
        self.btn_ativ_ler.setEnabled(False)
        self.rodar(ativacao.situacao, self._ativacao_pronta)

    def _ativacao_pronta(self, s) -> None:
        self.btn_ativ_ler.setEnabled(True)
        cores = {"ok": Cor.OK, "atencao": Cor.ATENCAO, "erro": Cor.ERRO}

        for rotulo, valor, alerta in (
            ("Edição", s.edicao, ""),
            ("Canal", s.canal or "não informado", ""),
            ("Estado", s.estado or "desconhecido", s.alerta),
            ("Final da chave", s.chave_parcial or "—", ""),
            ("Licença digital", "sim" if s.digital else "não/indeterminado", ""),
        ):
            item = QTreeWidgetItem(self.arvore_ativ, [rotulo, valor])
            if alerta in cores:
                item.setForeground(1, QBrush(QColor(cores[alerta])))

        raiz = QTreeWidgetItem(self.arvore_ativ, ["O que fazer", ""])
        raiz.setForeground(0, QBrush(QColor(Cor.DESTAQUE)))
        for passo in s.orientacao:
            QTreeWidgetItem(raiz, ["", passo])
        raiz.setExpanded(True)

    def instalar_chave(self) -> None:
        if self.ocupado:
            return
        chave = self.campo_chave.text().strip()
        resposta = QMessageBox.question(
            self, "Confirmar instalação de chave",
            "Instalar esta chave no Windows?" + chr(10) + chr(10)
            + chave + chr(10) + chr(10) + "Comando:" + chr(10)
            + "cscript slmgr.vbs /ipk <chave>",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return
        self.btn_instalar_chave.setEnabled(False)
        self.rodar(ativacao.instalar_chave, self._chave_pronta, chave)

    def _chave_pronta(self, r) -> None:
        self.btn_instalar_chave.setEnabled(True)
        self.notificar(r.mensagem, "ok" if r.ok else "erro")

    def ativar(self) -> None:
        if self.ocupado:
            return
        self.btn_ativar.setEnabled(False)
        self.anotar("Contatando o servidor de ativação da Microsoft...")
        self.rodar(ativacao.ativar, self._ativou)

    def _ativou(self, r) -> None:
        self.btn_ativar.setEnabled(True)
        self.notificar(r.mensagem, "ok" if r.ok else "erro")
        if r.ok:
            self.ler_ativacao()
