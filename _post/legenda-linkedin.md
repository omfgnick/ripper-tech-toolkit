# Post para LinkedIn — Ripper

## Legenda

Todo atendimento técnico começa igual: abrir cinco ferramentas diferentes,
anotar o que achou num papel, e no fim explicar ao cliente o que foi feito.
A parte que sempre me incomodou é a última — dizer "limpei e otimizei" sem
número nenhum para mostrar.

Construí o Ripper para resolver isso. É um utilitário de bancada para
Windows 10/11, em PySide6, que compila num executável único e roda de
pendrive.

O que ele faz: um roteiro executa diagnóstico, limpeza e reparo na ordem
certa e termina num PDF assinável, com comparação antes/depois e histórico
por número de série da placa.

Três decisões que valeram mais do que parecem:

▸ A comparação antes/depois tem faixa morta. A máquina nunca fica parada —
o Windows grava log sozinho entre as duas medições. Sem essa faixa, o
relatório anunciaria "40 MB liberados" que ninguém liberou. Prefiro um
relatório que às vezes diz "sem mudança" a um que inventa resultado.

▸ A medição de disco usa I/O sem cache. Ler um arquivo recém-escrito pela
API normal mede a RAM, não o disco: o Windows serve tudo do cache e acusa
3 GB/s até num HD velho. Com FILE_FLAG_NO_BUFFERING o número é real — e é
ele que transforma "seu computador está lento" em "seu HD entrega 0,6 MB/s
em leitura aleatória; um SSD faz cinquenta vezes isso".

▸ Toda consulta ao Windows passa por CIM, não por texto de console. A
saída do ipconfig e do pnputil vem traduzida, e qualquer regex sobre ela
quebra numa máquina em inglês. Aprendi isso da forma difícil.

A limpeza usa lista branca com dupla verificação antes de cada exclusão, e
essa é a parte mais testada do projeto: são 96 testes, e os que cercam a
função que autoriza apagar arquivo cobrem os casos que enganariam uma
comparação por texto.

Código aberto sob GPL-3.0:
github.com/omfgnick/ripper-tech-toolkit

#Python #Windows #SysAdmin #SuporteTecnico #OpenSource #Qt


## Notas de uso

- **Imagem:** `ripper-linkedin.png` (1200x1270). O LinkedIn corta o topo e a
  base em alguns tamanhos de tela; o título e o link estão com margem
  suficiente para sobreviver ao corte.
- **Primeiro comentário:** vale repetir o link do repositório ali. O
  LinkedIn reduz o alcance de post com link externo no corpo.
- **Tamanho:** a legenda tem cerca de 1.900 caracteres. O limite é 3.000, e
  o "ver mais" corta perto de 200 — por isso as duas primeiras linhas
  carregam o gancho.
