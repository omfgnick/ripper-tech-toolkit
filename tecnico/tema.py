"""Paleta, tipografia e folha de estilo do aplicativo.

Um lugar so. Widget que precisa de uma cor pega daqui - cor solta no meio
do codigo e o comeco de uma interface que nao parece do mesmo produto.

LINGUAGEM VISUAL: CYBERPUNK 2077
    Amarelo #FCEE0A sobre preto, tipografia Rajdhani (a fonte da interface
    do jogo), cantos chanfrados em vez de arredondados e molduras finas
    com marcacao de canto.

    A regra que toda analise seria do HUD repete: cada cor significa um
    estado e o mapeamento nunca quebra. A critica mais comum ao jogo e
    justamente ter vermelho demais sem codigo consistente. Por isso aqui o
    amarelo NAO participa da escala de alerta - ele e a cor do proprio
    aplicativo (selecao, foco, moldura ativa), e os avisos tem escala
    propria: ciano tranquilo, ambar atencao, vermelho acao necessaria.

    Sem essa separacao, uma tela cheia de amarelo de interface faria o
    amarelo de aviso desaparecer no meio.
"""

from __future__ import annotations


class Cor:
    """Cada valor tem uma funcao e um lugar onde nao deve aparecer."""

    # Fundos, do mais profundo ao mais claro. Preto de verdade e duro na
    # vista por horas; #08080a tem um azul minimo que descansa.
    FUNDO = "#08080a"
    FUNDO_ALTO = "#0e0e12"
    PAINEL = "#121218"
    PAINEL_ALTO = "#1a1a22"
    BORDA = "#2e2e38"
    BORDA_SUAVE = "#1e1e26"

    # Texto - nunca usar TEXTO_FRACO em leitura longa
    TEXTO = "#e8e8ec"
    TEXTO_SUAVE = "#8f8f9c"
    TEXTO_FRACO = "#5f5f6c"

    # Escala de alerta. Nao inclui amarelo de proposito: ver o cabecalho.
    OK = "#00f0ff"
    ATENCAO = "#ff9f1c"
    ERRO = "#ff003c"
    NEUTRO = "#5f5f6c"

    # A cor do aplicativo: selecao, foco, moldura ativa, cabecalho.
    DESTAQUE = "#fcee0a"
    DESTAQUE_FORTE = "#ffff66"
    # Amarelo apagado para moldura inativa - mantem a forma sem gritar.
    DESTAQUE_FOSCO = "#6b6608"
    # Texto sobre bloco amarelo solido. Preto puro vibra sobre amarelo
    # saturado; um cinza muito escuro assenta melhor.
    SOBRE_DESTAQUE = "#0a0a06"


class Fonte:
    FAMILIA = "Rajdhani"
    # O registro tecnico continua monoespacado: e leitura de dados em
    # coluna, e Rajdhani tem largura variavel que desalinha numero.
    MONO = "Consolas"
    RESERVA = "Segoe UI"


def _ha_aplicacao() -> bool:
    """Se existe QGuiApplication viva.

    Nao e zelo excessivo: QFontDatabase.families() sem aplicacao nao
    levanta excecao - ele ABORTA o processo (0xC0000409). Uma ferramenta
    que importasse o tema fora do app morreria sem mensagem nenhuma, e foi
    exatamente o que aconteceu na primeira versao deste arquivo.
    """
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() is not None


def registrar_fontes() -> bool:
    """Carrega Rajdhani do pacote. Devolve False se nao houver.

    Precisa rodar depois de criar a aplicacao e antes de qualquer widget.
    A maquina do cliente nao tem a fonte instalada, entao ela viaja dentro
    do executavel - sem isso o Qt cairia num substituto e o visual inteiro
    mudaria de cara.
    """
    if not _ha_aplicacao():
        return False

    from PySide6.QtGui import QFontDatabase

    from .recursos import fontes

    carregou = False
    for arquivo in fontes():
        if QFontDatabase.addApplicationFont(str(arquivo)) != -1:
            carregou = True
    return carregou


def familia() -> str:
    """Rajdhani se estiver carregada, senao a reserva do sistema."""
    if not _ha_aplicacao():
        return Fonte.RESERVA

    from PySide6.QtGui import QFontDatabase

    if Fonte.FAMILIA in QFontDatabase.families():
        return Fonte.FAMILIA
    return Fonte.RESERVA


def folha_de_estilo() -> str:
    """QSS global. Tudo que se repete vem daqui.

    Raio zero em tudo: canto arredondado e o oposto da linguagem do jogo.
    O chanfro de verdade e desenhado pelos widgets, porque o QSS nao sabe
    cortar canto - so arredondar.
    """
    f = familia()
    return f"""
    QWidget {{
        color: {Cor.TEXTO};
        font-family: "{f}";
        font-size: 14px;
    }}

    QToolTip {{
        background: {Cor.FUNDO};
        color: {Cor.DESTAQUE};
        border: 1px solid {Cor.DESTAQUE_FOSCO};
        border-radius: 0px;
        padding: 5px 8px;
        font-family: "{Fonte.MONO}";
        font-size: 11px;
    }}

    QTreeWidget, QPlainTextEdit, QLineEdit, QTextEdit {{
        background: {Cor.FUNDO_ALTO};
        border: 1px solid {Cor.BORDA};
        border-radius: 0px;
        selection-background-color: {Cor.DESTAQUE};
        selection-color: {Cor.SOBRE_DESTAQUE};
    }}

    QLineEdit {{
        padding: 6px 9px;
        color: {Cor.TEXTO};
    }}
    QLineEdit:focus {{
        border: 1px solid {Cor.DESTAQUE};
    }}

    QTreeWidget {{
        outline: none;
        alternate-background-color: {Cor.PAINEL};
    }}
    QTreeWidget::item {{
        padding: 5px 4px;
        border: none;
    }}
    /* Selecao invertida: bloco amarelo solido com texto preto. E a marca
       registrada do menu do jogo e o unico lugar onde o fundo e claro. */
    QTreeWidget::item:selected {{
        background: {Cor.DESTAQUE};
        color: {Cor.SOBRE_DESTAQUE};
    }}
    QTreeWidget::item:hover {{
        background: {Cor.PAINEL_ALTO};
    }}

    QHeaderView::section {{
        background: {Cor.FUNDO};
        color: {Cor.DESTAQUE};
        border: none;
        border-bottom: 1px solid {Cor.DESTAQUE_FOSCO};
        padding: 7px 6px;
        font-size: 11px;
        font-weight: 600;
    }}

    QProgressBar {{
        background: {Cor.FUNDO_ALTO};
        border: 1px solid {Cor.BORDA};
        border-radius: 0px;
    }}
    QProgressBar::chunk {{
        background: {Cor.DESTAQUE};
    }}

    QScrollBar:vertical {{
        background: {Cor.FUNDO};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {Cor.BORDA};
        min-height: 28px;
        border-radius: 0px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Cor.DESTAQUE_FOSCO};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QTabBar::tab {{
        background: transparent;
        color: {Cor.TEXTO_SUAVE};
        padding: 7px 18px;
        border: none;
        border-bottom: 1px solid {Cor.BORDA};
        font-size: 12px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        color: {Cor.DESTAQUE};
        border-bottom: 2px solid {Cor.DESTAQUE};
    }}
    QTabWidget::pane {{ border: none; }}

    QCheckBox::indicator, QTreeWidget::indicator {{
        width: 13px;
        height: 13px;
        border: 1px solid {Cor.BORDA};
        background: {Cor.FUNDO};
    }}
    QCheckBox::indicator:checked, QTreeWidget::indicator:checked {{
        background: {Cor.DESTAQUE};
        border: 1px solid {Cor.DESTAQUE};
    }}

    QMessageBox {{
        background: {Cor.PAINEL};
    }}
    QMessageBox QLabel {{
        color: {Cor.TEXTO};
    }}
    """
