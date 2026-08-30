"""Teste rapido de memoria RAM, sem reiniciar a maquina.

O QUE ESTE TESTE E, E O QUE ELE NAO E
    Ele aloca um bloco grande, escreve padroes conhecidos, le de volta e
    compara. Pega defeito grosseiro - bit que nao gruda, endereco que
    espelha outro - que e a causa de boa parte das telas azuis
    intermitentes.

    Ele NAO substitui o MemTest86 rodado do boot, e dizer o contrario
    seria enganar o cliente. Duas limitacoes de fundo:

        A memoria ocupada pelo Windows e pelos programas abertos nao pode
        ser testada, porque esta em uso. Sobra o que da para alocar.

        O Windows pode paginar parte do bloco para o disco, e ai o teste
        conferiria o arquivo de paginacao, nao o pente. O tamanho fica
        limitado justamente para caber na memoria livre de verdade.

    Por isso o resultado positivo e conclusivo (achou erro, a peca esta
    ruim) e o negativo e apenas indicativo (nao achou aqui).

PADROES
    0x00 e 0xFF pegam bit preso; 0xAA e 0x55 (10101010 e 01010101) pegam
    interferencia entre linhas vizinhas, que os padroes uniformes deixam
    passar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

BLOCO = 16 * 1024 * 1024          # 16 MB por pedaco
TETO = 2 * 1024 ** 3              # nunca passar de 2 GB
FRACAO_LIVRE = 0.55               # do que estiver disponivel no momento

PADROES = [
    (b"\x00", "zeros"),
    (b"\xff", "uns"),
    (b"\xaa", "alternado 10101010"),
    (b"\x55", "alternado 01010101"),
]


@dataclass
class Resultado:
    testado: int = 0
    erros: int = 0
    padroes: int = 0
    segundos: float = 0.0
    interrompido: bool = False
    erro: str = ""
    detalhes: list[str] = field(default_factory=list)

    @property
    def veredito(self) -> str:
        if self.erro:
            return ""
        if self.erros:
            return ("MEMÓRIA COM DEFEITO. Erros de leitura confirmados — "
                    "troque ou reassente os pentes e teste um de cada vez.")
        if self.interrompido:
            return "Teste interrompido antes do fim."
        return ("Nenhum erro nos blocos testados. Não descarta defeito "
                "na memória em uso pelo Windows; para isso, MemTest86 "
                "pelo boot.")


def _orcamento() -> int:
    import psutil

    disponivel = psutil.virtual_memory().available
    return max(BLOCO, min(TETO, int(disponivel * FRACAO_LIVRE)))


def testar(relatar=lambda _: None, percentual=lambda _: None,
           cancelado=lambda: False) -> Resultado:
    r = Resultado()
    orcamento = _orcamento()
    pedacos = max(1, orcamento // BLOCO)
    inicio = time.perf_counter()

    from .win import formatar_bytes

    relatar(f"Reservando {formatar_bytes(pedacos * BLOCO)} de memória...")
    try:
        for indice, (byte, nome) in enumerate(PADROES):
            if cancelado():
                r.interrompido = True
                break

            esperado = byte * BLOCO
            relatar(f"Padrão {nome}...")

            # Todos os pedacos ficam alocados ao mesmo tempo, e so depois
            # sao conferidos. Escrever e ler um por um deixaria o dado no
            # cache do processador e o teste medaria o cache, nao a RAM.
            blocos = []
            for i in range(pedacos):
                if cancelado():
                    r.interrompido = True
                    break
                blocos.append(bytearray(esperado))
                percentual(int((indice + i / pedacos) / len(PADROES) * 100))

            for i, bloco in enumerate(blocos):
                if cancelado():
                    r.interrompido = True
                    break
                if bytes(bloco) != esperado:
                    r.erros += 1
                    # Localizar o primeiro byte divergente ajuda a decidir
                    # se e um pente so ou a placa inteira.
                    posicao = next(
                        (j for j, valor in enumerate(bloco)
                         if valor != byte[0]), -1)
                    r.detalhes.append(
                        f"padrão {nome}, bloco {i}, deslocamento {posicao}")
                r.testado += BLOCO

            blocos.clear()
            r.padroes += 1
            if r.interrompido:
                break

    except MemoryError:
        r.erro = ("Memória insuficiente para o teste. Feche programas e "
                  "tente de novo.")
    percentual(100)
    r.segundos = round(time.perf_counter() - inicio, 1)
    relatar(f"{formatar_bytes(r.testado)} verificados em {r.segundos}s — "
            f"{r.erros} erro(s).")
    return r
