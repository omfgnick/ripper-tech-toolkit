"""A barreira que decide o que pode ser apagado.

E o teste mais importante do projeto: `_dentro_da_lista_branca` e a ultima
coisa que roda antes de um `unlink`. Se ela ceder, o app apaga arquivo de
cliente. Uma regressao aqui nao daria erro nenhum - so destruiria dados em
silencio, o que e exatamente o tipo de falha que teste automatizado
existe para impedir.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tecnico.nucleo import limpeza


class TestListaBranca(unittest.TestCase):
    def setUp(self):
        self.permitidas = [Path(r"C:\Users\fulano\AppData\Local\Temp"),
                           Path(r"C:\Windows\Temp")]

    def dentro(self, caminho: str) -> bool:
        return limpeza._dentro_da_lista_branca(Path(caminho), self.permitidas)

    def test_arquivo_dentro_da_pasta_permitida(self):
        self.assertTrue(
            self.dentro(r"C:\Users\fulano\AppData\Local\Temp\lixo.tmp"))

    def test_arquivo_em_subpasta_permitida(self):
        self.assertTrue(
            self.dentro(r"C:\Users\fulano\AppData\Local\Temp\sub\a\b.log"))

    def test_documentos_do_cliente_recusado(self):
        self.assertFalse(self.dentro(r"C:\Users\fulano\Documents\tese.docx"))

    def test_area_de_trabalho_recusada(self):
        self.assertFalse(self.dentro(r"C:\Users\fulano\Desktop\nota.pdf"))

    def test_raiz_do_windows_recusada(self):
        self.assertFalse(self.dentro(r"C:\Windows\explorer.exe"))

    def test_prefixo_parecido_nao_engana(self):
        # "Temp2" comeca com "Temp": comparacao por texto deixaria passar.
        self.assertFalse(self.dentro(r"C:\Windows\Temp2\arquivo.txt"))

    def test_subida_por_pontos_recusada(self):
        self.assertFalse(self.dentro(
            r"C:\Users\fulano\AppData\Local\Temp\..\..\Documents\a.docx"))

    def test_lista_vazia_recusa_tudo(self):
        self.assertFalse(limpeza._dentro_da_lista_branca(
            Path(r"C:\Windows\Temp\x.tmp"), []))


class TestAlvos(unittest.TestCase):
    def test_nenhum_alvo_toca_pasta_de_documentos(self):
        proibidas = ("documents", "desktop", "pictures", "videos", "music",
                     "meus documentos", "área de trabalho")
        for alvo in limpeza.alvos():
            for pasta in alvo.pastas:
                texto = str(pasta).lower()
                for proibida in proibidas:
                    self.assertNotIn(
                        proibida, texto,
                        f"{alvo.chave} aponta para {pasta}")

    def test_nenhum_alvo_e_a_raiz_de_uma_unidade(self):
        for alvo in limpeza.alvos():
            for pasta in alvo.pastas:
                self.assertGreater(
                    len(pasta.parts), 2,
                    f"{alvo.chave} aponta perigosamente alto: {pasta}")


if __name__ == "__main__":
    unittest.main()
