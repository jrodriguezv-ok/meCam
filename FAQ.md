# Preguntas frecuentes de MeCam

Guía para la versión 5 de MeCam o superior. Si algo de esta guía no coincide con lo que ves, avisa: el proyecto está en desarrollo.

**Índice**
- [Ver las cámaras](#ver-las-cámaras)
- [El visor (centro de control)](#el-visor-centro-de-control)
- [Instalación y uso](#instalación-y-uso)
- [Calor, batería y segundo plano](#calor-batería-y-segundo-plano)
- [Detección](#detección)
- [Privacidad y seguridad](#privacidad-y-seguridad)
- [Problemas frecuentes](#problemas-frecuentes)

---

## Ver las cámaras

### ¿Cómo veo mis cámaras desde fuera de mi Wi-Fi?

**Respuesta corta:** usa una VPN privada como **Tailscale**. No abras puertos en tu router.

MeCam funciona dentro de tu red: los celulares mandan el video a una computadora, y esa computadora muestra la página `/ver`. Para verla desde la calle hace falta un "túnel" seguro hasta esa computadora. Tailscale lo crea sin tocar el router.

> Este método todavía **no fue probado** con MeCam, pero no requiere cambios en el programa.

1. En la computadora donde corre `servidor.py`, entra a `tailscale.com/download`, descarga el instalador, instálalo y crea una cuenta (o inicia sesión).
2. En el celular con el que quieres mirar, abre **Play Store**, busca **Tailscale**, instálalo e inicia sesión con la **misma cuenta**.
3. En la computadora, haz clic en el ícono de Tailscale (cerca del reloj, abajo a la derecha) y copia la dirección de la computadora. Empieza por `100.` (por ejemplo `100.101.102.103`).
4. Cuando estés fuera de casa, abre **Tailscale** en el celular y enciende la conexión. Luego abre **Chrome** y escribe `https://100.101.102.103:8443/ver` (con tu dirección).
5. Saldrá el aviso "Tu conexión no es privada". Toca **Configuración avanzada** y luego **Acceder a ... (sitio no seguro)**. Es normal, porque MeCam usa un certificado propio.

Requisitos: la computadora debe estar **encendida**, con internet y con `servidor.py` ejecutándose. Los celulares cámara siguen en el Wi-Fi de casa.

Tailscale tiene un plan gratuito para uso personal. Las condiciones pueden cambiar, así que revísalas en su sitio web.

### ¿Puedo abrir un puerto en el router y entrar con mi IP pública?

**No lo recomendamos.** Hoy MeCam **no tiene usuario ni contraseña**: cualquiera que llegue a la dirección puede ver tus cámaras. Abrir un puerto lo dejaría expuesto a todo internet. Usa una VPN (ver pregunta anterior).

### ¿Puedo ver las cámaras desde otro celular estando en casa?

Sí. Conecta ese celular al mismo Wi-Fi, abre Chrome y entra a `https://IP-DE-LA-COMPUTADORA:8443/ver`. La IP aparece en la ventana negra del servidor, en la línea "En la COMPUTADORA abre".

### ¿Los celulares cámara pueden transmitir desde otra red o con datos móviles?

En teoría sí, si el celular cámara y la computadora tienen Tailscale: en el campo "IP de la computadora" de la app se escribe la dirección `100.x.x.x` de la computadora. **No está probado.** Ten en cuenta que gasta muchos datos (ver "¿Cuánto consume?").

---

## El visor (centro de control)

Es la página `https://IP-DE-LA-COMPUTADORA:8443/ver`. Funciona en la computadora y en el celular.

### ¿Cómo uso el visor?

- **Cuadrícula automática:** muestra todas las cámaras conectadas y se acomoda sola según cuántas haya. Arriba puedes fijarla en 1, 2 o 3 columnas.
- **Ampliar una cámara:** haz clic (o toca) sobre ella. Abajo verás miniaturas para pasar a otra, y también puedes usar las flechas del teclado (← →). **Esc** cierra la vista ampliada.
- **Zoom:** en la vista ampliada usa la rueda del mouse o los botones **+** y **−**. En el celular, pellizca con dos dedos. Con el zoom aplicado, arrastra para moverte. Doble clic acerca o restablece.
- **Capturar foto:** el botón de la cámara fotográfica guarda la imagen actual en la carpeta de descargas de tu navegador. MeCam no guarda nada en el servidor.
- **Sin recuadros:** muestra el video original, sin los recuadros de la detección.
- **Alerta sonora:** suena un aviso cuando aparece una persona. Los navegadores solo dejan activar el sonido tras un toque, por eso es un botón.
- **Actividad:** panel con el historial (cámaras que se conectan o se desconectan, personas y autos detectados).
- **Pantalla completa:** para dejarlo como un panel de vigilancia.

Cuando aparece una persona, la ficha de esa cámara se ilumina en rojo. Tus preferencias (columnas, sin recuadros, sonido) se guardan en ese navegador.

### ¿Qué pasa si dos celulares usan el mismo nombre?

Ya no se pisan. Si el nombre está en uso por otro celular, MeCam le agrega un número al segundo (por ejemplo `celular1-2`). La app muestra el nombre que recibió en su notificación, y el visor lo indica. Si es el **mismo celular** que se reconecta, conserva su nombre.

### ¿Qué pasa cuando un celular se apaga o pierde el Wi-Fi?

El servidor lo detecta en unos 20 segundos y lo desconecta: su ficha desaparece del visor y queda anotado en **Actividad**. Cuando el celular vuelve, la app se reconecta sola y la ficha reaparece. Si una cámara sigue conectada pero no manda imágenes (por ejemplo, en pausa por calor), la ficha se muestra en gris con la etiqueta **SIN SEÑAL**.

---

## Instalación y uso

### ¿Qué necesito para usar MeCam?

- Una **computadora con Windows** que quede encendida (hace la detección).
- Uno o más **celulares Android** (Android 7.0 o superior) con cámara.
- Que la computadora y los celulares estén en el **mismo Wi-Fi**.

### ¿Cómo instalo la app en el celular?

1. En el celular, abre **Chrome** y entra a la sección **Releases** de este repositorio.
2. Toca **MeCam.apk**. Si Chrome avisa que el archivo puede dañar el dispositivo, toca **Descargar de todos modos**.
3. Toca **Abrir** y luego **Instalar**. Si el celular pide permiso para instalar apps de origen desconocido, toca **Ajustes**, activa **Permitir de esta fuente**, vuelve atrás y toca **Instalar**.
4. Si Play Protect avisa, toca **Más detalles** y luego **Instalar de todos modos**.
5. Abre **MeCam**, escribe la IP de la computadora, un nombre para la cámara y toca **Iniciar cámara**. Toca **Permitir** en los permisos.

### ¿Cómo instalo y ejecuto el servidor en la computadora?

1. Instala **Python** desde `python.org/downloads`. Marca la casilla **Add python.exe to PATH**.
2. Descarga la carpeta `servidor` de este repositorio.
3. Pulsa la tecla **Windows**, escribe `cmd` y pulsa **Enter**.
4. Entra a la carpeta con `cd` (por ejemplo `cd Desktop\MEcam`).
5. Escribe `python -m pip install -r requirements.txt` y pulsa **Enter**. Tarda unos minutos.
6. Abre el puerto en el firewall: abre `cmd` **como administrador** y ejecuta estas dos líneas:
   ```
   netsh advfirewall firewall add rule name="MeCam" dir=in action=allow protocol=TCP localport=8443
   netsh advfirewall firewall add rule name="MeCam8080" dir=in action=allow protocol=TCP localport=8080
   ```
7. Escribe `python servidor.py` y pulsa **Enter**. Deja esa ventana abierta.
8. Abre `https://localhost:8443/ver` en Chrome para ver las cámaras.

La primera vez descarga el modelo de detección, así que tarda un poco más.

### ¿Cómo se actualiza la app?

MeCam consulta si hay una versión nueva cuando la abres y cada 6 horas mientras transmite. Si la hay, aparece la notificación **"MeCam: hay una versión nueva"**. Al tocarla se abre la app con un botón **Actualizar MeCam a la versión N**. Tócalo y luego toca **Instalar** cuando Android lo pida.

Android **no permite** instalar sin que la persona lo autorice, así que siempre hace falta al menos un toque. Después de actualizar, abre MeCam una vez: la cámara se reanuda sola si estaba encendida.

Si tu versión es anterior a la 5, desinstala la app y vuelve a instalarla una vez.

### ¿Puedo conectar varios celulares?

Sí. Cada celular necesita un **nombre distinto** en el campo "Nombre de esta cámara" (`celular1`, `celular2`, …). Si dos usan el mismo nombre, MeCam le agrega un número al segundo (por ejemplo `celular1-2`) para que no se pisen; aun así, conviene ponerles nombres distintos para reconocerlos.

Cada cámara hace trabajar más a la computadora. Si ves retraso, baja los **cuadros por segundo** de cada celular (5 o 6 suele bastar) o usa menos cámaras.

### ¿Funciona con iPhone?

La app es solo para **Android**. Existe una página web para el navegador (`https://IP-DE-LA-COMPUTADORA:8443`), pero funciona solo con la pantalla encendida y no fue probada en iPhone.

### ¿Necesito internet?

Para transmitir y detectar, **no**: todo ocurre dentro de tu red. Internet solo se usa para descargar el modelo la primera vez, para las actualizaciones y para ver las cámaras desde fuera.

### ¿Cuánto consume la red?

Es una **estimación**, no una medición: con la configuración por defecto (10 cuadros por segundo) cada cámara usa del orden de **1 GB por hora**. Dentro de tu Wi-Fi no importa; con datos móviles sí.

### ¿Puedo cambiar la calidad o la velocidad?

La velocidad se cambia en la app, en **Cuadros por segundo** (de 1 a 25). Más cuadros dan un video más fluido, pero calientan más el celular y cargan más la computadora.

### ¿Se puede ver la cámara en horizontal?

Sí. En la app, el selector **Orientación** viene en **automática**: usa el sensor de movimiento para saber si el celular está vertical u horizontal. Si el celular está acostado sobre una mesa, el sensor no puede saberlo y conviene elegir la orientación a mano.

---

## Calor, batería y segundo plano

### ¿La cámara sigue funcionando con la pantalla apagada?

Sí. La app usa un servicio en primer plano y deja una notificación fija. Algunas marcas (Xiaomi, Huawei, Oppo, Samsung, entre otras) cierran las apps en segundo plano para ahorrar batería. Para evitarlo, en MeCam toca **Ajustes de batería**, busca **MeCam** y pon **Sin restricciones** (o **No optimizar**). El sitio `dontkillmyapp.com` explica cada marca.

### ¿Cómo evito que el celular se caliente?

- Quítale la **funda** y ponlo en un lugar **ventilado**, lejos del sol directo.
- Bájale los **cuadros por segundo** (6 a 8 suele ser suficiente).
- Déjalo **enchufado**, pero mira la pregunta siguiente.

MeCam también se protege solo: a **40 °C** baja a 4 cuadros por segundo; a **42 °C** pausa la cámara, y vuelve a la velocidad normal por debajo de **38 °C**.

### ¿Es seguro dejar un celular viejo enchufado todo el día?

Con una batería en buen estado, normalmente sí. Pero si la batería está **hinchada** (la pantalla se despega o el celular se ve abombado), **no lo dejes enchufado** ni funcionando: es un riesgo real de incendio. Cambia la batería o no lo uses como cámara.

---

## Detección

### ¿Qué detecta MeCam?

Por ahora **personas y autos**, con el modelo YOLO. Cada objeto recibe un número y se sigue entre cuadros.

### ¿Puedo detectar otras cosas (motos, bicicletas, perros)?

Sí. En `servidor.py` busca la línea `CLASES = [0, 2]` y agrega los números que quieras: `1` bicicleta, `3` moto, `5` bus, `7` camión, `15` gato, `16` perro. Guarda el archivo y vuelve a ejecutar el servidor.

### ¿MeCam graba video, manda alertas o graba audio?

**Todavía no.** Está en la lista de mejoras: audio, alertas por Telegram, grabación de clips y zonas de alerta.

---

## Privacidad y seguridad

### ¿Mi video va a la nube?

No. El video viaja de tu celular a **tu computadora**, dentro de tu red. MeCam no lo sube a ningún servidor de terceros.

### ¿Cualquiera puede ver mis cámaras?

Cualquier persona **dentro de tu Wi-Fi** que conozca la dirección `https://IP-DE-LA-COMPUTADORA:8443/ver` puede verlas: **MeCam todavía no pide usuario ni contraseña**. Por eso no abras puertos en el router y usa una VPN para verlas desde fuera. Una contraseña está en la lista de mejoras.

### ¿Por qué el navegador dice "Tu conexión no es privada"?

Porque el servidor crea su propio certificado en tu computadora, y los navegadores solo confían en certificados emitidos por entidades conocidas. En tu propia red es seguro continuar: toca **Configuración avanzada** y luego **Acceder a ... (sitio no seguro)**.

### ¿Es legal grabar con MeCam?

Esto no es asesoramiento legal. En general, grabar dentro de tu casa es distinto a grabar la calle, a los vecinos o a personas que trabajan en tu casa: en muchos países (por ejemplo, en la UE con el RGPD) hay reglas sobre cámaras que enfocan espacios públicos o a terceros, como avisar con un cartel. Infórmate sobre las normas de tu país antes de instalar cámaras, y usa MeCam solo en espacios propios.

---

## Problemas frecuentes

### El celular dice "timed out" o "no se puede acceder al sitio"

Casi siempre es el **firewall de Windows**. Abre `cmd` **como administrador** y ejecuta:

```
netsh advfirewall firewall add rule name="MeCam" dir=in action=allow protocol=TCP localport=8443
netsh advfirewall firewall add rule name="MeCam8080" dir=in action=allow protocol=TCP localport=8080
```

Comprueba también que el celular y la computadora estén en el **mismo Wi-Fi** y con los datos móviles apagados.

### El navegador dice "ERR_EMPTY_RESPONSE" o "la página no funciona"

Falta la **s** de `https://`. La dirección debe empezar por `https://` y terminar en `:8443`. En Chrome de Android a veces se borra al escribir.

### En la ventana negra sale `No module named 'cv2'`

Las librerías no quedaron instaladas. Ejecuta `python -m pip install -r requirements.txt` dentro de la carpeta `servidor` y vuelve a probar.

### En la ventana negra sale `Numpy is not available`

Se instaló una versión de NumPy incompatible con YOLO. Ejecuta `python -m pip install "numpy<2"` y vuelve a iniciar el servidor.

### La app dice "Reconectando..."

La app no logra hablar con el servidor. Revisa en orden:
1. `servidor.py` está corriendo (ventana negra abierta).
2. La **IP** escrita en la app es la de la línea "En la APP de Android" del servidor.
3. El firewall permite el puerto **8080** (ver "timed out").
4. El celular y la computadora están en el **mismo Wi-Fi**.

### La página `/ver` no muestra ninguna cámara

Ves el mensaje "Esperando cámaras…": ningún celular está conectado. Mira la ventana negra: debe aparecer `[+] Cámara conectada: celular1`. La primera conexión tarda unos segundos porque carga el modelo.

### La IP de la computadora cambió y ya no conecta

El router puede darle otra IP a la computadora cuando se reinicia. Para que no cambie, entra a la configuración de tu router y busca **Reserva DHCP**, **IP estática** o **Asignación de direcciones**. Asigna una IP fija a la computadora. Después escribe esa IP en la app.

### La imagen sale de lado o al revés

En MeCam cambia el selector **Orientación** a **vertical**, **horizontal (izquierda)** o **horizontal (derecha)**, y toca **Iniciar cámara** otra vez.

### La app dice que no pudo abrir la cámara

Otra app está usando la cámara. Ciérrala, cierra MeCam y vuelve a abrirla. Si sigue, reinicia el celular.

### La app no se instala o dice que hay un conflicto con la versión instalada

Desinstala la versión anterior de MeCam (mantén pulsado su ícono, **Desinstalar**) y vuelve a instalar. Esto solo hace falta con versiones anteriores a la 5.

### El celular deja de transmitir después de un rato

Casi seguro el sistema cerró la app para ahorrar batería. Repite el paso de **Ajustes de batería** de la sección "Calor, batería y segundo plano". Si la notificación de MeCam dice "En pausa por calor", el celular se está enfriando: espera o baja los cuadros por segundo.

---

¿Tienes una pregunta que no está aquí? Abre un **Issue** en este repositorio.
