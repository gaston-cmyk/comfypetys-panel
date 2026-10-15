/**
 * probar_cierre.js — comprueba que un panel cifrado quedó bien cerrado.
 *
 * Abre el archivo en un navegador de verdad (Chromium headless) y verifica
 * cuatro cosas, que son las que importan:
 *
 *   1. Con la contraseña MAL  -> no se abre nada y avisa.
 *   2. Con la contraseña BIEN -> el panel entero se dibuja, sin errores de JS.
 *   3. Sin contraseña         -> no hay un solo dato del negocio en la página.
 *   4. Al recargar            -> la sesión sigue abierta (no vuelve a preguntar).
 *
 * Uso:
 *   node herramientas/probar_cierre.js <archivo.html> <contraseña>
 *
 * Necesita playwright. Si no lo tenés:  npm i playwright
 */

const path = require('path');

const ARCHIVO = process.argv[2];
const CLAVE = process.argv[3];

if (!ARCHIVO || !CLAVE) {
  console.error('uso: node herramientas/probar_cierre.js <archivo.html> <contraseña>');
  process.exit(2);
}

// Palabras que SOLO aparecen si el dato del negocio quedó en claro.
const RASTROS = ['stock_cargado', 'faltantes_tn', 'bajo_minimo', 'compra_proveedor', 'id="snap"'];

let playwright;
try {
  playwright = require('playwright');
} catch (e) {
  try {
    playwright = require('/opt/node-tools/node_modules/playwright');
  } catch (e2) {
    console.error('Falta playwright. Instalalo con:  npm i playwright');
    process.exit(2);
  }
}

const url = 'file://' + path.resolve(ARCHIVO);
let fallos = 0;

function ok(etiqueta, bien, detalle) {
  console.log(`  ${bien ? '✅' : '❌'} ${etiqueta}${detalle ? ' — ' + detalle : ''}`);
  if (!bien) fallos++;
}

(async () => {
  const fs = require('fs');
  const crudo = fs.readFileSync(ARCHIVO, 'utf8');

  console.log('\n1) El archivo en bruto, sin abrirlo');
  const sucios = RASTROS.filter(r => crudo.includes(r));
  ok('no hay datos del negocio en el texto del archivo', sucios.length === 0,
     sucios.length ? 'aparecen: ' + sucios.join(', ') : `${(crudo.length / 1024).toFixed(0)} KB, todo cifrado`);
  ok('lleva salt, nonce e iteraciones', /const SALT="/.test(crudo) && /ITER=\d{6,}/.test(crudo));
  const iter = (crudo.match(/ITER=(\d+)/) || [])[1];
  ok('las iteraciones de PBKDF2 son suficientes (>= 210.000)', Number(iter) >= 210000, `ITER=${iter}`);
  ok('pide a los buscadores que no lo indexen', /noindex/.test(crudo));

  const navegador = await playwright.chromium.launch();

  // --- 2) contraseña incorrecta --------------------------------------------
  console.log('\n2) Con la contraseña equivocada');
  let ctx = await navegador.newContext();
  let p = await ctx.newPage();
  await p.goto(url, { waitUntil: 'load' });
  await p.fill('#p', CLAVE + '-mal');
  await p.click('#b');
  await p.waitForTimeout(2500);
  let est = await p.evaluate(() => ({
    err: (document.getElementById('e') || {}).textContent || '',
    sigueEnLaPuerta: !!document.getElementById('p'),
    tablas: document.querySelectorAll('table').length,
    largo: document.body.innerText.length
  }));
  ok('avisa que la contraseña está mal', /incorrecta/i.test(est.err), est.err.trim());
  ok('no deja pasar', est.sigueEnLaPuerta && est.tablas === 0);
  ok('no filtra nada de texto', est.largo < 300, `${est.largo} caracteres visibles`);
  await ctx.close();

  // --- 3) contraseña correcta ----------------------------------------------
  console.log('\n3) Con la contraseña correcta');
  ctx = await navegador.newContext();
  p = await ctx.newPage();
  const errores = [];
  p.on('pageerror', e => errores.push(e.message));
  p.on('console', m => { if (m.type() === 'error' && !/ERR_|net::/.test(m.text())) errores.push(m.text()); });
  await p.goto(url, { waitUntil: 'load' });
  await p.fill('#p', CLAVE);
  await p.click('#b');
  await p.waitForTimeout(4000);
  est = await p.evaluate(() => ({
    titulo: document.title,
    secciones: document.querySelectorAll('[role=tabpanel]').length,
    tablas: document.querySelectorAll('table').length,
    vacias: [...document.querySelectorAll('table')].filter(t => t.querySelectorAll('tr').length === 0).length,
    candadoViejo: !!document.getElementById('gate') ||
                  document.documentElement.getAttribute('data-locked') === '1',
    datos: (document.getElementById('snap') || {}).textContent ?
           (document.getElementById('snap').textContent.length) : 0
  }));
  ok('el panel se abre entero', est.secciones > 10 && est.tablas > 50,
     `${est.secciones} secciones, ${est.tablas} tablas`);
  ok('ninguna tabla quedó vacía', est.vacias === 0, est.vacias ? `${est.vacias} vacías` : '');
  ok('el candado viejo no vuelve a preguntar', !est.candadoViejo);
  ok('los datos quedaron disponibles adentro', est.datos > 100000, `${(est.datos / 1024).toFixed(0)} KB`);
  ok('sin errores de JavaScript', errores.length === 0, errores.slice(0, 2).join(' · '));

  // --- 4) recarga -----------------------------------------------------------
  console.log('\n4) Al recargar la página');
  await p.reload({ waitUntil: 'load' });
  await p.waitForTimeout(3500);
  const tras = await p.evaluate(() => ({
    tablas: document.querySelectorAll('table').length,
    puerta: !!document.getElementById('p')
  }));
  ok('sigue abierto sin volver a pedir la clave', tras.tablas > 50 && !tras.puerta,
     `${tras.tablas} tablas`);
  await ctx.close();
  await navegador.close();

  console.log(fallos === 0
    ? '\n🔒 TODO BIEN: el panel está cerrado y funciona.\n'
    : `\n⚠️  ${fallos} comprobación(es) fallaron.\n`);
  process.exit(fallos === 0 ? 0 : 1);
})().catch(e => { console.error('El test falló:', e.message); process.exit(2); });
