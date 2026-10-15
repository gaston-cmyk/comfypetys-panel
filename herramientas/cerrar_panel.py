#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cerrar_panel.py — deja el panel del depósito cerrado de verdad.

POR QUÉ EXISTE
--------------
Hasta el 14/10/2026 `index.html` salía con los datos en TEXTO PLANO y una
"contraseña" que era base64 del password en el mismo archivo. El repo es público
y GitHub Pages lo publica, así que cualquiera podía leer el stock, los pedidos,
los remitos y los 454 nombres de clientes sin escribir nada: alcanzaba con abrir
el código fuente de la página.

`atencion.html` ya lo hacía bien: el dato es un blob cifrado con AES-256-GCM y la
clave sale de PBKDF2 con 250.000 iteraciones. Sin la contraseña no hay nada que
leer, ni siquiera con el archivo en la mano. Esta herramienta aplica EXACTAMENTE
ese mismo esquema al panel del depósito.

CÓMO SE USA (se engancha al final del build, después de generar index.html)
---------------------------------------------------------------------------
    export CLAVE_PANEL='...'
    python3 herramientas/cerrar_panel.py index.html --clave-env CLAVE_PANEL

Eso reescribe index.html dejándolo cifrado. Para no pisar el original:

    python3 herramientas/cerrar_panel.py index.html \
        --salida index_cerrado.html --clave-env CLAVE_PANEL

Opciones útiles:
    --anonimizar     reemplaza los nombres de clientes por iniciales ANTES de
                     cifrar (leé la advertencia en limpiar_datos.py: la hoja del
                     transportista usa esos nombres)
    --iteraciones N  por defecto 250000, igual que atencion.html

QUÉ PASA CON EL CANDADO VIEJO
-----------------------------
El panel original trae adentro su propio candado (el de base64). Al cifrar, ese
candado queda DENTRO del blob, así que ya no lo ve nadie. Para que no pida la
contraseña dos veces, el envoltorio marca la sesión como abierta justo antes de
escribir el panel. El candado real pasa a ser el de afuera, el criptográfico.

REQUISITOS
----------
    pip install cryptography
"""

import argparse
import base64
import gzip
import os
import re
import secrets
import sys

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("Falta la librería 'cryptography'. Instalala con:  pip install cryptography")

import hashlib

ITERACIONES_POR_DEFECTO = 250_000
LARGO_SAL = 16      # bytes
LARGO_NONCE = 12    # bytes — AES-GCM estándar


# ----------------------------------------------------------------------------
# El envoltorio: la pantalla de contraseña + el descifrado en el navegador.
# Es el mismo esquema de atencion.html. Lo único que cambia es que acá, antes de
# escribir el panel, se marca la sesión como abierta para que el candado viejo
# que viaja adentro no vuelva a preguntar.
# ----------------------------------------------------------------------------
ENVOLTORIO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>__TITULO__</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:#141821;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
  .card{background:#fff;border-radius:16px;padding:36px 32px;width:320px;text-align:center;
    box-shadow:0 20px 60px rgba(0,0,0,.4)}
  .paw{font-size:34px}
  h2{margin:10px 0 2px;font-size:20px;color:#141821}
  h2 b{color:#12A5D9}
  .sub{color:#777;font-size:13px;margin-bottom:18px}
  input{width:100%;box-sizing:border-box;padding:12px 14px;font-size:16px;border:1px solid #ddd;
    border-radius:10px;margin-bottom:12px}
  button{width:100%;padding:12px;font-size:15px;font-weight:700;border:0;border-radius:10px;
    background:#12A5D9;color:#fff;cursor:pointer}
  button:disabled{opacity:.6}
  .err{color:#dc2626;font-size:13px;height:16px;margin-top:8px}
</style></head><body>
<div class="card">
  <div class="paw">\U0001f43e</div>
  <h2>Panel <b>ComfyPetys</b></h2>
  <div class="sub">__SUBTITULO__</div>
  <input id="p" type="password" placeholder="Contraseña" autocomplete="off" autofocus>
  <button id="b">Entrar</button>
  <div class="err" id="e"></div>
</div>
<script>
const SALT="__SALT__", NONCE="__NONCE__", ITER=__ITER__, DATA="__DATA__";
function b2a(s){const b=atob(s),u=new Uint8Array(b.length);
  for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u}
async function abrir(pass){
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b2a(SALT),iterations:ITER,hash:'SHA-256'},
    km,{name:'AES-GCM',length:256},false,['decrypt']);
  const claro=await crypto.subtle.decrypt({name:'AES-GCM',iv:b2a(NONCE)},key,b2a(DATA));
  const res=new Response(new Blob([claro]).stream().pipeThrough(new DecompressionStream('gzip')));
  const html=await res.text();
  /* El panel trae adentro su propio candado viejo. Ya pasaste el de verdad
     (este), así que se le avisa para que no pregunte de nuevo. */
  try{sessionStorage.setItem('cp_ok','1');
      sessionStorage.setItem('cp_panel','1');
      sessionStorage.setItem('cp_panel_p',pass);}catch(x){}
  document.open();document.write(html);document.close();
}
async function intentar(){
  const p=(document.getElementById('p').value||'').trim();
  const btn=document.getElementById('b'),err=document.getElementById('e');
  btn.disabled=true;err.textContent='Abriendo…';
  try{await abrir(p)}catch(x){
    btn.disabled=false;
    err.textContent=(typeof DecompressionStream==='undefined')?
      'Este navegador es muy viejo para el panel':'Contraseña incorrecta';
  }
}
document.getElementById('b').addEventListener('click',intentar);
document.getElementById('p').addEventListener('keydown',e=>{if(e.key==='Enter'||e.keyCode===13)intentar()});
document.getElementById('p').addEventListener('keyup',e=>{if(e.key==='Enter'||e.keyCode===13)intentar()});
if(sessionStorage.getItem('cp_panel')==='1'&&sessionStorage.getItem('cp_panel_p')){
  abrir(sessionStorage.getItem('cp_panel_p')).catch(()=>{});
}
</script>
</body></html>
"""


def leer_clave(args) -> str:
    """La clave nunca se pasa por la línea de comandos: queda en el historial
    del shell y en la lista de procesos."""
    if args.clave_env:
        clave = os.environ.get(args.clave_env, "")
        if not clave:
            sys.exit(f"La variable de entorno {args.clave_env} está vacía o no existe.")
        return clave
    if args.clave_archivo:
        with open(os.path.expanduser(args.clave_archivo), encoding="utf-8") as fh:
            clave = fh.read().strip()
        if not clave:
            sys.exit(f"El archivo {args.clave_archivo} está vacío.")
        return clave
    import getpass
    clave = getpass.getpass("Contraseña para el panel: ").strip()
    if not clave:
        sys.exit("Contraseña vacía.")
    return clave


def ya_esta_cifrado(html: str) -> bool:
    return 'const SALT="' in html and "DecompressionStream" in html and 'id="snap"' not in html


def titulo_de(html: str, por_defecto: str) -> str:
    m = re.search(r"<title>([^<]*)</title>", html, re.I)
    return m.group(1).strip() if m else por_defecto


def cifrar(html: str, clave: str, iteraciones: int, titulo: str, subtitulo: str) -> str:
    crudo = html.encode("utf-8")
    # mtime=0 para que dos builds del mismo dato den el mismo gzip (sirve para
    # comparar y para que git no vea cambios donde no los hay).
    comprimido = gzip.compress(crudo, compresslevel=9, mtime=0)

    sal = secrets.token_bytes(LARGO_SAL)
    nonce = secrets.token_bytes(LARGO_NONCE)
    llave = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones, dklen=32)
    # AESGCM.encrypt devuelve ciphertext || tag, que es justo lo que espera
    # crypto.subtle.decrypt en el navegador.
    cifrado = AESGCM(llave).encrypt(nonce, comprimido, None)

    b64 = lambda x: base64.b64encode(x).decode("ascii")
    salida = ENVOLTORIO
    for marca, valor in (
        ("__TITULO__", titulo),
        ("__SUBTITULO__", subtitulo),
        ("__SALT__", b64(sal)),
        ("__NONCE__", b64(nonce)),
        ("__ITER__", str(iteraciones)),
        ("__DATA__", b64(cifrado)),
    ):
        salida = salida.replace(marca, valor)
    return salida


def main() -> None:
    p = argparse.ArgumentParser(
        description="Cifra un panel de ComfyPetys con el mismo esquema que atencion.html.")
    p.add_argument("entrada", help="el HTML generado por el build (en texto plano)")
    p.add_argument("--salida", help="dónde escribir el cifrado (por defecto: pisa la entrada)")
    p.add_argument("--clave-env", metavar="VAR", help="nombre de la variable de entorno con la clave")
    p.add_argument("--clave-archivo", metavar="RUTA", help="archivo que contiene la clave")
    p.add_argument("--iteraciones", type=int, default=ITERACIONES_POR_DEFECTO)
    p.add_argument("--anonimizar", action="store_true",
                   help="reemplaza nombres de clientes por iniciales antes de cifrar")
    p.add_argument("--subtitulo", default="Depósito · stock y pedidos")
    p.add_argument("--forzar", action="store_true",
                   help="cifrar aunque la entrada ya parezca cifrada")
    args = p.parse_args()

    with open(args.entrada, encoding="utf-8") as fh:
        html = fh.read()

    if ya_esta_cifrado(html) and not args.forzar:
        print(f"[cerrar_panel] {args.entrada} ya está cifrado — no hago nada. (--forzar para igual cifrarlo)")
        return

    tamano_antes = len(html.encode("utf-8"))

    if args.anonimizar:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from limpiar_datos import anonimizar_html
        html, cambios = anonimizar_html(html)
        print(f"[cerrar_panel] anonimizados {cambios} nombres de clientes")

    titulo = titulo_de(html, "Panel ComfyPetys")
    clave = leer_clave(args)
    cifrado = cifrar(html, clave, args.iteraciones, titulo, args.subtitulo)

    destino = args.salida or args.entrada
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(cifrado)

    tamano_despues = len(cifrado.encode("utf-8"))
    print(f"[cerrar_panel] {destino} cerrado con AES-256-GCM "
          f"(PBKDF2-SHA256 × {args.iteraciones:,} iteraciones)".replace(",", "."))
    print(f"[cerrar_panel] {tamano_antes/1024:,.0f} KB en claro → "
          f"{tamano_despues/1024:,.0f} KB cifrados".replace(",", "."))


if __name__ == "__main__":
    main()
