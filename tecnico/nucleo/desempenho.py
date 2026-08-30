r"""Medicao real de velocidade do disco.

Existe para transformar "meu computador esta lento" em numero. Um HD de
5400 rpm entrega uns 0,5 MB/s em leitura aleatoria de 4 KB; um SSD NVMe
passa de 40 MB/s no mesmo teste. Essa diferenca de quase cem vezes e a
razao pela qual o Windows demora dois minutos para abrir no HD e oito
segundos no SSD - e o argumento que vende a troca.

POR QUE I/O SEM BUFFER
    Ler um arquivo recem-escrito com a API normal mede a memoria RAM, nao
    o disco: o Windows serve tudo do cache e o teste acusa 3 GB/s ate num
    HD velho. FILE_FLAG_NO_BUFFERING desliga esse cache e faz cada leitura
    ir ao dispositivo.

    O preco e que o Windows passa a exigir alinhamento de setor: buffer,
    deslocamento e tamanho precisam ser multiplos do tamanho do setor.
    VirtualAlloc devolve memoria alinhada a pagina (4096), que satisfaz
    qualquer setor de disco atual.
"""

from __future__ import annotations

import ctypes
import os
import random
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_WRITE_THROUGH = 0x80000000
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
INVALID_HANDLE = ctypes.c_void_p(-1).value

SETOR = 4096
BLOCO = 1024 * 1024          # 1 MB por leitura sequencial
TAMANHO_PADRAO = 192 * 1024 * 1024
AMOSTRAS_ALEATORIAS = 800

# use_last_error: sem isso GetLastError volta zerado e o erro
# real do Windows se perde no caminho.
k32 = ctypes.WinDLL('kernel32', use_last_error=True)


@dataclass
class Medida:
    leitura_sequencial: float = 0.0    # MB/s
    escrita_sequencial: float = 0.0    # MB/s
    leitura_aleatoria: float = 0.0     # MB/s em blocos de 4 KB
    iops: int = 0
    unidade: str = ""
    tipo: str = ""                     # "SSD" | "HDD" | ""
    erro: str = ""

    @property
    def veredito(self) -> str:
        """Frase para o relatorio, ancorada na leitura aleatoria.

        A aleatoria e a que o usuario sente: abrir o Windows e carregar
        programa sao milhares de leituras pequenas espalhadas, nao uma
        copia sequencial de arquivo grande.
        """
        if self.erro:
            return ""
        if self.leitura_aleatoria >= 20:
            return "Desempenho compatível com SSD moderno."
        if self.leitura_aleatoria >= 5:
            return "Desempenho de SSD de entrada ou SSD saturado."
        if self.leitura_aleatoria >= 1.5:
            return "Lento para uso diário. Compatível com HD mecânico."
        return ("Muito lento. Trocar por SSD muda a experiência de uso "
                "mais que qualquer outro upgrade.")


class _BufferAlinhado:
    """Memoria alinhada a pagina, exigencia do FILE_FLAG_NO_BUFFERING."""

    def __init__(self, tamanho: int):
        self.tamanho = tamanho
        k32.VirtualAlloc.restype = ctypes.c_void_p
        self.ponteiro = k32.VirtualAlloc(
            None, ctypes.c_size_t(tamanho), MEM_COMMIT | MEM_RESERVE,
            PAGE_READWRITE)
        if not self.ponteiro:
            raise MemoryError("VirtualAlloc falhou")

    def preencher(self) -> None:
        # Dados variados: setor cheio de zero pode ser comprimido pelo
        # firmware de alguns SSDs e inflar o resultado da escrita.
        ctypes.memmove(self.ponteiro, random.randbytes(self.tamanho),
                       self.tamanho)

    def liberar(self) -> None:
        if self.ponteiro:
            k32.VirtualFree(ctypes.c_void_p(self.ponteiro), 0, MEM_RELEASE)
            self.ponteiro = None


def _abrir(caminho: Path, escrita: bool) -> int:
    acesso = GENERIC_WRITE if escrita else GENERIC_READ
    criacao = CREATE_ALWAYS if escrita else OPEN_EXISTING
    bandeiras = FILE_FLAG_NO_BUFFERING
    if escrita:
        bandeiras |= FILE_FLAG_WRITE_THROUGH

    k32.CreateFileW.restype = ctypes.c_void_p
    alca = k32.CreateFileW(ctypes.c_wchar_p(str(caminho)), acesso,
                           FILE_SHARE_READ, None, criacao, bandeiras, None)
    if alca == INVALID_HANDLE or alca is None:
        codigo = ctypes.get_last_error()
        if codigo == 5:
            raise OSError(f"sem permissão de escrita em {caminho.parent}")
        raise OSError(f"não foi possível abrir {caminho} (erro {codigo})")
    return alca


def _ler(alca: int, buffer: _BufferAlinhado, quantos: int) -> int:
    lidos = wintypes.DWORD(0)
    ok = k32.ReadFile(ctypes.c_void_p(alca), ctypes.c_void_p(buffer.ponteiro),
                      quantos, ctypes.byref(lidos), None)
    return lidos.value if ok else 0


def _posicionar(alca: int, deslocamento: int) -> None:
    alto = wintypes.LONG(deslocamento >> 32)
    k32.SetFilePointer(ctypes.c_void_p(alca), deslocamento & 0xFFFFFFFF,
                       ctypes.byref(alto), 0)


def _local_gravavel(raiz: Path) -> Path:
    r"""Onde escrever o arquivo de teste dentro da unidade pedida.

    A raiz de C:\ nao aceita escrita de usuario comum desde o Windows 7.
    No disco do sistema o teste vai para o %TEMP% do proprio usuario; nos
    demais, para uma subpasta que e apagada junto com o arquivo.
    """
    import tempfile

    sistema = os.environ.get("SystemDrive", "C:").rstrip("\\").lower()
    if str(raiz).rstrip("\\").lower() == sistema:
        return Path(tempfile.gettempdir())

    destino = raiz / "ripper_temp"
    try:
        destino.mkdir(exist_ok=True)
        return destino
    except OSError:
        return raiz


def _tipo_da_unidade(letra: str) -> str:
    from . import saude
    try:
        for disco in saude.discos():
            if disco.tipo:
                return disco.tipo
    except OSError:
        pass
    return ""


def medir(unidade: str = "", tamanho: int = TAMANHO_PADRAO,
          relatar=lambda _: None, percentual=lambda _: None,
          cancelado=lambda: False) -> Medida:
    """Escreve um arquivo de teste, le de volta sem cache e apaga."""
    import shutil

    unidade = unidade or os.environ.get("SystemDrive", "C:")
    raiz = Path(unidade + "\\" if not unidade.endswith("\\") else unidade)
    m = Medida(unidade=str(raiz), tipo=_tipo_da_unidade(unidade))

    try:
        livre = shutil.disk_usage(str(raiz)).free
    except OSError as erro:
        m.erro = f"Unidade indisponível: {erro}"
        return m
    # Margem larga: encher o disco durante o teste e pior que nao testar.
    if livre < tamanho * 3:
        m.erro = "Espaço livre insuficiente para o teste."
        return m

    arquivo = _local_gravavel(raiz) / "bancada_teste_disco.tmp"
    buffer = None
    alca = None
    try:
        buffer = _BufferAlinhado(BLOCO)
        buffer.preencher()
        blocos = tamanho // BLOCO

        # ---- escrita sequencial ----
        relatar("Medindo escrita...")
        alca = _abrir(arquivo, escrita=True)
        escritos = wintypes.DWORD(0)
        inicio = time.perf_counter()
        for i in range(blocos):
            if cancelado():
                break
            k32.WriteFile(ctypes.c_void_p(alca),
                          ctypes.c_void_p(buffer.ponteiro), BLOCO,
                          ctypes.byref(escritos), None)
            percentual(int(i / blocos * 40))
        decorrido = time.perf_counter() - inicio
        k32.CloseHandle(ctypes.c_void_p(alca))
        alca = None
        if decorrido > 0:
            m.escrita_sequencial = (blocos * BLOCO) / decorrido / 1e6

        if cancelado():
            return m

        # ---- leitura sequencial ----
        relatar("Medindo leitura sequencial...")
        alca = _abrir(arquivo, escrita=False)
        inicio = time.perf_counter()
        lidos_total = 0
        for i in range(blocos):
            if cancelado():
                break
            lidos_total += _ler(alca, buffer, BLOCO)
            percentual(40 + int(i / blocos * 35))
        decorrido = time.perf_counter() - inicio
        if decorrido > 0 and lidos_total:
            m.leitura_sequencial = lidos_total / decorrido / 1e6

        # ---- leitura aleatoria de 4 KB ----
        relatar("Medindo leitura aleatória...")
        maximo = (tamanho // SETOR) - 1
        inicio = time.perf_counter()
        feitas = 0
        for i in range(AMOSTRAS_ALEATORIAS):
            if cancelado():
                break
            _posicionar(alca, random.randint(0, maximo) * SETOR)
            if _ler(alca, buffer, SETOR):
                feitas += 1
            if i % 50 == 0:
                percentual(75 + int(i / AMOSTRAS_ALEATORIAS * 25))
        decorrido = time.perf_counter() - inicio
        if decorrido > 0 and feitas:
            m.leitura_aleatoria = (feitas * SETOR) / decorrido / 1e6
            m.iops = int(feitas / decorrido)

    except (OSError, MemoryError) as erro:
        m.erro = str(erro)
    finally:
        if alca:
            k32.CloseHandle(ctypes.c_void_p(alca))
        if buffer:
            buffer.liberar()
        try:
            arquivo.unlink(missing_ok=True)
        except OSError:
            pass

    percentual(100)
    return m
