# Ripper

Utilitário de suporte técnico para Windows 10/11. Diagnóstico, limpeza,
rede, programas, reparo e relatórios numa janela só, compilável em um
`.exe` que roda sem Python instalado.

Ferramenta de uso interno, não distribuída a clientes.

## Rodar do código

```bash
python -m venv .venv
.venv\Scripts\pip install -r requisitos.txt
.venv\Scripts\python principal.py
```

## Gerar o executável

```bash
.venv\Scripts\python construir.py
```

Saída: `dist/Ripper.exe` — arquivo único, ~48 MB, sem
dependência externa na máquina onde roda.

> **Não use `tecnico/__main__.py` como entrada do PyInstaller.** Ele usa
> import relativo e o PyInstaller o analisa como script solto: o Qt não
> entra no pacote e o `.exe` sai com 8 MB, abrindo sem janela. A entrada
> correta é `principal.py`, com import absoluto.

## Diagnosticar o próprio app

```bash
Ripper.exe --verificar
Ripper.exe --autoteste
```

Grava `verificacao.txt` ao lado do executável dizendo se cada ilustração
foi encontrada. Como a versão empacotada roda sem console, esse arquivo é
a única forma de investigar "abriu mas a ilustração não apareceu".

## O que faz

| Tela | Função |
| --- | --- |
| **Início** | Grade das oito funções. Rede e disco são verificados sozinhos ao abrir. |
| **Roteiro** | A sequência inteira de atendimento num clique, terminando no PDF. |
| **Diagnóstico** | Equipamento, saúde, bateria, licenciamento, segurança, impressoras e espaço para upgrade. |
| **Limpeza** | Temporários, maiores pastas do disco e processos que estão pesando agora. |
| **Rede** | Testa em camadas: adaptador, gateway, internet, DNS. Velocidade e varredura de Wi-Fi. |
| **Programas** | Instalados, inicialização, apps de fábrica, tarefas agendadas e extensões de navegador. |
| **Reparo** | SFC, DISM, CHKDSK, ponto de restauração, reset de rede, Windows Update, índice. |
| **Manutenção** | Instalação em lote, backup de perfil, pré-formatação e ativação do Windows. |
| **Relatórios** | Varre tudo, aponta por gravidade, compara antes/depois e exporta o PDF. |
| **Entrega** | Checklist conferido, testes de tela e teclado, e a pasta do cliente. |
| **Histórico** | Atendimentos gravados por número de série, com exportação em CSV. |

### Teste de velocidade

Baixa 25 MB e cronometra, com **velocímetro ao vivo** — o ponteiro segue
a taxa parcial enquanto o download acontece, não só o número final.

Três servidores tentados em ordem: Cloudflare, Hetzner, OVH. Ter mais de
um não é excesso de zelo: a Cloudflare devolve 403 depois de várias
medições seguidas do mesmo IP, e rede corporativa costuma liberar um
provedor e barrar outro.

Não usa biblioteca de speedtest — elas trazem dependência pesada e
dependem de lista de servidores que muda. `urllib` da biblioteca padrão
resolve, e o número que interessa é o mesmo.

O endpoint recusa User-Agent desconhecido com 403, então o app se
identifica como navegador. Não é disfarce: é o formato que o serviço
aceita.

**Escala do velocímetro é não linear.** As marcas (0, 1, 5, 10, 25, 50,
100, 250, 500, 1000) ocupam fatias iguais do arco. Numa escala linear de
0 a 1000, uma conexão de 20 Mbps ficaria colada no zero e o ponteiro não
diria nada.

## Antes e depois

`Marcar estado inicial` fotografa disco livre, lixo, itens de
inicialização, programas e memória. No fim do atendimento, `Comparar com
o inicial` gera a tabela que entra no PDF — a prova numérica do serviço.

Cada comparação tem uma **faixa morta** (50 MB no disco, 10 MB no lixo,
3 pontos de memória). A máquina nunca fica parada: o Windows grava log e
cache sozinho entre as duas medições. Sem a faixa morta o relatório
anunciaria melhorias que ninguém fez.

Os instantâneos ficam em
`%LOCALAPPDATA%\Ripper\historico\<série>.jsonl`, um por linha. Quando o
mesmo computador volta, o histórico mostra se o problema é recorrente.

**A chave é o número de série, com cadeia de reserva.** Desktop montado
quase sempre traz `To Be Filled By O.E.M.` no BIOS — todas essas máquinas
cairiam no mesmo arquivo, misturando clientes. A ordem é: série do
sistema, série da placa-mãe, UUID, nome do computador.

## Linha de comando

O `.exe` é compilado com `--windowed` e não tem console próprio.
`AttachConsole(-1)` pega emprestado o console de quem chamou, então a
saída aparece no cmd ou PowerShell aberto. Sem isso o modo funcionaria em
silêncio absoluto.

```
Ripper.exe --marcar-antes
Ripper.exe --relatorio --comparar --saida D:\cliente\
Ripper.exe --verificar
```

`--saida` aceita arquivo ou pasta; sendo pasta, o nome sai com carimbo de
hora. Código de saída **1** quando aparece apontamento de gravidade alta,
para o `.bat` de atendimento poder parar e chamar o técnico.

## Roteiro de atendimento

A tela **Roteiro** roda a sequência inteira em ordem fixa e termina no PDF.
As etapas que alteram a máquina — limpeza e SFC — vêm **desmarcadas** e
pedem confirmação; as de leitura vêm marcadas porque não custam nada.

A ordem virou código e não instrução, por dois motivos concretos:

- O estado inicial é medido **antes** de qualquer alteração. Invertido, o
  relatório mostraria zero de ganho.
- O teste de disco roda **depois** do estado final. Ele escreve e lê
  192 MB, o que move o uso de memória — rodando antes, sujava a comparação
  com uma piora causada pela própria medição. Isso apareceu no primeiro
  teste real e a ordem foi corrigida.

## Medição de disco

Escreve, lê de volta e apaga um arquivo de 192 MB usando
`FILE_FLAG_NO_BUFFERING`. Sem isso o teste mediria a RAM: o Windows serve
o arquivo recém-escrito do cache e acusa 3 GB/s até num HD velho.

O preço do flag é alinhamento de setor — buffer, deslocamento e tamanho
precisam ser múltiplos do setor. `VirtualAlloc` devolve memória alinhada à
página (4096), que satisfaz qualquer disco atual.

O número que importa é a **leitura aleatória de 4 KB**, não a sequencial:
abrir o Windows são milhares de leituras pequenas espalhadas, não uma
cópia de arquivo grande. HD mecânico entrega ~0,5 MB/s ali; SSD NVMe passa
de 40 MB/s. Essa diferença de quase cem vezes é o argumento da troca.

## Pré-formatação

| O quê | Como |
| --- | --- |
| Drivers de terceiros | `pnputil /export-driver` para salvar, `/add-driver /subdirs /install` para restaurar. Exige administrador. |
| Chave OEM e ativação | `OA3xOriginalProductKey` e `SoftwareLicensingProduct`. Diz se a licença sobrevive à formatação. |
| Senhas de Wi-Fi | `netsh wlan export profile key=clear` gera XML; o app lê e apaga o arquivo temporário. |
| Apps de fábrica | Catálogo curado de 39 pacotes AppX conhecidos. |

**A listagem de drivers usa CIM, não `pnputil /enum-drivers`.** A saída do
pnputil é texto traduzido ("Nome do Provedor"), que quebraria em Windows
inglês. O CIM devolve os mesmos dados com nomes de campo fixos.

**O catálogo de bloatware é lista branca.** O Windows marca 46 dos 91
pacotes desta máquina como removíveis, e seria tentador oferecer todos —
mas essa lista inclui o pacote de idioma pt-BR, os codecs HEIF/HEVC (sem
eles as fotos do celular param de abrir) e os programas que o cliente
instalou. Item desconhecido fica de fora.

## Onde adware se esconde

A aba **Tarefas e extensões** cobre o que Programas e Inicialização não
pegam: tarefa agendada que roda script a cada logon, e extensão de
navegador que sequestra a busca. Lê Chrome, Edge, Brave, Vivaldi e Opera
(que guarda o perfil no Roaming, ao contrário dos outros Chromium).

O app aponta **indícios, não veredictos**: "executa script a partir de
pasta de usuário" é fato observável; chamar de vírus seria chute.

## Modo pendrive

Criar uma pasta `dados` ao lado do executável faz o histórico e a
configuração morarem ali, em vez de `%LOCALAPPDATA%`.

A marca é explícita de propósito. Testar se a unidade é removível falha
nos dois sentidos: HD externo aparece como fixo e cartão SD interno de
notebook aparece como removível.

## Ponto de restauração

Criado automaticamente antes de SFC, DISM, reset de rede, reset do Windows
Update e reindexação.

**E conferido depois.** `Checkpoint-Computer` devolve sucesso mesmo quando
não cria nada: o Windows ignora pedidos se já houve um ponto nas últimas
24 horas, e faz o mesmo silenciosamente quando a Proteção do Sistema está
desligada — o padrão em boa parte das máquinas de fábrica. O app compara o
último ponto antes e depois; se não mudou, avisa que não há rede de
segurança e segue mesmo assim, porque o técnico pediu o reparo.

## Ordem de serviço

A aba **Ficha**, em Relatórios, guarda cliente, telefone, equipamento,
defeito relatado e serviço executado. Ela abre o PDF, antes de qualquer
número: sem isso o documento é um laudo sem dono.

Fica gravada por número de série junto com o histórico, e é recuperada
sozinha quando a mesma máquina volta — o que o cliente reclamou da outra
vez costuma ser o mesmo de agora. Uma ficha por máquina, sempre a última:
guardar todas viraria arquivo morto sem tela para navegar.

## Autoteste

A máquina de desenvolvimento roda sem elevação, então exportar drivers,
ler senhas de Wi-Fi, criar ponto de restauração e consultar SMART sempre
paravam na guarda de permissão — o caminho de sucesso nunca era exercitado.

```
Ripper.exe --autoteste
```

Aberto como administrador, ele roda esses caminhos e grava
`autoteste.txt` ao lado do executável. Tudo que escreve vai para pasta
temporária e é apagado no fim.

**Duas coisas ele não executa, de propósito.** Limpar a fila de impressão
descarta todos os trabalhos pendentes de todos os usuários, e não há
versão inofensiva disso — um teste que apaga o trabalho de alguém não é
teste, é acidente. Restaurar drivers instala pacotes no repositório do
Windows e pode pedir reinício. Nos dois casos o autoteste vai até a
validação e para.

## Testes

```bash
python -m unittest discover -s testes
```

62 testes sobre as funções que têm consequência. Nenhum toca o disco: são
regras puras, que é justamente onde regressão passa despercebida.

O mais importante é `testes/test_seguranca_de_apagar.py`, que cerca
`_dentro_da_lista_branca` — a última coisa que roda antes de um `unlink`.
Ele cobre os casos que enganariam uma comparação por texto: `C:\Windows\Temp2`
começa com `C:\Windows\Temp` e precisa ser recusado, e um caminho com `..`
que sobe até Documentos também.

**A suíte foi validada reintroduzindo bugs reais.** Os três que eu já havia
corrigido nesta ferramenta — "serviço parado = suspeito", faixa morta do
disco zerada, e comparar `alerta` só com string vazia — foram colocados de
volta, um a um, e a suíte acusou os três. Um conjunto de testes que passa
mas não pega nada é pior que nenhum, porque dá confiança falsa.

## Quando algo dá errado

**Falha não tratada vira arquivo.** O `.exe` é compilado com `--windowed` e
não tem console: sem `sys.excepthook`, uma exceção fecharia a janela sem
deixar vestígio nenhum — o que na máquina de um cliente vira "o programa
sumiu" e acaba a investigação. Agora o traceback vai para
`falhas/AAAA-MM-DD_HHMMSS.txt` com hora, versão, nível de permissão e onde
os dados moram, e uma caixa diz ao técnico o caminho do arquivo.

**Duas instâncias são bloqueadas por mutex nomeado.** Duas cópias abertas
gravam histórico e ficha uma por cima da outra sem perceber, e travam o
próprio executável para regravação — o que aconteceu durante o
desenvolvimento. O segundo processo descobre que já existe um antes de
abrir qualquer janela.

## Resumo em imagem

O PDF é para imprimir, anexar e arquivar. Na prática o cliente pergunta
pelo WhatsApp, e lá um PDF vira "baixar arquivo" que metade das pessoas não
abre. O botão **Resumo em imagem** gera um PNG de 1080 px de largura com o
que mudou, os pontos de atenção e o checklist.

Entra o que o cliente entende. Fica de fora tudo que só interessa ao
técnico — IOPS, canal de Wi-Fi, nome de pacote AppX. Resumo que precisa de
tradução não é resumo.

## O que o teste elevado confirmou

Rodado como administrador em 30/08/2026, `--autoteste` deu:

| Passo | Resultado |
| --- | --- |
| Listar drivers de terceiros | 22 pacotes |
| Exportar drivers | **37 pacotes** exportados |
| Pasta de restauração válida | 37 arquivos `.inf` |
| Senhas de Wi-Fi | pulado — máquina sem adaptador |
| Criar ponto de restauração | recusado pela regra de 24 h |
| Contadores SMART | **3 de 3 discos** (sem elevação era 0 de 3) |
| Limpar fila de impressão | pulado por ser destrutivo |

Duas coisas mudaram no código por causa disso.

**O ponto de restauração não estava falhando.** A mensagem dizia "a
Proteção do Sistema está desativada, ou já houve um ponto nas últimas
24 horas" — duas hipóteses sem distinção. O relatório mostrou
`antes=27|20260829055936` e `depois` idêntico: existia um ponto de 21 h
antes, e o Windows recusa criar outro no mesmo dia. A proteção estava
ligada o tempo todo. Agora o app parseia a data no formato `CIM_DATETIME`
do WMI e diz qual dos dois casos é, porque mandar o técnico caçar uma
proteção desativada que está ativa custa tempo de bancada.

**Ponto de restauração é invisível sem elevação.** `Get-ComputerRestorePoint`
não devolve nada e não reclama. Quem chamar `_ultimo_ponto()` sem checar
admin antes vai concluir que a máquina nunca teve ponto.

**Listar 22 e exportar 37 é o comportamento certo.** O CIM só enxerga
driver preso a dispositivo conectado agora; o repositório do Windows
guarda também os da impressora que ficou na outra sala e do dock
desconectado. A exportação leva tudo de propósito — o que falta na máquina
nova é justamente o driver do periférico que não estava plugado no dia. A
tela avisa isso para o técnico não achar que exportou demais.

## Ativação

O painel de Ativação instala uma chave que **o cliente forneceu**
(`slmgr /ipk`), dispara a ativação oficial (`slmgr /ato`), lê o detalhe da
licença e explica por que a ativação falhou.

**Ele não contorna licenciamento.** Não emula servidor KMS, não aplica
HWID forjado, não instala chave genérica de volume. O caso que resolve é o
honesto e o mais comum na bancada: máquina que tem licença e perdeu a
ativação depois de formatar ou trocar placa-mãe.

**O diagnóstico vem antes dos botões, de propósito.** Desde o Windows 10 a
maioria das máquinas de varejo tem licença digital atrelada à conta ou ao
hardware — nesses casos não há chave para digitar, e pedir uma ao cliente
só atrasa o atendimento. A orientação muda conforme o canal detectado:
OEM, varejo, volume ou digital.

## Entrega

Checklist do que se confere antes de devolver. Metade verifica sozinha —
áudio, rede, Wi-Fi, câmera, bateria — e metade não: tela, teclado, portas
USB e o que foi devolvido em mãos. **Marcar automaticamente um item que
ninguém testou seria pior que não ter checklist**, então esses ficam em
branco.

Entra no PDF como última seção, com linha de assinatura para técnico e
cliente.

**Teste de tela** percorre seis campos de cor em tela cheia: branco pega
pixel morto, preto pega pixel travado aceso, as primárias pegam falha de
subpixel, cinza revela mancha de retroiluminação que some no branco puro.

**Teste de teclado** desenha um layout ABNT2 e acende cada tecla acionada.
Não é o teclado inteiro — numérico e teclas de mídia variam demais entre
modelos, e um layout que não bate com a máquina do cliente confunde mais
do que ajuda.

**Exportar pasta do cliente** junta PDF, histórico, ficha e registro numa
pasta com nome e data. A pesquisa sobre suporte aponta fragmentação de
ferramentas como uma das duas maiores dores do dia a dia.

## Espaço para upgrade

O Diagnóstico já dizia quanta memória a máquina tem. O que decide venda é
outra coisa: quantos slots estão **livres**, que tipo de pente cabe e até
quanto a placa aceita. Sem isso o técnico precisa abrir o gabinete ou
caçar o manual da placa para dar um preço.

## Visual

A interface segue a linguagem do **Cyberpunk 2077**: amarelo `#FCEE0A`
sobre preto, tipografia **Rajdhani** (a fonte da interface do jogo,
licença OFL, embutida no `.exe`), cantos chanfrados e seleção invertida —
bloco amarelo sólido com texto preto.

**O amarelo não participa da escala de alerta.** Ele é a cor do próprio
aplicativo: seleção, foco, moldura ativa, cabeçalho. Os avisos têm escala
separada — ciano tranquilo, âmbar atenção, vermelho ação necessária. Sem
essa separação, uma tela cheia de amarelo de interface faria o amarelo de
aviso desaparecer no meio. A crítica mais comum ao HUD do próprio jogo é
justamente ter vermelho demais sem código de cor consistente.

**Chanfro é desenhado, não estilizado.** O QSS só sabe arredondar
(`border-radius`); cortar canto exige `QPainter`. Fica em
[tecnico/ui/chanfro.py](tecnico/ui/chanfro.py), e os widgets pintam a si
mesmos.

**Vinheta em vez de distorção real.** O HUD do jogo é curvado por um
shader, para parecer projetado dentro dos olhos do personagem e não colado
na tela. Distorcer de verdade exigiria renderizar a janela numa textura a
cada quadro; a vinheta compra quase toda a leitura por quase nada, porque o
que o olho registra como curvatura é a queda de luz nas quinas, não a
geometria.

**Faixa de status contextual.** O HUD do jogo muda conforme a tarefa. Aqui
uma linha fina diz sempre em que máquina se está mexendo e o que roda
agora — e resolve um problema prático: o técnico troca de painel o tempo
todo, e sem ela saber se a varredura ainda roda exige voltar até a tela que
a disparou.

**Velocímetro segmentado.** Medidor do jogo é feito de blocos, não de arco
contínuo. Cada bloco acende inteiro, o que torna a leitura discreta e faz o
mostrador parecer instrumento em vez de barra de progresso.

**Números em monoespaçada.** Rajdhani tem largura variável — `1` é muito
mais estreito que `8` — e uma coluna de tamanhos fica serrilhada. Leitura
de dados monoespaçada é característica citada do próprio jogo.

**Abertura em cascata com valores reais.** Fonte carregada, recursos
achados, nível de permissão, onde os dados moram. Inventar texto de enfeite
seria transformar em cenário o que pode ser informação útil nos dois
segundos em que o técnico já está olhando a tela. Pulável com qualquer
clique.

**Scanline permanente, glitch só na troca de painel.** A regra que toda
análise do HUD repete é "um efeito de glitch por tela". Aqui ela vai um
passo além por causa do uso: isto é ferramenta de bancada, aberta oito
horas seguidas. Efeito que pisca sozinho vira ruído e cansa — o oposto do
que faz num jogo, cuja sessão tem hora para acabar. Então o glitch é um
evento com começo e fim, ligado a uma ação do técnico; enquanto ele lê, a
tela fica parada.

**Ícones desenhados em código**, em [tecnico/ui/icones.py](tecnico/ui/icones.py).
Precisam mudar de cor conforme o estado da verificação, e recolorir SVG em
tempo de execução no Qt exige reescrever o XML ou aplicar máscara.

### Uma armadilha que custou caro

`QFontDatabase.families()` sem uma `QGuiApplication` viva **não levanta
exceção — aborta o processo** (`0xC0000409`). Qualquer ferramenta que
importasse o tema fora do app morria sem mensagem nenhuma. Por isso
`familia()` e `registrar_fontes()` checam se há aplicação antes de tocar
no Qt.

## Onde o disco foi parar

A Limpeza acha dezenas de megabytes de temporários. A pergunta do cliente
é outra — "para onde foram os 400 GB" — e quem responde é a aba **Maiores
pastas**, que percorre o disco de verdade até dois níveis da raiz. A aba
**Processos** dá o complemento: o apontamento de "memória sob pressão"
dizia a porcentagem e não o culpado.

## Segurança e serviços

Antivírus registrados na Central de Segurança (dois em tempo real ao mesmo
tempo é causa clássica de lentidão), serviços essenciais e idade da última
atualização.

**Parado não é sinônimo de problema.** No Windows 10 e 11 o Windows Update
e o BITS ficam com inicialização Manual e sobem sob demanda — marcá-los
seria alarme falso em toda máquina saudável, e foi exatamente o que a
primeira versão fez. O que indica interferência é serviço *desabilitado*,
ou parado apesar de estar como *automático*.

Não há tabela de fim de suporte no código de propósito: essas datas mudam
e envelheceriam aqui dentro sem ninguém perceber. O app afirma o que mede
— quando entrou a última correção.

## Teste de memória

Aloca a RAM livre, escreve quatro padrões (`00`, `FF`, `AA`, `55` — os dois
alternados pegam interferência entre linhas vizinhas) e confere.

**Resultado positivo é conclusivo; negativo é apenas indicativo.** A
memória ocupada pelo Windows não pode ser testada porque está em uso, e o
teto de 2 GB existe para o bloco não ser paginado para o disco — aí o
teste conferiria o arquivo de paginação, não o pente. Para varredura
completa, MemTest86 pelo boot.

## Segurança

Três limites no código, não na interface:

1. **Lista branca na limpeza.** `nucleo/limpeza.py` só percorre pastas
   declaradas em `alvos()`. Documentos, área de trabalho e downloads não
   estão lá e não devem entrar.
2. **Varre antes de apagar.** `varrer()` só mede. `limpar()` recebe o
   resultado da varredura — o que sai é exatamente o que foi mostrado.
   Há uma segunda checagem de lista branca antes de cada exclusão.
3. **Confirmação com o comando à vista.** Toda ação de reparo mostra o
   comando exato antes de rodar.

Arquivo em uso é pulado em silêncio — forçar exclusão de arquivo travado
é como se quebra perfil de usuário.

O app **não pede UAC ao abrir**. As telas que precisam avisam na hora.

## Licença

O código deste repositório está sob **GPL-3.0** (arquivo `LICENSE`).

Os recursos de terceiros que viajam junto têm licença própria e
compatível:

| Recurso | Licença | Onde |
| --- | --- | --- |
| Rajdhani (tipografia da interface) | SIL OFL 1.1 | `recursos/fontes/OFL.txt` |
| 3dicons (PNGs, hoje sem uso na interface) | CC0 1.0 | `recursos/icones/LICENSE` |

## Créditos de recursos

**Rajdhani** — Indian Type Foundry, licença SIL Open Font License 1.1.
Arquivos e licença em `recursos/fontes/`. É a tipografia da interface do
Cyberpunk 2077 e viaja dentro do executável, porque a máquina do cliente
não a tem instalada.

Os ícones da grade são desenhados em código. Os PNGs 3D do 3dicons (CC0)
seguem em `recursos/icones/` mas não são mais usados pela interface — o
material de argila, com luz suave e canto arredondado, é o oposto da
linguagem visual atual.

## Estrutura

```
principal.py          entrada (import absoluto)
tecnico/cli.py        modos sem janela (--relatorio, --roteiro, --autoteste)
tecnico/autoteste.py  exercita os caminhos que exigem elevação
construir.py          gera o .exe
tecnico/
  tema.py             paleta, tipografia e QSS
  recursos.py         localizador de assets (dev e empacotado)
  nucleo/
    win.py            ponte com o Windows (subprocesso sem console)
    sistema.py        diagnóstico
    limpeza.py        varredura e limpeza
    rede.py           diagnóstico, correções e teste de velocidade
    programas.py      instalados e inicialização
    reparo.py         ações que alteram o sistema
    otimizacao.py     varredura completa e apontamentos
    saude.py          SMART, eventos críticos, dispositivos, bateria
    roteiro.py        sequência completa de atendimento
    desempenho.py     medição de disco sem cache
    drivers.py        exportação e restauração de drivers
    licenca.py        ativação do Windows e do Office
    wifi.py           redes ao alcance e perfis salvos
    bloatware.py      catálogo de apps de fábrica
    persistencia.py   tarefas agendadas e extensões
    dados.py          modo pendrive, log da sessão
    uso.py            maiores pastas e processos
    seguranca.py      antivírus, serviços, atualizações
    memoria.py        teste de RAM
    ficha.py          ordem de serviço por máquina
    ativacao.py       chave, ativação e diagnóstico de licença
    entrega.py        checklist e pasta do cliente
    inventario.py     slots livres e oportunidades de upgrade
    falhas.py         registro de exceção e trava de instância única
    resumo.py         resumo de uma página em PNG
    impressoras.py    impressoras e fila do spooler
  ui/
    chanfro.py        formas chanfradas e marcação de canto
    efeitos.py        scanline e glitch
    icones.py         ícones angulares desenhados em código
    hud.py            faixa de status e notificações de canto
    abertura.py       sequência de boot
    testes.py         testes de tela e teclado em tela cheia
recursos/fontes/      Rajdhani (OFL) embutida no executável
    manutencao.py     instalação em lote (winget) e backup de perfil
    historico.py      instantâneos, comparação antes/depois, histórico
    pdf.py            relatório em PDF
    relatorio.py      exportação em texto
    tarefa.py         execução em segundo plano
    admin.py          elevação
  ui/
    janela.py         janela principal
    cartao_funcao.py  célula da grade inicial
    widgets.py        botão, cartão, título
    paineis/          uma tela por função
recursos/icones/      ilustrações CC0 + LICENSE
testes/               suíte automatizada (unittest, sem dependência extra)
ferramentas/
  previa_janela.py    renderiza a janela em PNG, sem abrir
  previa_viva.py      idem, após a verificação real rodar
  gerar_icone.py      gera recursos/app.ico
```

### Detalhes que não são óbvios

- **Codificação de subprocesso.** `ipconfig`, `ping` e `netsh` escrevem na
  codepage do console (850 no Brasil), não em UTF-8. `win.rodar` usa
  `encoding="oem"`. PowerShell usa UTF-8.
- **Nada de parsear texto traduzido.** Gateway, DNS e ping vêm de
  `Get-NetIPConfiguration` e `Test-Connection`, que devolvem dados
  estruturados. Regex sobre a saída do `ipconfig` quebra numa máquina em
  inglês.
- **Fechamento seguro.** `Janela.closeEvent` cancela as tarefas e espera o
  pool. Sem isso, fechar durante uma varredura faz o sinal chegar a um
  objeto destruído e o processo cai.
- **Cor no Qt é AARRGGBB.** `QColor("#ffffff22")` é branco opaco
  amarelado, não branco translúcido. O alfa vem primeiro.
