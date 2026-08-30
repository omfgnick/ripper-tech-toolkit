"""Renomeia o produto de Bancada para Ripper.

Duas ocorrencias NAO sao trocadas porque ali "bancada" e o substantivo
comum, nao o nome do produto:

    README.md      "ferramenta de bancada, aberta oito horas"
    tecnico/cli.py "junto com as outras ferramentas da bancada"

Trocar essas duas deixaria o texto sem sentido.
"""

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# (de, para) - ordem importa: os mais especificos primeiro.
TROCAS = [
    ("bancada_autoteste_", "ripper_autoteste_"),
    ("bancada_temp", "ripper_temp"),
    ("bancada_{maquina}", "ripper_{maquina}"),
    ("bancada_{socket.gethostname()}", "ripper_{socket.gethostname()}"),
    ("historico_bancada.csv", "historico_ripper.csv"),
    ("Bancada.exe", "Ripper.exe"),
    ("Bancada - ", "Ripper - "),
    ("Bancada -", "Ripper -"),
    ("BANCADA", "RIPPER"),
    ("Bancada", "Ripper"),
]

# Linhas que contem o substantivo comum e devem ficar intactas.
PRESERVAR = (
    "ferramenta de bancada",
    "ferramentas da bancada",
)

ALVOS = list(RAIZ.glob("*.py")) + list(RAIZ.glob("*.md")) + \
    list((RAIZ / "tecnico").rglob("*.py")) + \
    [RAIZ / "ferramentas" / f for f in ("previa_janela.py", "previa_viva.py",
                                        "gerar_icone.py", "previa_icones.py",
                                        "previa_chanfro.py")]

alterados = 0
for arquivo in ALVOS:
    if not arquivo.is_file() or arquivo.name == pathlib.Path(__file__).name:
        continue
    original = arquivo.read_text(encoding="utf-8")
    linhas = original.split("\n")
    novas = []
    for linha in linhas:
        if any(p in linha for p in PRESERVAR):
            novas.append(linha)
            continue
        for de, para in TROCAS:
            linha = linha.replace(de, para)
        novas.append(linha)
    novo = "\n".join(novas)
    if novo != original:
        arquivo.write_text(novo, encoding="utf-8")
        alterados += 1
        print(f"  {arquivo.relative_to(RAIZ)}")

print(f"{alterados} arquivo(s) alterados.")
