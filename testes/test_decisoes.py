"""Funcoes que decidem o que o tecnico ve, e os limiares que as regem.

Nenhuma delas toca o disco: sao regras puras, que e onde regressao passa
despercebida. Varias destas foram corrigidas depois de errar contra a
maquina real, e o teste existe para que a correcao nao se perca.
"""

from __future__ import annotations

import unittest

from tecnico.nucleo import (
    ativacao,
    bloatware,
    desempenho,
    historico,
    licenca,
    persistencia,
    reparo,
    saude,
    seguranca,
    wifi,
)


class TestFaixaMortaDaComparacao(unittest.TestCase):
    """A maquina nunca fica parada: o Windows grava log entre as duas
    medicoes. Sem faixa morta o relatorio anuncia melhoria que ninguem
    fez."""

    def comparar(self, **campos):
        base = dict(disco_livre=100 * 1024 ** 3, lixo_bytes=500 * 1024 ** 2,
                    itens_inicializacao=10, programas_instalados=50,
                    memoria_usada_pct=60.0)
        antes = historico.Instantaneo(**base)
        base.update(campos)
        depois = historico.Instantaneo(**base)
        return {m.rotulo: m for m in historico.comparar(antes, depois)}

    def test_variacao_minima_de_disco_e_ignorada(self):
        # 40 MB, abaixo do limiar de 50 MB.
        m = self.comparar(disco_livre=100 * 1024 ** 3 + 40 * 1024 ** 2)
        self.assertEqual(m["Espaço livre no disco"].situacao, "neutro")

    def test_variacao_real_de_disco_e_registrada(self):
        m = self.comparar(disco_livre=102 * 1024 ** 3)
        self.assertEqual(m["Espaço livre no disco"].situacao, "melhorou")

    def test_disco_encolhendo_conta_como_piora(self):
        m = self.comparar(disco_livre=90 * 1024 ** 3)
        self.assertEqual(m["Espaço livre no disco"].situacao, "piorou")

    def test_lixo_a_menos_e_melhora(self):
        m = self.comparar(lixo_bytes=10 * 1024 ** 2)
        self.assertEqual(m["Arquivos temporários"].situacao, "melhorou")

    def test_memoria_oscilando_pouco_e_ignorada(self):
        m = self.comparar(memoria_usada_pct=62.0)   # 2 pontos, limiar 3
        self.assertEqual(m["Memória em uso"].situacao, "neutro")

    def test_inicializacao_nao_tem_faixa_morta(self):
        # Um item a menos e sempre acao deliberada de alguem.
        m = self.comparar(itens_inicializacao=9)
        self.assertEqual(m["Itens na inicialização"].situacao, "melhorou")

    def test_duas_medicoes_iguais_nao_inventam_nada(self):
        m = self.comparar()
        for mudanca in m.values():
            self.assertEqual(mudanca.situacao, "neutro")
            self.assertEqual(mudanca.variacao, "")


class TestIdentidadeDaMaquina(unittest.TestCase):
    """Desktop montado traz placeholder no BIOS. Sem filtro, todas essas
    maquinas cairiam no mesmo arquivo de historico."""

    def test_placeholders_de_fabrica_sao_recusados(self):
        for lixo in ("To Be Filled By O.E.M.", "Default string", "None",
                     "System Serial Number", "0123456789", "n/a"):
            self.assertEqual(historico._serie_valida(lixo), "",
                             f"{lixo!r} deveria ser recusado")

    def test_serie_real_e_aceita(self):
        # Formato de serial de placa-mae; valor sintetico de proposito,
        # para nao publicar o numero de uma maquina de verdade.
        self.assertEqual(historico._serie_valida("XY0-Z1234567890"),
                         "XY0-Z1234567890")

    def test_serie_curta_demais_e_recusada(self):
        self.assertEqual(historico._serie_valida("ABC"), "")


class TestServicoSuspeito(unittest.TestCase):
    """Windows Update e BITS ficam parados com inicializacao Manual no
    Windows 10 e 11. A primeira versao marcava os dois e daria alarme
    falso em toda maquina saudavel."""

    def suspeito(self, estado, inicio):
        return seguranca.Servico("x", "Teste", estado, inicio).suspeito

    def test_parado_e_manual_e_normal(self):
        self.assertFalse(self.suspeito("Stopped", "Manual"))

    def test_parado_mas_automatico_e_suspeito(self):
        self.assertTrue(self.suspeito("Stopped", "Automatic"))

    def test_desabilitado_e_sempre_suspeito(self):
        self.assertTrue(self.suspeito("Stopped", "Disabled"))
        self.assertTrue(self.suspeito("Running", "Disabled"))

    def test_rodando_e_automatico_esta_certo(self):
        self.assertFalse(self.suspeito("Running", "Automatic"))


class TestTarefaSuspeita(unittest.TestCase):
    def test_script_em_pasta_de_usuario(self):
        motivo = persistencia._avaliar(
            r"C:\Users\x\AppData\Roaming\update.vbs", "")
        self.assertIn("pasta de usuário", motivo)

    def test_programa_legitimo_nao_gera_aviso(self):
        self.assertEqual(
            persistencia._avaliar(r"C:\Program Files\App\app.exe", ""), "")

    def test_tarefa_sem_programa(self):
        self.assertIn("sem programa", persistencia._avaliar("", ""))

    def test_powershell_codificado(self):
        self.assertIn("codificado",
                      persistencia._avaliar("powershell.exe", "-enc SQBF"))

    def test_programa_na_pasta_temp(self):
        self.assertIn("temporários",
                      persistencia._avaliar(r"C:\Windows\Temp\svc.exe", ""))


class TestPontoDeRestauracao(unittest.TestCase):
    """A data vem no formato CIM_DATETIME. Sem parsear, o app nao
    distingue 'protecao desligada' de 'ja teve ponto hoje'."""

    def test_data_do_wmi_vira_horas(self):
        horas = reparo._horas_desde("27|20260829055936.969312-000")
        self.assertIsNotNone(horas)
        self.assertGreater(horas, 0)

    def test_entrada_invalida_devolve_none(self):
        for ruim in ("", "lixo", "27|", "27|abc", "sem barra"):
            self.assertIsNone(reparo._horas_desde(ruim))

    def test_acoes_destrutivas_criam_ponto_antes(self):
        for chave in ("sfc", "dism", "reset_rede", "chkdsk_corrigir"):
            self.assertIn(chave, reparo.COM_PONTO_AUTOMATICO)

    def test_leitura_pura_nao_cria_ponto(self):
        # chkdsk sem /f nao altera nada; criar ponto seria desperdicio.
        self.assertNotIn("chkdsk", reparo.COM_PONTO_AUTOMATICO)


class TestVereditoDoDisco(unittest.TestCase):
    """A leitura aleatoria de 4 KB e o que o usuario sente; a sequencial
    engana. Os limiares aqui viram recomendacao de troca por SSD."""

    def veredito(self, aleatoria):
        return desempenho.Medida(leitura_aleatoria=aleatoria).veredito

    def test_hd_mecanico_recebe_recomendacao_forte(self):
        self.assertIn("Trocar por SSD", self.veredito(0.6))

    def test_ssd_moderno_nao_gera_recomendacao(self):
        self.assertIn("SSD moderno", self.veredito(40.0))

    def test_faixa_intermediaria_e_reconhecida(self):
        self.assertIn("entrada", self.veredito(8.0))

    def test_medida_com_erro_nao_opina(self):
        self.assertEqual(
            desempenho.Medida(erro="falhou", leitura_aleatoria=0.1).veredito,
            "")


class TestSaudeDaBateria(unittest.TestCase):
    """Carga e saude sao coisas diferentes: uma bateria pode marcar 100%
    carregada e guardar um terco do que guardava nova."""

    def bateria(self, projeto, cheia):
        return saude.Bateria(presente=True, projeto_mwh=projeto,
                             cheia_mwh=cheia)

    def test_bateria_nova_nao_alerta(self):
        self.assertEqual(self.bateria(45000, 44000).alerta, "")

    def test_bateria_gasta_vira_erro(self):
        b = self.bateria(45000, 19800)
        self.assertEqual(b.saude_pct, 44)
        self.assertEqual(b.alerta, "erro")

    def test_meia_vida_vira_atencao(self):
        self.assertEqual(self.bateria(45000, 33000).alerta, "atencao")

    def test_desktop_sem_bateria_nao_alerta(self):
        self.assertEqual(saude.Bateria().alerta, "")
        self.assertEqual(saude.Bateria().saude_pct, 0)


class TestCanalDeWifi(unittest.TestCase):
    def test_canais_disputados_conta_certo(self):
        redes = [wifi.Rede("A", 70, 6), wifi.Rede("B", 60, 6),
                 wifi.Rede("C", 50, 11)]
        self.assertEqual(wifi.canais_disputados(redes), {6: 2, 11: 1})

    def test_faixa_por_numero_do_canal(self):
        self.assertEqual(wifi.Rede("x", 50, 6).faixa, "2,4 GHz")
        self.assertEqual(wifi.Rede("x", 50, 44).faixa, "5 GHz")
        self.assertEqual(wifi.Rede("x", 50, 0).faixa, "")

    def test_rede_sem_canal_nao_entra_na_contagem(self):
        self.assertEqual(wifi.canais_disputados([wifi.Rede("A", 70, 0)]), {})


class TestCatalogoDeBloatware(unittest.TestCase):
    """Lista branca curada: o que nao esta aqui nao e oferecido. O risco
    e o inverso do normal - incluir demais, nao de menos."""

    def test_sem_identificadores_repetidos(self):
        ids = [i for i, _n, _c in bloatware.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))

    def test_nao_oferece_o_que_quebraria_a_maquina(self):
        protegidos = ("languageexperiencepack", "heifimageextension",
                      "hevcvideoextension", "vclibs", "ui.xaml",
                      "windowsstore", "desktopappinstaller",
                      "shellexperiencehost", "startmenuexperiencehost")
        for identificador, _nome, _cat in bloatware.CATALOGO:
            for proibido in protegidos:
                self.assertNotIn(proibido, identificador.lower(),
                                 f"{identificador} nao deveria ser oferecido")


class TestLicencaEAtivacao(unittest.TestCase):
    def test_canal_extraido_da_descricao(self):
        self.assertEqual(
            licenca._canal("Windows(R) Operating System, RETAIL channel"),
            "RETAIL")
        self.assertEqual(
            licenca._canal("Office 16, TIMEBASED_SUB channel"),
            "TIMEBASED_SUB")

    def test_descricao_sem_canal_devolve_vazio(self):
        self.assertEqual(licenca._canal("sem virgula aqui"), "")

    def test_formato_de_chave(self):
        self.assertTrue(
            ativacao.FORMATO_CHAVE.match("ABCDE-12345-FGHIJ-67890-KLMNO"))
        for ruim in ("curta", "ABCDE-12345", "ABCDE12345FGHIJ67890KLMNO"):
            self.assertFalse(ativacao.FORMATO_CHAVE.match(ruim), ruim)

    def test_maquina_ativada_nao_pede_chave(self):
        # licenca.SITUACOES devolve "ok", nao "". Comparar so com vazio
        # fazia a orientacao mandar pedir chave a quem ja esta ativado.
        s = ativacao.Situacao(canal="RETAIL", estado="Ativado", alerta="ok")
        self.assertIn("Nada a fazer", ativacao._orientar(s)[0])

    def test_licenca_digital_nao_pede_chave(self):
        s = ativacao.Situacao(estado="Não ativado", alerta="erro", digital=True)
        self.assertIn("não há chave", ativacao._orientar(s)[0])

    def test_volume_manda_falar_com_o_ti(self):
        s = ativacao.Situacao(canal="VOLUME_MAK", estado="Não ativado",
                              alerta="erro")
        self.assertIn("servidor de ativação", ativacao._orientar(s)[0])

    def test_orientacao_sempre_recusa_contornar(self):
        s = ativacao.Situacao(canal="RETAIL", estado="Não ativado",
                              alerta="erro")
        self.assertIn("não contorna", " ".join(ativacao._orientar(s)))


if __name__ == "__main__":
    unittest.main()


class TestResumoParaOCliente(unittest.TestCase):
    """O resumo vai para o cliente, nao para o tecnico: texto cortado no
    lugar errado vira informacao errada na mao de quem paga."""

    def test_nao_quebra_em_numero_decimal(self):
        from tecnico.nucleo.resumo import _primeira_frase

        # Cortar no primeiro ponto transformava isto em "0".
        self.assertEqual(
            _primeira_frase("0.6 MB/s em leitura aleatória. Um SSD faz mais."),
            "0.6 MB/s em leitura aleatória")

    def test_frase_unica_perde_o_ponto_final(self):
        from tecnico.nucleo.resumo import _primeira_frase

        self.assertEqual(_primeira_frase("Apenas 6% livres."),
                         "Apenas 6% livres")

    def test_texto_longo_e_cortado_em_palavra_inteira(self):
        from tecnico.nucleo.resumo import _primeira_frase

        saida = _primeira_frase("palavra " * 40)
        self.assertTrue(saida.endswith("..."))
        self.assertLessEqual(len(saida), 92)


class TestOrdemDoRoteiro(unittest.TestCase):
    """A ordem virou codigo porque inverter produz relatorio errado."""

    def chaves(self):
        from tecnico.nucleo import roteiro

        return [e.chave for e in roteiro.etapas()]

    def test_estado_inicial_vem_antes_de_alterar(self):
        c = self.chaves()
        for alteracao in ("limpeza", "sfc"):
            self.assertLess(c.index("antes"), c.index(alteracao))

    def test_estado_final_vem_depois_de_alterar(self):
        c = self.chaves()
        for alteracao in ("limpeza", "sfc"):
            self.assertGreater(c.index("depois"), c.index(alteracao))

    def test_disco_e_medido_depois_do_fechamento(self):
        # O teste escreve 192 MB e move a memoria; antes do "depois" ele
        # sujava a comparacao com uma piora causada pela propria medicao.
        c = self.chaves()
        self.assertGreater(c.index("disco"), c.index("depois"))

    def test_pdf_e_a_ultima_etapa(self):
        self.assertEqual(self.chaves()[-1], "pdf")

    def test_checklist_entra_antes_do_pdf(self):
        c = self.chaves()
        self.assertLess(c.index("entrega"), c.index("pdf"))

    def test_etapas_que_alteram_vem_desmarcadas(self):
        from tecnico.nucleo import roteiro

        for e in roteiro.etapas():
            if e.altera:
                self.assertFalse(e.marcada, f"{e.chave} vem marcada")
