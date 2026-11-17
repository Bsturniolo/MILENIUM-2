"""Arma index.html (documento completo) a partir de mostrador.src.html."""
import pathlib
root = pathlib.Path(__file__).resolve().parent.parent
src = (root / "mostrador.src.html").read_text(encoding="utf-8")
cut = src.index("</style>") + len("</style>")
head, body = src[:cut], src[cut:]
html = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n'
        + head + '\n</head>\n<body>' + body + '\n</body>\n</html>\n')
(root / "index.html").write_text(html, encoding="utf-8")
print("index.html listo")
