#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpiar_datos.py — saca los nombres de clientes del dato del panel.

QUÉ ENCONTRÓ LA AUDITORÍA DEL 14/10/2026
----------------------------------------
El JSON del panel llevaba 454 nombres y apellidos de clientes reales (más un
email), en `logistica.lista` y `logistica.repetidos`, cada uno atado a su número
de pedido y su transporte. Mientras el panel estuvo en texto plano en un repo
público, eso fue dato personal publicado en internet.

⚠️  LEÉ ESTO ANTES DE USARLO
----------------------------
Cifrar el panel (cerrar_panel.py) ya protege estos nombres. Anonimizar ADEMÁS es
defensa en profundidad — protege incluso si el panel se vuelve a publicar en
claro por error.

PERO la hoja del transportista imprime esos nombres, y quien entrega los
paquetes los necesita para saber de quién es cada bulto. Si anonimizás, esa hoja
sale con iniciales.

Por eso esta limpieza es OPCIONAL y viene apagada. Tres caminos razonables:

  a) Cifrar y NO anonimizar  → la operación queda igual que hoy. (recomendado
     para arrancar: es el cambio que no toca el trabajo de nadie)
  b) Cifrar Y anonimizar     → máxima protección; hay que ver si la hoja del
     transportista sigue sirviendo con iniciales + número de pedido
  c) Anonimizar solo el panel y dejar los nombres en la hoja impresa, que se
     genera aparte y no se publica → lo mejor de los dos, pero hay que tocar el
     generador de la hoja

CÓMO SE USA
-----------
    python3 herramientas/limpiar_datos.py index.html --salida index_limpio.html
    python3 herramientas/limpiar_datos.py index.html --revisar   # no escribe nada

O desde cerrar_panel.py con --anonimizar.
"""

import argparse
import json
import re
import sys

# Los campos del JSON que llevan el nombre de una persona.
CAMPOS_PERSONA = ("cliente", "comprador", "nombre_cliente", "destinatario")

PATRON_SNAP = re.compile(
    r'(<script id="snap" type="application/json">)(.*?)(</script>)', re.S)
PATRON_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def iniciales(nombre: str) -> str:
    """'Maria Eugenia Quiroga' -> 'M. E. Q.'   ·   'juan@mail.com Perez' -> 'J. P.'

    Se queda con lo suficiente para distinguir dos pedidos en una lista corta,
    sin identificar a la persona."""
    limpio = PATRON_EMAIL.sub(lambda m: m.group(0).split("@")[0], nombre)
    partes = [p for p in re.split(r"[\s,]+", limpio.strip()) if p]
    letras = [p[0].upper() for p in partes if p[0].isalpha()]
    if not letras:
        return "—"
    return " ".join(f"{l}." for l in letras[:3])


def limpiar_valor(valor):
    if isinstance(valor, str) and valor.strip():
        return iniciales(valor)
    return valor


def recorrer(nodo, contador):
    """Camina el JSON y reemplaza todo campo de persona por sus iniciales."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave in CAMPOS_PERSONA and isinstance(valor, str) and valor.strip():
                nuevo = limpiar_valor(valor)
                if nuevo != valor:
                    nodo[clave] = nuevo
                    contador[0] += 1
            else:
                recorrer(valor, contador)
    elif isinstance(nodo, list):
        for valor in nodo:
            recorrer(valor, contador)


def contar(nodo, encontrados):
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave in CAMPOS_PERSONA and isinstance(valor, str) and valor.strip():
                encontrados.append(valor)
            else:
                contar(valor, encontrados)
    elif isinstance(nodo, list):
        for valor in nodo:
            contar(valor, encontrados)


def anonimizar_html(html: str):
    """Devuelve (html_limpio, cantidad_de_nombres_reemplazados)."""
    m = PATRON_SNAP.search(html)
    if not m:
        return html, 0
    datos = json.loads(m.group(2))
    contador = [0]
    recorrer(datos, contador)
    nuevo_json = json.dumps(datos, ensure_ascii=False, separators=(", ", ": "))
    return html[:m.start(2)] + nuevo_json + html[m.end(2):], contador[0]


def revisar_html(html: str):
    m = PATRON_SNAP.search(html)
    if not m:
        print("No encontré el bloque de datos (<script id=\"snap\">) en el archivo.")
        return
    datos = json.loads(m.group(2))
    encontrados = []
    contar(datos, encontrados)
    emails = set(PATRON_EMAIL.findall(m.group(2)))
    print(f"nombres de personas en el dato : {len(encontrados)}")
    print(f"emails en el dato              : {len(emails)}")
    if encontrados:
        print("\nejemplo de cómo quedarían:")
        for nombre in encontrados[:5]:
            print(f"  {nombre[:34]:36} ->  {iniciales(nombre)}")


def main() -> None:
    p = argparse.ArgumentParser(description="Reemplaza nombres de clientes por iniciales.")
    p.add_argument("entrada")
    p.add_argument("--salida", help="por defecto pisa la entrada")
    p.add_argument("--revisar", action="store_true", help="solo informa, no escribe")
    args = p.parse_args()

    with open(args.entrada, encoding="utf-8") as fh:
        html = fh.read()

    if args.revisar:
        revisar_html(html)
        return

    limpio, cambios = anonimizar_html(html)
    if not cambios:
        print("No había nombres que limpiar.")
        return
    destino = args.salida or args.entrada
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(limpio)
    print(f"{cambios} nombres reemplazados por iniciales en {destino}")


if __name__ == "__main__":
    main()
