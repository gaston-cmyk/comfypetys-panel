#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pendientes.py — la lista de lo que hay que arreglar, sacada del panel.

El panel ya se audita solo: cuenta el stock negativo, los SKU repartidos en
varias filas, los despachos que salieron sin descontar. Pero todo eso vive
desparramado entre 21 secciones, y lo que uno quiere a la mañana es una lista
ordenada por urgencia.

Esto lee el panel y escupe esa lista.

CÓMO SE USA
-----------
    python3 herramientas/pendientes.py index.html

Si el panel ya está cifrado, pasale la clave y lo abre igual:

    python3 herramientas/pendientes.py index.html --clave-archivo ~/.comfypetys/clave_panel

Opciones:
    --markdown      sale en markdown, para pegar en un mail o un documento
    --dias N        cuántos días de cobertura considerar urgente (por defecto 10)

No modifica nada.
"""

import argparse
import base64
import gzip
import json
import os
import re
import sys

PATRON_SNAP = re.compile(r'<script id="snap" type="application/json">(.*?)</script>', re.S)
PATRON_CIFRADO = re.compile(
    r'const SALT="([^"]+)", NONCE="([^"]+)", ITER=(\d+), DATA="([^"]+)"')


# ---------------------------------------------------------------- abrir panel
def descifrar(html: str, clave: str) -> str:
    """Abre un panel cifrado por cerrar_panel.py. Es el mismo procedimiento que
    hace el navegador, pero en Python."""
    import hashlib
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        sys.exit("Para abrir un panel cifrado hace falta:  pip install cryptography")

    m = PATRON_CIFRADO.search(html)
    if not m:
        sys.exit("El archivo parece cifrado pero no encuentro el bloque de datos.")
    sal, nonce, iteraciones, datos = m.groups()
    llave = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"),
                                base64.b64decode(sal), int(iteraciones), dklen=32)
    try:
        comprimido = AESGCM(llave).decrypt(base64.b64decode(nonce),
                                           base64.b64decode(datos), None)
    except Exception:
        sys.exit("Contraseña incorrecta.")
    return gzip.decompress(comprimido).decode("utf-8")


def cargar_datos(ruta: str, clave_archivo: str | None) -> dict:
    with open(ruta, encoding="utf-8") as fh:
        html = fh.read()

    if PATRON_CIFRADO.search(html) and not PATRON_SNAP.search(html):
        if clave_archivo:
            with open(os.path.expanduser(clave_archivo), encoding="utf-8") as fh:
                clave = fh.read().strip()
        else:
            import getpass
            clave = getpass.getpass("El panel está cifrado. Contraseña: ").strip()
        html = descifrar(html, clave)

    m = PATRON_SNAP.search(html)
    if not m:
        sys.exit("No encuentro el bloque de datos en el archivo.")
    return json.loads(m.group(1))


# ------------------------------------------------------------------- utilidad
def producto(item: dict) -> str:
    partes = [item.get("modelo", "")]
    for campo in ("color", "talle"):
        if item.get(campo):
            partes.append(item[campo])
    return " · ".join(p for p in partes if p)


class Salida:
    """Junta el informe, en texto o en markdown."""

    def __init__(self, markdown: bool):
        self.md = markdown
        self.lineas = []
        self.bloques = 0

    def titulo(self, texto: str, generado: str):
        if self.md:
            self.lineas += [f"# {texto}", "", f"Panel generado el {generado}.", ""]
        else:
            self.lineas += ["", f"  {texto.upper()}", f"  panel generado el {generado}",
                            "  " + "─" * 62, ""]

    def seccion(self, numero: int, texto: str, detalle: str = ""):
        self.bloques += 1
        if self.md:
            self.lineas += ["", f"## {numero}. {texto}", ""]
            if detalle:
                self.lineas += [f"_{detalle}_", ""]
        else:
            self.lineas += ["", f"  {numero}. {texto.upper()}"]
            if detalle:
                self.lineas.append(f"     {detalle}")
            self.lineas.append("")

    def item(self, texto: str, valor: str = ""):
        if self.md:
            self.lineas.append(f"- {texto}" + (f" — **{valor}**" if valor else ""))
        else:
            if valor:
                self.lineas.append(f"     {texto[:56]:58} {valor}")
            else:
                self.lineas.append(f"     {texto}")

    def nota(self, texto: str):
        self.lineas.append("" if self.md else "")
        self.lineas.append(f"_{texto}_" if self.md else f"     ({texto})")

    def __str__(self):
        return "\n".join(self.lineas) + "\n"


# -------------------------------------------------------------------- informe
def armar(d: dict, dias_urgente: int, markdown: bool) -> Salida:
    s = Salida(markdown)
    s.titulo("Pendientes del depósito", d.get("generado", "?"))
    n = 0

    # 1 — stock negativo: lo que está mal contado, no lo que falta
    negativos = [i for i in d.get("insumos", [])
                 if isinstance(i.get("stock"), (int, float)) and i["stock"] < 0]
    if negativos:
        n += 1
        s.seccion(n, f"Stock negativo: {len(negativos)} insumos",
                  "El sistema dice que hay menos que cero. Faltan cargar llegadas: "
                  "mientras tanto la reposición sale corta.")
        for i in sorted(negativos, key=lambda x: x["stock"]):
            s.item(i["nombre"], f"{i['stock']:+,}".replace(",", "."))

    # 2 — se agota en pocos días
    agotan = [i for i in d.get("agotamiento", {}).get("items", [])
              if isinstance(i.get("dias"), (int, float)) and i["dias"] <= dias_urgente]
    if agotan:
        n += 1
        s.seccion(n, f"Se agotan en menos de {dias_urgente} días: {len(agotan)}",
                  "Al ritmo de venta de ahora.")
        for i in sorted(agotan, key=lambda x: x["dias"]):
            s.item(producto(i), f"{i['dias']:.1f} días ({i.get('por_dia', 0)}/día)")

    # 3 — faltantes que todavía nadie pidió
    sin_pedir = [f for f in d.get("faltantes", [])
                 if f.get("faltan", 0) > 0 and not f.get("ya_pedido")]
    if sin_pedir:
        n += 1
        s.seccion(n, f"Faltan y no están pedidos: {len(sin_pedir)}",
                  "Hay pedidos esperando estas unidades y todavía no se le pidieron al proveedor.")
        for f in sorted(sin_pedir, key=lambda x: -x["faltan"]):
            s.item(f"{f.get('modelo','')} · {f.get('talle','')}", f"faltan {f['faltan']}")

    # 4 — lo que el propio panel marca como roto
    alertas = d.get("salud", {}).get("alertas", [])
    if alertas:
        n += 1
        s.seccion(n, f"Integridad del dato: {len(alertas)} alertas",
                  "Esto lo detecta el panel solo. Lo de arriba de la lista es lo que "
                  "más ensucia el stock.")
        for a in alertas:
            limpio = re.sub(r"\s+", " ", a).strip()
            s.item(limpio if markdown else limpio[:300])

    # 5 — chequeos del sistema que hace rato no dan OK
    detalle = d.get("salud_sistema", {}).get("detalle", {})
    atrasados = [(k, v["horas_sin_ok"]) for k, v in detalle.items()
                 if isinstance(v, dict) and isinstance(v.get("horas_sin_ok"), (int, float))
                 and v["horas_sin_ok"] >= 3]
    if atrasados:
        n += 1
        s.seccion(n, f"Chequeos atrasados: {len(atrasados)}",
                  "Horas desde la última vez que dieron OK.")
        for k, h in sorted(atrasados, key=lambda x: -x[1]):
            s.item(k, f"{h:.1f} h")

    # 6 — etiquetas viejas
    etiquetas = d.get("etiquetas", {})
    viejos = etiquetas.get("viejos", [])
    if viejos:
        n += 1
        s.seccion(n, f"Pedidos viejos sin etiqueta: {len(viejos)}",
                  f"De {etiquetas.get('sin_imprimir','?')} sin imprimir en total.")
        for v in viejos[:15]:
            s.item(v.get("numero", "?"), v.get("fecha", ""))
        if len(viejos) > 15:
            s.nota(f"y {len(viejos) - 15} más")

    # 7 — los canales que no cuadran
    salud = d.get("salud", {})
    if salud.get("cuadra_tn") is False or salud.get("cuadra_ml") is False:
        n += 1
        s.seccion(n, "Los canales no cuadran")
        if salud.get("cuadra_tn") is False:
            s.item("Tienda Nube: sistema vs canal",
                   f"{salud.get('tn_sistema')} vs {salud.get('tn_canal')} "
                   f"({salud.get('delta_tn'):+})")
        if salud.get("cuadra_ml") is False:
            s.item("Mercado Libre: sistema vs canal",
                   f"{salud.get('ml_en_sistema')} vs {salud.get('ml_canal')} "
                   f"({salud.get('delta_ml'):+})")

    if n == 0:
        s.seccion(1, "No hay nada pendiente", "El panel no reporta problemas.")
    return s


def main() -> None:
    p = argparse.ArgumentParser(description="Arma la lista de pendientes del depósito.")
    p.add_argument("panel", nargs="?", default="index.html")
    p.add_argument("--clave-archivo", metavar="RUTA",
                   help="archivo con la contraseña, si el panel está cifrado")
    p.add_argument("--markdown", action="store_true")
    p.add_argument("--dias", type=int, default=10)
    p.add_argument("--salida", metavar="RUTA", help="escribir a un archivo en vez de la pantalla")
    args = p.parse_args()

    datos = cargar_datos(args.panel, args.clave_archivo)
    informe = str(armar(datos, args.dias, args.markdown))

    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as fh:
            fh.write(informe)
        print(f"Escrito en {args.salida}")
    else:
        print(informe)


if __name__ == "__main__":
    main()
