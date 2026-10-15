# comfypetys-panel

Panel interno de ComfyPetys. El contenido lo genera y lo publica una máquina
aparte; este repositorio es el lugar donde se publica, no donde se arma.

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `index.html` | Panel del depósito: stock, pedidos, remitos, logística. Se re-publica cada ~10 minutos. |
| `atencion.html` | Panel de atención al cliente. Cifrado: pide contraseña y descifra en el navegador. |
| `backups/` | Copias de la base, cifradas, con rotación de 7 días. |

## Herramientas

| Herramienta | Para qué |
|---|---|
| `herramientas/cerrar_panel.py` | Cifra un panel con AES-256-GCM + PBKDF2 (250.000 iteraciones), igual que `atencion.html`. Se engancha al final del build. |
| `herramientas/limpiar_datos.py` | Reemplaza nombres de clientes por iniciales. Opcional — leé la advertencia adentro. |
| `herramientas/probar_cierre.js` | Abre un panel cifrado en un navegador real y comprueba que quedó bien cerrado y que funciona. |
| `herramientas/pendientes.py` | La lista de lo que hay que arreglar en el depósito, ordenada por urgencia, sacada del propio panel. Sabe abrir el panel cifrado. |
| `herramientas/verificar_backup.py` | Dice con qué fuerza está cifrado un backup: prueba las combinaciones de `openssl enc` y avisa si la clave se deriva de forma débil. |

Cómo se usan: **[docs/CERRAR-EL-PANEL.md](docs/CERRAR-EL-PANEL.md)**.

La de todos los días es `pendientes.py`:

```bash
python3 herramientas/pendientes.py index.html
```

## Automatismos

| Workflow | Qué hace |
|---|---|
| `.github/workflows/alerta.yml` | Manda un mail con asunto y cuerpo que le pasás al dispararlo. El registro de las corridas es público, así que el cuerpo no lleva montos. |
| `.github/workflows/vigia.yml` | Cada 30 minutos revisa hace cuánto no se actualiza el panel y avisa por mail si se congeló. |
| `.github/workflows/candado.yml` | Avisa si el panel vuelve a publicarse sin cifrar. Calla hasta que exista el archivo `.candado-activo`. |
