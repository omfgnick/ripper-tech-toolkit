# ripper-tech-toolkit

[English](README.md) · **Português (BR)**

[![CI](https://github.com/omfgnick/ripper-tech-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/omfgnick/ripper-tech-toolkit/actions/workflows/ci.yml)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-informational)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-informational)](requisitos.txt)

Ferramenta de bancada para atendimento em Windows 10/11 — diagnóstico,
limpeza, reparo, checklist de entrega e relatório em PDF assinável — em
**Python + PySide6**, compilada num **executável único** que roda de
pendrive.

Escrita e usada por [Nicolas Mesquita Fernandes](https://github.com/omfgnick)
(NOC / suporte N1–N3) na bancada de verdade. Todo achado que ela reporta foi
verificado contra máquinas reais, não simulado.

> Ela **não** contorna o licenciamento do Windows nem do Office. O painel de
> ativação instala uma chave que o cliente já tem e dispara a ativação
> oficial — nada além disso.

## Layout

```
principal.py        entrada (import absoluto, para o PyInstaller ver a árvore)
construir.py        gera o executável de arquivo único
tecnico/
  nucleo/           31 módulos: leem a máquina, decidem, relatam
  ui/               10 painéis e a camada visual
testes/             96 testes (unittest, sem dependência extra)
docs/decisoes.md    por que cada decisão não óbvia foi tomada
recursos/           Rajdhani (OFL) e ícones Lucide (ISC), embutidos
```

## O fluxo que justifica a ferramenta

Uma tela executa o atendimento inteiro em ordem fixa e termina no PDF:

```
marcar "antes"  →  varredura  →  limpeza  →  SFC  →  marcar "depois"
                →  medir disco  →  checklist de entrega  →  PDF
```

A ordem virou código, e não instrução, por dois motivos que apareceram em
teste. O estado inicial é medido **antes** de qualquer alteração —
invertido, o relatório mostra zero de ganho. E o teste de disco roda
**depois** do fechamento, porque escreve e lê 192 MB, o que move o uso de
memória; rodando antes, ele sujava a comparação com uma piora causada pela
própria medição.

## O que ela mede

| Área | O que reporta |
| --- | --- |
| Hardware | SMART com referência, desgaste de bateria, slots livres e espaço para upgrade |
| Disco | Leitura sequencial e aleatória de 4 KB, sem cache |
| Memória | Teste de RAM em quatro padrões, sem reiniciar |
| Windows | Eventos críticos, dispositivos com problema, licença, serviços, idade das atualizações |
| Rede | Teste em camadas, velocidade contra o plano contratado, canais de Wi-Fi |
| Persistência | Tarefas agendadas e extensões — onde adware se esconde |

Todo achado diz o que **significa** e o que **verificar**. O evento ID 11
não fica em "erro de controladora de disco": ele manda trocar o cabo SATA e
a porta antes de condenar o disco, que é a causa mais barata e a mais comum.

## Três decisões que valem conhecer

**A comparação antes/depois tem faixa morta.** A máquina nunca fica parada —
o Windows grava log e cache sozinho entre as duas medições. Sem a faixa, o
relatório anunciaria "40 MB liberados" que ninguém liberou. Um relatório que
às vezes diz "sem mudança" vale mais que um que inventa resultado.

**A medição de disco contorna o cache.** Ler um arquivo recém-escrito pela
API normal mede a RAM, não o disco: o Windows serve tudo do cache e acusa
3 GB/s até num HD velho. Com `FILE_FLAG_NO_BUFFERING` o número é real — e é
ele que transforma "meu computador está lento" em "seu disco entrega
0,6 MB/s em leitura aleatória; um SSD faz cinquenta vezes isso".

**Toda consulta ao Windows passa por CIM, nunca por texto de console.** A
saída do `ipconfig` e do `pnputil` vem traduzida, e qualquer regex sobre ela
quebra numa máquina em inglês. Aprendido da forma difícil.

## Sobre apagar arquivos

A limpeza trabalha por **lista branca**, e `_dentro_da_lista_branca` confere
cada caminho de novo imediatamente antes do `unlink`. Documentos, Área de
Trabalho e Downloads nunca entram nela.

Essa barreira é o código mais testado do projeto. A suíte cobre os casos que
enganariam uma comparação por texto — `C:\Windows\Temp2` começa com
`C:\Windows\Temp` e precisa ser recusado, assim como um caminho que sobe com
`..`.

## Instalação

Baixe o `Ripper.exe` dos artefatos do CI, ou compile:

```bash
pip install -r requisitos.txt
python construir.py
```

Criar uma pasta chamada `dados` ao lado do executável liga o **modo
pendrive**: histórico, fichas e registros passam a morar ali em vez de
`%LOCALAPPDATA%`, viajando com o pendrive em vez de ficarem espalhados pelas
máquinas dos clientes.

## Linha de comando

O executável é compilado sem console próprio; `AttachConsole(-1)` pega
emprestado o de quem chamou, então a saída aparece no cmd ou PowerShell onde
você o executou.

```bash
Ripper.exe --marcar-antes                          # estado antes do serviço
Ripper.exe --roteiro --com-limpeza                 # roteiro completo com limpeza
Ripper.exe --relatorio --comparar --saida D:\job\  # varredura e PDF
Ripper.exe --autoteste                             # exercita os caminhos elevados
Ripper.exe --verificar                             # confere os recursos empacotados
```

Código de saída **1** quando aparece apontamento de gravidade alta, para o
`.bat` de atendimento poder parar e chamar o técnico.

## Dados e privacidade

Tudo fica local. O histórico é indexado pelo número de série da placa-mãe,
com cadeia de reserva — desktop montado costuma trazer `To Be Filled By
O.E.M.` no BIOS, e sem a reserva todas essas máquinas dividiriam um arquivo
só, misturando clientes diferentes.

Fichas, checklists e registros de sessão ficam em `%LOCALAPPDATA%\Ripper\`
(ou em `dados/` no modo pendrive) e são excluídos deste repositório pelo
`.gitignore`.

## Requisitos

- Windows 10 ou 11
- Python 3.12+ e os pacotes de `requisitos.txt` — só para compilar do código
- Administrador para exportar drivers, ler senhas de Wi-Fi salvas, contadores
  SMART e ponto de restauração. O app detecta a falta e oferece reabrir
  elevado, em vez de falhar no meio da operação.

## Desenvolvimento

```bash
python -m unittest discover -s testes
```

96 testes. Além das regras puras, um teste monta a interface inteira, abre
os dez painéis e chama **todo método público sem argumento obrigatório** — a
lista de exclusões é nominal, então método novo é coberto por padrão. Ele
existe porque três travamentos chegaram ao uso real e nenhum aparecia ao
compilar; o terceiro foi pego por esse teste na primeira execução, antes de
sair.

## Decisões de projeto

O raciocínio por trás das escolhas não óbvias — por que o roteiro tem essa
ordem, por que serviço "parado" quase sempre está certo, por que o tema
claro precisa de dois amarelos — está em [docs/decisoes.md](docs/decisoes.md).

## Créditos

**Rajdhani**, da Indian Type Foundry, SIL OFL 1.1 — a tipografia da
interface do Cyberpunk 2077, embutida porque a máquina do cliente não a tem.
**Lucide**, ISC — SVG monocromático, recolorido em tempo de execução para
sinalizar estado.

## Licença

GPL-3.0. Veja [LICENSE](LICENSE).
