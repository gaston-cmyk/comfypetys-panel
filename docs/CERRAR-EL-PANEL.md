# Cómo cerrar el panel del depósito

Guía para que `index.html` salga cifrado, con el mismo esquema que ya usa
`atencion.html`: AES-256-GCM y clave derivada con PBKDF2-SHA256 × 250.000.
Sin la contraseña, el archivo no se puede leer aunque se tenga en la mano.

Todo lo que se nombra acá está en `herramientas/` y probado.

> Las notas de la auditoría del 14/10/2026 y los pendientes de infraestructura se
> llevan aparte, fuera de este repositorio.

---

## Dónde va el cambio: en el build, no acá

**El generador reescribe `index.html` entero en cada cierre.** Se ve en la historia:
el código del panel pasó de 3.150 a 3.637 líneas a lo largo de los 4.911 cierres,
siempre llegando ya armado desde la máquina que lo genera.

Entonces un cambio hecho directamente en el repo se pierde en el próximo cierre, unos
diez minutos después. Peor: el push automático se encontraría con un commit ajeno y
podría trabarse, que es justo lo que dejó el panel congelado 14,8 horas el 2/10.

Este repo aporta la herramienta. El enganche va en la máquina que arma el panel.

---

## Paso 1 — La contraseña, fuera del código

En la máquina que genera el panel:

```bash
mkdir -p ~/.comfypetys
printf '%s' 'LA-CONTRASEÑA-QUE-ELIJAS' > ~/.comfypetys/clave_panel
chmod 600 ~/.comfypetys/clave_panel
```

Que sea una contraseña nueva. Y que no vaya en el comando ni en el código: queda en el
historial del shell y en la lista de procesos.

## Paso 2 — Enganchar la herramienta al final del build

Donde el build termina de escribir `index.html`, antes del `git add`:

```bash
python3 herramientas/cerrar_panel.py index.html \
        --clave-archivo ~/.comfypetys/clave_panel
```

Desde Python, si el build es `stock.py`:

```python
import subprocess
from pathlib import Path

subprocess.run([
    "python3", "herramientas/cerrar_panel.py", str(ruta_index),
    "--clave-archivo", str(Path.home() / ".comfypetys/clave_panel"),
], check=True)
```

La herramienta:
- comprime el panel y lo cifra;
- le pone adelante la pantalla de contraseña, la misma de `atencion.html`;
- le avisa al panel de adentro que la sesión ya está abierta, para que no pregunte dos
  veces;
- **no hace nada si el archivo ya está cifrado**, así que correrla de más no rompe.

Necesita `pip install cryptography`, que la máquina ya tiene: es lo que usa para
cifrar `atencion.html`.

## Paso 3 — Probar antes de publicar

```bash
node herramientas/probar_cierre.js index.html 'LA-CONTRASEÑA'
```

Abre el archivo en un Chromium de verdad y comprueba 13 cosas: que no quede nada
legible en el texto del archivo, que la contraseña equivocada no deje pasar, que la
correcta abra el panel entero sin errores de JavaScript, y que al recargar no vuelva a
preguntar. Termina con error si algo falla, así que se puede enganchar al build para
que nunca publique un panel roto.

Sobre el panel del 14/10, las 13 pasan.

## Paso 4 — Lo que cambia para quien lo usa

Ahora hay una pantalla de contraseña antes de que cargue nada, igual que en el panel
de atención.

**Sobre el backup dentro de Claude:** el panel trae `if(window.claude)` para abrirse
sin clave cuando lo mirás como artifact. Con el cifrado, ese atajo queda adentro y la
pantalla de afuera siempre pregunta. Si querés conservarlo, publicá la versión en
claro solo a Claude —que es privado— y la cifrada al resto.

---

## El archivo pesa seis veces menos, pero el repositorio crece más rápido

El panel pasa de **1.464 KB a 233 KB**, porque el gzip comprime muy bien el bloque de
datos. Suena a que el repositorio va a crecer menos. **Es al revés**, y conviene
saberlo antes de decidir.

Hoy, entre un cierre y el siguiente, lo único que cambia de `index.html` es la línea de
datos. Git guarda esa diferencia y no el archivo entero: **unos 30 KB por cierre**.
Un archivo cifrado, en cambio, cambia entero cada vez —el nonce es distinto en cada
cifrado, como tiene que ser— así que no hay diferencia que guardar: **unos 191 KB por
cierre**.

Medido sobre doce cierres reales del panel:

| | por cierre | a 137 cierres/día |
|---|---|---|
| en claro | 30 KB | ~4 MB/día |
| cifrado | 191 KB | ~26 MB/día |

Es el mismo precio que ya paga `atencion.html`, que está cifrado desde siempre y aporta
unos 30 MB por día él solo.

**Qué hacer con esto.** El cifrado igual vale la pena: 22 MB más por día es barato al
lado de tener los datos abiertos en internet. Pero deja claro que publicar el panel por
git es una solución de transición. Lo que de verdad resuelve las dos cosas a la vez
—la exposición y el peso— es **servir el panel desde el VPS**, que ya existe y ya pide
contraseña, y dejar git para los backups y el código.

Si el cifrado va a convivir un tiempo con el repo público, lo que más alivia es sacar
los backups de git: son unos 29 MB por día, y los que se borran siguen ocupando lugar
en la historia para siempre.

---

## Si además querés anonimizar

```bash
python3 herramientas/limpiar_datos.py index.html --revisar   # primero mirá qué hay
python3 herramientas/cerrar_panel.py index.html --anonimizar --clave-archivo ...
```

Reemplaza los nombres de clientes por iniciales (`Maria Eugenia Quiroga` → `M. E. Q.`).

⚠️ **Antes de prenderlo:** la hoja del transportista imprime esos nombres y quien
entrega los paquetes los necesita. Con el panel cifrado ya están protegidos; esto es
defensa extra por si el panel alguna vez vuelve a salir sin cifrar. Si lo prendés,
fijate primero si la hoja sigue sirviendo con iniciales más el número de pedido.

---

## Los dos automatismos nuevos

**`vigia.yml`** mira cada 30 minutos hace cuánto no se actualiza `index.html` y manda
un mail si pasó demasiado: a los 45 minutos, a las 6 horas y a las 24, más un
recordatorio diario a las 9 si sigue caído. Existe por el 2 de octubre, cuando el panel
quedó congelado 14,8 horas mostrando datos viejos con cara de buenos y no había nada
que avisara.

**`candado.yml`** avisa si el panel vuelve a publicarse sin cifrar. Existe por el 8 de
septiembre, cuando el panel quedó abierto en internet y nadie se dio cuenta. Mientras
no exista el archivo `.candado-activo` solo mira y anota; cuando termines de enganchar
el cifrado, lo creás y a partir de ahí cualquier regresión te llega por mail:

```bash
touch .candado-activo
git add .candado-activo && git commit -m "Activar el candado" && git push
```

Los dos usan los secretos de mail que ya tenés, y **empiezan a funcionar recién cuando
están en `main`**.

---

## Después del cifrado: cómo seguir leyendo los datos

Una vez que el panel salga cifrado, las herramientas que necesitan los datos lo abren
solas si les pasás la clave:

```bash
python3 herramientas/pendientes.py index.html --clave-archivo ~/.comfypetys/clave_panel
```

`pendientes.py` arma la lista de lo que hay que arreglar en el depósito, ordenada por
urgencia: stock negativo, lo que se agota en pocos días, lo que falta y nadie pidió,
las alertas de integridad del panel, los chequeos atrasados y los pedidos viejos sin
etiqueta. Es la herramienta de todos los días.

## Los backups

```bash
python3 herramientas/verificar_backup.py backups/confipetis-2026-10-14.db.enc
```

Te pide la contraseña y prueba las combinaciones de `openssl enc` hasta dar con la que
se usó. Te dice cuál es y si la derivación de clave es fuerte o floja. Tarda un poco a
propósito: las vueltas altas son lentas, que es justamente el punto.
