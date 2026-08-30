"""Constroi a interface inteira e chama tudo que e seguro chamar.

Os dois travamentos que chegaram ao usuario seriam pegos aqui:

    KeyError: 'espaco'          - a grade foi refeita e a verificacao
                                  inicial continuou pedindo chave antiga
    AttributeError: 'ocupado'   - o botao de tema assumiu que todo painel
                                  herda de PainelBase

Nenhum dos dois aparece ao compilar, e nenhum teste de unidade os tocava:
eram bugs de integracao entre widgets, visiveis so ao montar a tela.

O QUE ESTE TESTE NAO FAZ
    Nao clica no que apaga, instala, repara ou abre dialogo do sistema.
    A lista NEGADAS existe para isso, e e explicita: metodo novo entra no
    teste por padrao, e so sai se alguem justificar.
"""

from __future__ import annotations

import inspect
import os
import unittest

# Chamar todo metodo publico dispara consultas CIM e PowerShell de verdade.
# Aqui isso leva segundos; num runner do GitHub leva mais de quinze
# minutos, porque cada invocacao do PowerShell custa muito mais numa
# maquina virtual sem estado quente. O teste continua valendo localmente,
# que e onde ele pega o erro antes do commit.
NO_CI = bool(os.environ.get("CI"))

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from tecnico.tema import aplicar_tema, registrar_fontes  # noqa: E402

registrar_fontes()

from tecnico.ui.janela import Janela  # noqa: E402

# Metodos que alteram a maquina, gastam banda ou abrem dialogo bloqueante.
# Chamar qualquer um destes num teste seria acidente, nao verificacao.
NEGADAS = {
    # apagam, instalam ou reparam
    "limpar", "esvaziar_lixeira", "aplicar", "executar_acao", "desinstalar",
    "remover_do_inicio", "remover_fabrica", "instalar", "instalar_chave",
    "ativar", "copiar", "restaurar_drivers", "exportar_drivers",
    # abrem dialogo e travam a espera de clique
    "salvar", "salvar_resumo", "salvar_ficha", "escolher_destino",
    "exportar", "escolher_plano",
    # abrem janela em tela cheia
    "testar_tela", "testar_teclado",
    # elevam, fecham ou remontam a janela
    "elevar", "alternar_tema", "close", "abrir_pasta",
    # consomem rede ou demoram minutos
    "medir_velocidade", "medir_disco", "medir_memoria", "medir_pastas",
    "varrer_wifi", "ler_senhas",
}


class TestFumacaDaInterface(unittest.TestCase):
    def setUp(self):
        self.janela = Janela()
        self.janela.resize(1400, 860)

    def tearDown(self):
        # Sem isto o close() recolhe para a bandeja em vez de fechar, e o
        # teste vai acumulando janelas escondidas.
        self.janela.encerrar_de_verdade = True
        self.janela.close()
        self.janela.deleteLater()
        _app.processEvents()

    def test_todo_painel_da_navegacao_abre(self):
        for chave in self.janela.botoes:
            with self.subTest(painel=chave):
                self.janela.mostrar(chave)
                _app.processEvents()
                self.assertIs(self.janela.pilha.currentWidget(),
                              self.janela.paineis[chave])

    @unittest.skipIf(NO_CI, "dispara varredura de disco e rede")
    def test_verificacao_inicial_nao_estoura(self):
        # Este e o caminho exato do KeyError: 'espaco'.
        self.janela.mostrar("inicio")
        self.janela.iniciar_verificacao()
        _app.processEvents()

    def test_faixa_de_status_e_avisos_respondem(self):
        self.janela.operacao("teste em andamento")
        self.janela.notificar("mensagem de teste", "ok")
        self.janela.notificar("mensagem de erro", "erro")
        _app.processEvents()
        self.janela.operacao("")

    @unittest.skipIf(NO_CI, "consulta o sistema de verdade; lento em runner")
    def test_metodos_publicos_seguros_de_todo_painel(self):
        """Chama todo metodo publico sem argumento obrigatorio.

        E o teste que pega assinatura quebrada, atributo que sumiu e
        chave renomeada - o tipo de defeito que compilar nao acusa.
        """
        chamados = 0
        for chave, painel in self.janela.paineis.items():
            for nome, metodo in inspect.getmembers(painel, inspect.ismethod):
                if nome.startswith("_") or nome in NEGADAS:
                    continue
                try:
                    assinatura = inspect.signature(metodo)
                except (TypeError, ValueError):
                    continue
                obrigatorios = [
                    p for p in assinatura.parameters.values()
                    if p.default is p.empty
                    and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                ]
                if obrigatorios:
                    continue

                with self.subTest(painel=chave, metodo=nome):
                    try:
                        metodo()
                    except Exception as erro:  # noqa: BLE001
                        self.fail(f"{chave}.{nome}() estourou: "
                                  f"{type(erro).__name__}: {erro}")
                    chamados += 1
                _app.processEvents()

        # Guarda contra o teste virar vazio por engano.
        self.assertGreater(chamados, 10,
                           "quase nada foi chamado; a filtragem está errada")


class TestFumacaNosDoisTemas(unittest.TestCase):
    """A troca de tema remonta a janela; ambas as paletas precisam montar."""

    def test_a_janela_monta_nos_dois_temas(self):
        original = None
        from tecnico.tema import tema_atual

        original = tema_atual()
        try:
            for tema in ("escuro", "claro"):
                with self.subTest(tema=tema):
                    aplicar_tema(tema)
                    j = Janela()
                    j.resize(1400, 860)
                    for chave in j.botoes:
                        j.mostrar(chave)
                    _app.processEvents()
                    j.encerrar_de_verdade = True
                    j.close()
                    j.deleteLater()
                    _app.processEvents()
        finally:
            aplicar_tema(original)


if __name__ == "__main__":
    unittest.main()


class TestGuardaDaTrocaDeTema(unittest.TestCase):
    """`alternar_tema` remonta a janela e por isso fica fora da fumaça.

    A checagem de painel ocupado foi extraída justamente para poder ser
    testada sem remontar — foi ali que o AttributeError se escondeu.
    """

    def setUp(self):
        self.janela = Janela()

    def tearDown(self):
        # Sem isto o close() recolhe para a bandeja em vez de fechar, e o
        # teste vai acumulando janelas escondidas.
        self.janela.encerrar_de_verdade = True
        self.janela.close()
        self.janela.deleteLater()
        _app.processEvents()

    def test_checagem_de_ocupado_atravessa_todo_painel(self):
        # PainelInicio não herda de PainelBase: sem getattr, estoura aqui.
        self.assertEqual(self.janela.paineis_ocupados(), [])

    def test_nem_todo_painel_tem_a_propriedade_ocupado(self):
        # Documenta o motivo do getattr. Se um dia todos herdarem de
        # PainelBase, este teste falha e o getattr pode sair.
        sem = [c for c, p in self.janela.paineis.items()
               if not hasattr(p, "ocupado")]
        self.assertIn("inicio", sem)


class TestBandeja(unittest.TestCase):
    """Fechar recolhe; sair encerra. Confundir os dois deixa o técnico
    achando que fechou o app quando ele continua rodando, ou o contrário:
    perdendo o histórico carregado a cada atendimento."""

    def setUp(self):
        self.janela = Janela()

    def tearDown(self):
        self.janela.encerrar_de_verdade = True
        self.janela.close()
        self.janela.deleteLater()
        _app.processEvents()

    def test_fechar_recolhe_em_vez_de_encerrar(self):
        if self.janela.bandeja is None:
            self.skipTest("sistema sem área de notificação")
        self.janela.show()
        _app.processEvents()
        self.janela.close()
        _app.processEvents()
        # A janela some da tela mas o objeto continua vivo.
        self.assertFalse(self.janela.isVisible())
        self.assertIsNotNone(self.janela.bandeja)

    def test_restaurar_traz_a_janela_de_volta(self):
        if self.janela.bandeja is None:
            self.skipTest("sistema sem área de notificação")
        self.janela.show()
        self.janela.bandeja.recolher()
        _app.processEvents()
        self.assertFalse(self.janela.isVisible())

        self.janela.bandeja.restaurar()
        _app.processEvents()
        self.assertTrue(self.janela.isVisible())

    def test_o_aviso_da_bandeja_so_aparece_uma_vez(self):
        if self.janela.bandeja is None:
            self.skipTest("sistema sem área de notificação")
        b = self.janela.bandeja
        self.assertFalse(b._avisou)
        b.recolher()
        self.assertTrue(b._avisou)
        # Repetir o balão a cada fechamento viraria ruído.
        b.recolher()
        self.assertTrue(b._avisou)

    def test_titulo_da_janela_bate_com_o_que_a_busca_procura(self):
        """`focar_instancia_existente` acha a janela por título exato.

        Se o título mudar sem atualizar a busca, a segunda instância volta
        a só mostrar o aviso em vez de trazer a existente para frente.
        """
        from tecnico.ui.janela import APLICATIVO, VERSAO

        self.assertEqual(self.janela.windowTitle(), f"{APLICATIVO} {VERSAO}")
