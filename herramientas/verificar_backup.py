#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_backup.py — ¿con qué fuerza están cifrados los backups?

POR QUÉ
-------
Los backups de `backups/` empiezan con `Salted__`, que es el formato de
`openssl enc`. Ese formato admite dos maneras muy distintas de derivar la clave
a partir de la contraseña:

  • `-pbkdf2 -iter N`  → N vueltas. Con N grande, probar contraseñas es carísimo.
  • sin `-pbkdf2`      → el modo viejo: MD5 y UNA sola vuelta. Probar millones de
                         contraseñas por segundo es barato en una placa de video.

Desde afuera los dos archivos se ven idénticos: no hay forma de saber cuál es
mirando el archivo. Hay que probar a descifrar. Eso hace esta herramienta.

Importa porque mientras el repositorio sea público, esos archivos los puede bajar
cualquiera y probar contraseñas con todo el tiempo del mundo.

CÓMO SE USA
-----------
    python3 herramientas/verificar_backup.py backups/confipetis-2026-10-14.db.enc

Te pide la contraseña (no la escribas en el comando: queda en el historial),
prueba las combinaciones más habituales y te dice cuál es la tuya y qué tan
fuerte es.

No modifica nada. Descifra a un archivo temporal que borra al terminar.
"""

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import tempfile

# Una base SQLite siempre arranca con estos 16 bytes.
FIRMA_SQLITE = b"SQLite format 3\x00"

# Las combinaciones que vale la pena probar, de la más fuerte a la más débil.
# (etiqueta, argumentos extra, veredicto)
COMBINACIONES = [
    ("AES-256-CBC con PBKDF2 y 600.000 vueltas",
     ["-aes-256-cbc", "-pbkdf2", "-iter", "600000"], "fuerte"),
    ("AES-256-CBC con PBKDF2 y 310.000 vueltas",
     ["-aes-256-cbc", "-pbkdf2", "-iter", "310000"], "fuerte"),
    ("AES-256-CBC con PBKDF2 y 100.000 vueltas",
     ["-aes-256-cbc", "-pbkdf2", "-iter", "100000"], "aceptable"),
    ("AES-256-CBC con PBKDF2 por defecto (10.000 vueltas)",
     ["-aes-256-cbc", "-pbkdf2"], "flojo"),
    ("AES-256-CBC sin PBKDF2 (MD5, UNA vuelta)",
     ["-aes-256-cbc"], "DÉBIL"),
    ("AES-128-CBC sin PBKDF2 (MD5, UNA vuelta)",
     ["-aes-128-cbc"], "DÉBIL"),
]

VEREDICTOS = {
    "fuerte": ("✅", "Bien. Aunque alguien baje el archivo, probar contraseñas le sale carísimo."),
    "aceptable": ("🟡", "Pasable, pero subilo a 600.000 vueltas en el próximo backup."),
    "flojo": ("🟠", "Las 10.000 vueltas por defecto de OpenSSL quedaron cortas hace rato.\n"
                    "   Regeneralo con: -pbkdf2 -iter 600000"),
    "DÉBIL": ("🔴", "La clave se deriva con MD5 y una sola vuelta. Con el archivo en la mano,\n"
                    "   probar millones de contraseñas por segundo es barato.\n"
                    "   Hay que recifrar TODOS los backups con: -pbkdf2 -iter 600000\n"
                    "   y, mientras tanto, sacarlos de cualquier lugar público."),
}


def hay_openssl() -> bool:
    return shutil.which("openssl") is not None


def probar(archivo: str, clave: str, extra: list) -> bool:
    """Descifra los primeros bytes y mira si salió una base SQLite."""
    destino = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    destino.close()
    try:
        proc = subprocess.run(
            ["openssl", "enc", "-d", *extra, "-in", archivo, "-out", destino.name,
             "-pass", "stdin"],
            input=clave.encode(), capture_output=True, timeout=600)
        if proc.returncode != 0:
            return False
        with open(destino.name, "rb") as fh:
            return fh.read(16) == FIRMA_SQLITE
    except subprocess.TimeoutExpired:
        return False
    finally:
        try:
            os.unlink(destino.name)
        except OSError:
            pass


def main() -> None:
    p = argparse.ArgumentParser(
        description="Dice con qué cifrado y qué derivación de clave se hizo un backup.")
    p.add_argument("archivo", help="un .db.enc de backups/")
    args = p.parse_args()

    if not hay_openssl():
        sys.exit("No encuentro el comando 'openssl'.")
    if not os.path.exists(args.archivo):
        sys.exit(f"No existe {args.archivo}")

    with open(args.archivo, "rb") as fh:
        cabecera = fh.read(8)
    if cabecera != b"Salted__":
        print(f"⚠️  {args.archivo} no arranca con 'Salted__': no lo hizo `openssl enc`.")
        print("   Si usás age, gpg o similar, esta herramienta no aplica (y probablemente estés mejor).")
        return

    tamano = os.path.getsize(args.archivo) / 1024 / 1024
    print(f"\nArchivo : {args.archivo}  ({tamano:.1f} MB)")
    print("Formato : openssl enc (empieza con 'Salted__')\n")

    clave = getpass.getpass("Contraseña del backup: ")
    if not clave:
        sys.exit("Contraseña vacía.")

    print("\nProbando combinaciones (puede tardar: las vueltas altas son lentas a propósito)…\n")
    for etiqueta, extra, nivel in COMBINACIONES:
        print(f"  … {etiqueta}", end="", flush=True)
        if probar(args.archivo, clave, extra):
            icono, consejo = VEREDICTOS[nivel]
            print("  ← ES ESTA\n")
            print(f"{icono}  {etiqueta}")
            print(f"   {consejo}\n")
            return
        print("  no")

    print("\n❓ Ninguna combinación funcionó.")
    print("   O la contraseña no es esa, o el backup usa otro cifrado.")
    print("   Mirá el comando que los genera en el script de backup.\n")


if __name__ == "__main__":
    main()
