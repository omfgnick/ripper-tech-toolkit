import pathlib, re

trocas_texto = [
    ('APLICATIVO = "Bancada"', 'APLICATIVO = "Bancada"'),
    ('"Bancada"', '"Bancada"'),
    ("Bancada", "Bancada"),
    ("Bancada", "Bancada"),
    ("bancada", "bancada"),
]

alvos = []
for padrao in ("*.py", "*.md", "*.txt"):
    alvos += list(pathlib.Path("tecnico").rglob(padrao))
    alvos += list(pathlib.Path("ferramentas").rglob(padrao))
alvos += [pathlib.Path(n) for n in
          ("principal.py", "construir.py", "README.md", "requisitos.txt")]

tocados = 0
for caminho in alvos:
    if not caminho.is_file():
        continue
    s = original = caminho.read_text(encoding="utf-8")
    for velho, novo in trocas_texto:
        s = s.replace(velho, novo)
    if s != original:
        caminho.write_text(s, encoding="utf-8")
        tocados += 1

print(f"arquivos atualizados: {tocados}")

# O nome do arquivo do relatorio tambem carrega a marca
for modulo in ("tecnico/nucleo/relatorio.py", "tecnico/nucleo/pdf.py"):
    p = pathlib.Path(modulo)
    s = p.read_text(encoding="utf-8")
    s = s.replace('f"atendimento_{maquina}_{carimbo}.txt"',
                  'f"bancada_{maquina}_{carimbo}.txt"')
    s = s.replace('f"atendimento_{socket.gethostname()}_{carimbo}.pdf"',
                  'f"bancada_{socket.gethostname()}_{carimbo}.pdf"')
    p.write_text(s, encoding="utf-8")
print("nome do arquivo de relatorio atualizado")
