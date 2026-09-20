# Preguntas frecuentes de MeCam

Guía para la versión 5 de MeCam o superior. Si algo de esta guía no coincide con lo que ves, avisa: el proyecto está en desarrollo.

**Índice**
- [Ver las cámaras](#ver-las-cámaras)
- [El visor (centro de control)](#el-visor-centro-de-control)
- [Vincular dispositivos (QR)](#vincular-dispositivos-qr)
- [Instalación y uso](#instalación-y-uso)
- [Calor, batería y segundo plano](#calor-batería-y-segundo-plano)
- [Detección](#detección)
- [Grabaciones](#grabaciones)
- [Privacidad y seguridad](#privacidad-y-seguridad)
- [Problemas frecuentes](#problemas-frecuentes)

---

## Ver las cámaras

### ¿Cómo veo mis cámaras desde fuera de mi Wi-Fi?

**Respuesta corta:** usa una VPN privada como **Tailscale**. No abras puertos en tu router.

MeCam funciona dentro de tu red: los celulares mandan el video a una computadora, y esa computadora muestra la página `/ver`. Para verla desde la calle hace falta un "túnel" seguro hasta esa computadora. Tailscale lo crea sin tocar el router.

> Este método todavía **no fue probado** con MeCam, pero no requiere cambios en el programa.

1. En la computadora donde corre MeCam, entra a `tailscale.com/download`, descarga el instalador, instálalo y crea una cuenta (o inicia sesión).
2. En el celular con el que quieres mirar, abre **Play Store**, busca **Tailscale**, instálalo e inicia sesión con la **misma cuenta**.
3. En la computadora, haz clic en el ícono de Tailscale (cerca del reloj, abajo a la derecha) y copia la dirección de la computadora. Empieza por `100.` (por ejemplo `100.101.102.103`).
4. Cuando estés fuera de casa, abre **Tailscale** en el celular y enciende la conexión. Luego abre **Chrome** y escribe `https://100.101.102.103:8443/ver` (con tu dirección).
5. Saldrá el aviso "Tu conexión no es privada". Toca **Configuración avanzada** y luego **Acceder a ... (sitio no seguro)**. Es normal, porque MeCam usa un certificado propio.

Requisitos: la computadora debe estar **encendida**, con internet y con el servidor en marcha. **No hace falta vincular** ese celular: MeCam confía en tu red Tailscale (mira «¿Hace falta vincular si veo las cámaras por Tailscale?»). Los celulares cámara siguen en el Wi-Fi de casa.

Tailscale tiene un plan gratuito para uso personal. Las condiciones pueden cambiar, así que revísalas en su sitio web.

### ¿Puedo abrir un puerto en el router y entrar con mi IP pública?

**No lo recomendamos.** Aunque MeCam solo deja entrar a dispositivos vinculados, abrir un puerto deja tu computadora expuesta a todo internet. Usa una VPN (ver pregunta anterior).

### ¿Puedo ver las cámaras desde otro celular estando en casa?

Sí. Si ya vinculaste algún dispositivo, primero vincula este (mira «¿Cómo vinculo otro aparato para ver las cámaras?»). Después, con el celular en el mismo Wi-Fi, abre Chrome y entra a `https://IP-DE-LA-COMPUTADORA:8443/ver`. La dirección aparece en la ventana de MeCam, en el recuadro **Centro de control**.

### ¿Los celulares cámara pueden transmitir desde otra red o con datos móviles?

En teoría sí, si el celular cámara y la computadora tienen Tailscale: en el campo "IP de la computadora" de la app se escribe la dirección `100.x.x.x` de la computadora. **No está probado.** Ten en cuenta que gasta muchos datos (ver "¿Cuánto consume?").

---

## El visor (centro de control)

Es la página `https://IP-DE-LA-COMPUTADORA:8443/ver`. Funciona en la computadora y en el celular.

### ¿Cómo uso el visor?

Los botones están en una **barra flotante**: a la derecha en la computadora y abajo en el celular. Pasa el mouse sobre un botón para ver su nombre y su tecla rápida.

| Botón | Qué hace | Tecla |
|---|---|---|
| Grabaciones | Abre la página con los clips guardados | **G** |
| Grabación de clips | Interruptor general: **rojo** = activada, **punteado** = desactivada | **Q** |
| Vincular dispositivo | Muestra el QR para conectar un celular (solo se ve en la propia computadora) | **V** |
| Actividad | Historial con un ícono por tipo de aviso. Un **punto rojo** te avisa si hay algo nuevo | **A** |
| Alerta sonora | Suena un aviso cuando aparece una persona (la campana se ve tachada cuando está apagada) | **S** |
| Sin recuadros | Muestra el video original, sin los recuadros de detección | **R** |
| Distribución | Cambia entre automática, 1, 2 y 3 columnas. La letra o el número en la esquina del botón indica cuál está activa | **L** |
| Pantalla completa | Para dejarlo como un panel de vigilancia | **F** |

**Indicador REC en cada cámara:** junto al nombre de cada cámara aparece un indicador que también es su selector. Tócalo para elegir si esa cámara graba.

- **REC rojo y palpitante:** está grabando un clip ahora mismo.
- **REC con borde:** está lista y grabará cuando detecte una persona.
- **REC tachado:** esa cámara no graba (la elegiste tú).
- Si la grabación general está desactivada, los indicadores se ocultan.

**Ampliar una cámara:** haz clic (o toca) sobre ella. Aparecen flechas grandes a los lados para pasar a la anterior o la siguiente (también con **←** y **→**) y miniaturas abajo. **Esc** cierra la vista ampliada.

**Zoom y foto:** en la vista ampliada, la barra flotante de abajo tiene **alejar**, **acercar**, **zoom normal** (**0**), **capturar foto** (**C**) y **pantalla completa** (**F**). También puedes usar la rueda del mouse; en el celular, pellizca con dos dedos. Con el zoom aplicado, arrastra para moverte; doble clic acerca o restablece. La foto se guarda en la carpeta de descargas de tu navegador: MeCam no guarda nada en el servidor.

Cuando aparece una persona, la ficha de esa cámara se ilumina en rojo. Tus preferencias (columnas, sin recuadros, sonido) se guardan en ese navegador. Los íconos son de [Phosphor Icons](https://phosphoricons.com) y vienen incluidos en el programa, así que el visor funciona sin internet.

### ¿Qué pasa si dos celulares usan el mismo nombre?

Ya no se pisan. Con los celulares **vinculados por QR** el problema no existe: el servidor le da a cada uno su propio nombre («Cámara 1», «Cámara 2»…) y puedes cambiarlo con **Renombrar** en la ventana de MeCam. Solo con la conexión manual puede repetirse: entonces MeCam le agrega un número al segundo (por ejemplo `celular1-2`). Si es el **mismo celular** que se reconecta, conserva su nombre.

### ¿Qué pasa cuando un celular se apaga o pierde el Wi-Fi?

El servidor lo detecta en unos 20 segundos y lo desconecta: su ficha desaparece del visor y queda anotado en **Actividad**. Cuando el celular vuelve, la app se reconecta sola y la ficha reaparece. Si una cámara sigue conectada pero no manda imágenes (por ejemplo, en pausa por calor), la ficha se muestra en gris con la etiqueta **SIN SEÑAL**.

---

## Vincular dispositivos (QR)

### ¿Qué es vincular y por qué hace falta?

Vincular es "presentar" un celular a tu computadora. En la ventana de MeCam haces clic en **Vincular dispositivo**, aparece un QR, lo escaneas y listo: no hay que escribir IP ni contraseñas. Desde que vinculas el primero, el servidor solo acepta dispositivos vinculados, así nadie más de tu Wi-Fi puede conectar una cámara ni ver el centro de control.

### ¿Cómo vinculo un celular cámara?

1. En la computadora, abre el centro de control (`https://localhost:8443/ver`, o el botón **Centro de control** de la ventana de MeCam). Mientras no haya cámaras, **el QR aparece solo** en la pantalla de bienvenida. Si ya hay cámaras conectadas, haz clic en el botón **Vincular dispositivo** de arriba (o pulsa **V**). También puedes usar el botón **Vincular dispositivo** de la ventana de MeCam.
2. En el celular abre **MeCam** y toca **Escanear QR para vincular**. Toca **Permitir** si pide permiso de cámara.
3. Apunta la cámara del celular al QR. Cuando aparezca «¡Listo! Vinculada como «Cámara 1»», toca **Iniciar cámara**.

El nombre lo asigna el servidor («Cámara 1», «Cámara 2»…). Puedes cambiarlo con **Renombrar** en la ventana de MeCam.

### ¿Cómo vinculo otro aparato para ver las cámaras?

1. En la computadora haz clic en **Vincular dispositivo** (en el centro de control o en la ventana de MeCam).
2. Con la **cámara normal** del celular (o de la tablet) escanea el QR y abre el enlace que aparece.
3. Saldrá el aviso «Tu conexión no es privada»: toca **Configuración avanzada** y luego **Acceder a ... (sitio no seguro)**. Se abre el centro de control, ya vinculado. La próxima vez basta con entrar a la dirección de siempre.

El aparato debe estar en el mismo Wi-Fi que la computadora al vincularlo.

### ¿Por qué no veo el QR o el botón «Vincular dispositivo»?

Por seguridad, el QR **solo se muestra en la computadora donde corre MeCam**. Si abres el centro de control desde otro aparato (otro celular, otra computadora, o por Tailscale), no aparece el QR ni el botón, y en su lugar verás los pasos para vincular. Abre `https://localhost:8443/ver` en la computadora de MeCam. Si aun así no aparece, comprueba que el servidor esté iniciado y que hayas actualizado MeCam en la computadora (puede faltar el componente del QR: mira «La ventana de MeCam no se abre»).

### ¿Cada QR es distinto? ¿Se puede reutilizar?

Cada QR es distinto y **sirve una sola vez**; además vence a los 5 minutos. Cuando se usa, la ventana muestra uno nuevo para el siguiente dispositivo. Una foto de un QR ya usado no sirve para nada.

### ¿Qué pasa cuando vinculo el primer dispositivo?

MeCam pasa de **Abierto** a **Protegido**: solo entran los dispositivos vinculados. **Vincula todas tus cámaras y visores**, porque los que no estén vinculados dejarán de conectar. La ventana de MeCam te avisa qué cámaras conectadas siguen sin vincular.

### ¿Cómo desvinculo un dispositivo (por ejemplo, si pierdo un celular)?

En la ventana de MeCam elige el dispositivo en la lista y haz clic en **Desvincular**. Se corta al instante y no puede volver a conectarse sin un QR nuevo.

### ¿Hace falta vincular si veo las cámaras por Tailscale?

No. Si Tailscale está instalado y conectado en la computadora, MeCam deja entrar a los aparatos de tu red Tailscale sin vincularlos, porque Tailscale ya los autentica. Eso incluye a quien tú hayas invitado a tu red. Tampoco hace falta vincular cuando abres el centro de control en la propia computadora.

MeCam detecta Tailscale al iniciar y cada minuto, usando el programa `tailscale` de la computadora. Si por Tailscale ves «Este dispositivo no está vinculado», MeCam no lo detectó: reinicia MeCam y, si sigue igual, abre un **Issue** en este repositorio.

### ¿La conexión de las cámaras está cifrada?

Sí. Las cámaras vinculadas se conectan por HTTPS y solo confían en el certificado de tu computadora, cuya huella viaja dentro del QR. Así nadie más en tu Wi-Fi puede hacerse pasar por tu computadora.

### ¿Dónde se guardan los dispositivos vinculados?

En la carpeta `MeCam` dentro de `%APPDATA%` (escribe `%APPDATA%` en la barra de direcciones del Explorador de archivos y pulsa **Enter**). Ahí están la lista y el certificado, y se conservan al actualizar MeCam. **Si borras esa carpeta, hay que vincular todo de nuevo.**

### ¿Puedo seguir usando la IP manual?

Sí, en la app: **Ajustes** y luego **Conexión manual**. Solo funciona mientras MeCam está **Abierto** (sin dispositivos vinculados).

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
5. Abre **MeCam** y toca **Escanear QR para vincular** (el QR aparece en la ventana de MeCam de la computadora: mira «¿Cómo vinculo un celular cámara?»). Después toca **Iniciar cámara** y **Permitir** en los permisos.

### ¿Cómo instalo y ejecuto el servidor en la computadora?

1. Instala **Python** desde `python.org/downloads`. Marca la casilla **Add python.exe to PATH**.
2. Descarga el proyecto: en la página del repositorio haz clic en **Code** y luego en **Download ZIP**. Haz clic derecho sobre el archivo descargado, luego **Extraer todo…** y **Extraer**.
3. Abre la carpeta extraída y entra a la carpeta **servidor**.
4. Haz doble clic en **Iniciar MeCam.bat**. Si Windows avisa "Windows protegió su PC", haz clic en **Más información** y luego en **Ejecutar de todos modos**.
5. La primera vez se instala lo necesario en una ventana negra. Tarda varios minutos y no hay que cerrarla. Al terminar se abre la ventana de MeCam.
6. En la ventana de MeCam haz clic en el botón verde **Iniciar servidor**. La primera vez descarga el modelo de detección y tarda un poco más.
7. Haz clic en **Abrir puertos del firewall (una sola vez)** y, cuando Windows pregunte, haz clic en **Sí**. Solo hace falta la primera vez.
8. Se abre el centro de control en el navegador. Para conectar tus celulares, haz clic en **Vincular dispositivo** y sigue «¿Cómo vinculo un celular cámara?».

Deja la ventana de MeCam abierta (puedes minimizarla): al cerrarla se apagan las cámaras. Si prefieres la terminal, dentro de la carpeta `servidor` ejecuta `python servidor.py`.

### ¿Cómo se actualiza la app?

MeCam consulta si hay una versión nueva cuando la abres y cada 6 horas mientras transmite. Si la hay, aparece la notificación **"MeCam: hay una versión nueva"**. Al tocarla se abre la app con un botón **Actualizar MeCam a la versión N**. Tócalo y luego toca **Instalar** cuando Android lo pida.

Android **no permite** instalar sin que la persona lo autorice, así que siempre hace falta al menos un toque. Después de actualizar, abre MeCam una vez: la cámara se reanuda sola si estaba encendida.

Si tu versión es anterior a la 5, desinstala la app y vuelve a instalarla una vez.

### ¿Cómo actualizo el servidor en la computadora?

1. En la ventana de MeCam haz clic en **Detener servidor** y cierra la ventana.
2. Descarga el proyecto de nuevo (en la página del repositorio, **Code** y luego **Download ZIP**) o el archivo `MeCam-servidor.zip` si te lo pasaron. Haz clic derecho, **Extraer todo…** y **Extraer**.
3. En la carpeta nueva, dentro de **servidor**, haz doble clic en **Iniciar MeCam.bat**.

Tus dispositivos vinculados y el certificado se guardan aparte, en `%APPDATA%\MeCam`, así que **no hay que vincular nada de nuevo**. Cuando todo funcione puedes borrar la carpeta vieja. Cada versión nueva de la app llega sola, con el aviso de actualización.

### ¿Puedo conectar varios celulares?

Sí. Vincula cada celular con un QR distinto (mira «¿Cómo vinculo un celular cámara?»): cada uno recibe automáticamente su propio nombre («Cámara 1», «Cámara 2»…) y puedes cambiarlo con **Renombrar** en la ventana de MeCam. Solo si usas la conexión manual hay que ponerle un nombre distinto a cada celular en **Ajustes**.

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

- **Graba clips:** sí, cuando detecta una persona (mira la sección «Grabaciones»).
- **Manda alertas:** no por ahora.
- **Graba audio:** todavía no. También está en la lista, junto con las zonas de alerta.

## Grabaciones

### ¿Cómo funciona la grabación?

Cuando una cámara detecta una **persona**, MeCam guarda un clip corto con los recuadros de detección. Incluye unos **3 segundos de antes** de que apareciera, y sigue grabando hasta **6 segundos después** de que la persona se va (máximo 90 segundos por clip; si sigue habiendo alguien, empieza otro). Para evitar falsas alarmas, hace falta ver a la persona en dos cuadros seguidos. Solo se graban **personas**, no autos.

### ¿Dónde veo las grabaciones?

- En la ventana de MeCam, haz clic en **Ver grabaciones**.
- O en el centro de control, haz clic en el botón **Grabaciones** de la barra flotante (o pulsa la tecla **G**).
- O escribe `https://localhost:8443/grabaciones` en el navegador (desde otro aparato, cambia `localhost` por la IP de la computadora).

Cada grabación aparece con su miniatura, cámara, fecha, duración y tamaño. Toca una para verla; con las flechas ◀ ▶ pasas a la anterior o siguiente. Hay un filtro por cámara, y los botones **Descargar** y **Borrar**.

### ¿Dónde se guardan los archivos?

En la carpeta `grabaciones` dentro de `%APPDATA%\MeCam` (en la ventana de MeCam, el botón **Abrir carpeta** te lleva directo). No están en OneDrive ni en ninguna nube. Cada clip son tres archivos con el mismo nombre: el video (`.mp4`), una miniatura (`.jpg`) y un pequeño archivo de datos (`.json`).

### ¿Cuánto espacio ocupan?

Depende de la escena; no lo medí con el detector real, pero son clips cortos. Para que nunca se llene el disco, MeCam **borra solo** los clips de más de **30 días** y, si el total pasa de **5 GB**, los más antiguos. Arriba de la página de grabaciones ves cuánto espacio llevas usado.

### ¿Puedo elegir si se graba y qué cámaras graban?

Sí, la grabación es **optativa** y viene **activada**. Hay dos niveles:

**Interruptor general** (graba o no graba nada). Hay tres lugares y los tres están sincronizados:
- En la ventana de MeCam, la casilla **Grabar un clip cuando se detecte una persona**.
- En el centro de control, el botón redondo de la barra flotante (tecla **Q**). Rojo = activada, punteado = desactivada.
- En la página de grabaciones, el interruptor **Grabar clips** de arriba.

**Selector por cámara** (por ejemplo, no grabar la del dormitorio): en el centro de control, toca el indicador **REC** junto al nombre de la cámara (mira «¿Cómo uso el visor?»). También funciona en la vista ampliada, y la página de grabaciones te dice cuáles no graban.

Las dos elecciones se recuerdan al reiniciar. La elección por cámara se guarda con el **nombre** de la cámara: si la renombras, vuelve a grabar y tendrás que elegirlo otra vez. Apagar la grabación no borra los clips que ya tienes.

### ¿Con qué programa abro los archivos descargados?

Los `.mp4` usan un formato de video común pero antiguo: **VLC** (gratis) los abre siempre. Algunos navegadores y reproductores de Windows pueden no abrirlos. Por eso la página de grabaciones de MeCam los reproduce ella misma, sin descargar nada.

### ¿Los clips llevan audio?

No, todavía no: MeCam solo transmite video. El audio está en la lista de mejoras.

### ¿Quién puede ver las grabaciones?

Los mismos que pueden ver el centro de control: esta computadora, los dispositivos vinculados y tu red Tailscale (mira «Vincular dispositivos»). Sin esa autorización, la página de grabaciones muestra «Este dispositivo no está vinculado».

## Privacidad y seguridad

### ¿Mi video va a la nube?

No. El video viaja de tu celular a **tu computadora**, dentro de tu red. MeCam no lo sube a ningún servidor de terceros.

### ¿Cualquiera puede ver mis cámaras?

Cuando vinculas el primer dispositivo, MeCam se **protege**: solo entran los dispositivos vinculados con un QR, esta computadora y, si tienes Tailscale en ella, los aparatos de tu red Tailscale. Mientras no hayas vinculado nada, la ventana de MeCam muestra **Abierto** y cualquier persona dentro de tu Wi-Fi que conozca la dirección podría ver las cámaras. Por eso vincula tus dispositivos y no abras puertos en el router.

### ¿Por qué el navegador dice "Tu conexión no es privada"?

Porque MeCam crea su propio certificado en tu computadora (una sola vez, y lo guarda), y los navegadores solo confían en certificados emitidos por entidades conocidas. En tu propia red es seguro continuar: toca **Configuración avanzada** y luego **Acceder a ... (sitio no seguro)**. Cada navegador lo pregunta una vez; no vuelve a aparecer salvo que borres la carpeta `%APPDATA%\MeCam` o cambie la IP de la computadora.

### ¿Es legal grabar con MeCam?

Esto no es asesoramiento legal. En general, grabar dentro de tu casa es distinto a grabar la calle, a los vecinos o a personas que trabajan en tu casa: en muchos países (por ejemplo, en la UE con el RGPD) hay reglas sobre cámaras que enfocan espacios públicos o a terceros, como avisar con un cartel. Infórmate sobre las normas de tu país antes de instalar cámaras, y usa MeCam solo en espacios propios.

---

## Problemas frecuentes

### El celular dice "timed out" o "no se puede acceder al sitio"

Casi siempre es el **firewall de Windows**. En la ventana de MeCam haz clic en **Abrir puertos del firewall (una sola vez)** y en **Sí**. Si prefieres hacerlo a mano, abre `cmd` **como administrador** y ejecuta:

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
1. El servidor está en marcha (la ventana de MeCam dice **En marcha**).
2. Si la vinculaste con QR, la app se conecta sola. Si usas la conexión manual, la IP escrita es la que muestra la ventana de MeCam (y solo funciona mientras MeCam está **Abierto**).
3. El firewall permite el puerto **8080** (ver "timed out").
4. El celular y la computadora están en el **mismo Wi-Fi**.
5. Si la notificación dice «ya no está vinculada» o «no se pudo verificar la computadora», vuelve a escanear un QR nuevo.

### La página `/ver` no muestra ninguna cámara

Ves el mensaje "Esperando cámaras…": ningún celular está conectado. Mira la ventana negra: debe aparecer `[+] Cámara conectada: celular1`. La primera conexión tarda unos segundos porque carga el modelo.

### La IP de la computadora cambió y ya no conecta

El router puede darle otra IP a la computadora cuando se reinicia. Para que no cambie, entra a la configuración de tu router y busca **Reserva DHCP**, **IP estática** o **Asignación de direcciones**. Asigna una IP fija a la computadora. Después, si la cámara está vinculada, escanea un QR nuevo (la vinculación recuerda la IP anterior) y quita la cámara vieja de la lista con **Desvincular**. Si usas la conexión manual, escribe la IP nueva en la app.

### La imagen sale de lado o al revés

En MeCam cambia el selector **Orientación** a **vertical**, **horizontal (izquierda)** o **horizontal (derecha)**, y toca **Iniciar cámara** otra vez.

### La app dice que no pudo abrir la cámara

Otra app está usando la cámara. Ciérrala, cierra MeCam y vuelve a abrirla. Si sigue, reinicia el celular.

### Al escanear el QR, la app muestra un error

- **«Ese QR no es de MeCam»:** escaneaste otro código. Usa el que muestra la ventana **Vincular dispositivo** de MeCam en la computadora.
- **«Ese QR ya se usó o venció»:** cada QR sirve una sola vez y dura 5 minutos. La ventana muestra uno nuevo automáticamente; escanea el que se ve en ese momento.
- **«No se pudo verificar la computadora»:** escaneaste un QR que ya no corresponde a esta computadora. Escanea el más reciente y comprueba que no haya dos ventanas de MeCam abiertas.
- **«No se pudo conectar»:** el celular y la computadora deben estar en el **mismo Wi-Fi**, con el servidor en marcha, y el firewall debe permitir el puerto **8443** (botón **Abrir puertos del firewall** de la ventana de MeCam).
- **El escáner se abre en horizontal:** actualiza la app a la **versión 9 o superior**; desde ahí el escáner se abre en vertical.
- **El escáner no abre la cámara:** en la app toca **Permitir** cuando pida el permiso de cámara. Si lo negaste, actívalo en **Ajustes**, **Aplicaciones**, **MeCam**, **Permisos**.

### La app no se instala o dice que hay un conflicto con la versión instalada

Desinstala la versión anterior de MeCam (mantén pulsado su ícono, **Desinstalar**) y vuelve a instalar. Esto solo hace falta con versiones anteriores a la 5.

### El celular deja de transmitir después de un rato

Casi seguro el sistema cerró la app para ahorrar batería. Repite el paso de **Ajustes de batería** de la sección "Calor, batería y segundo plano". Si la notificación de MeCam dice "En pausa por calor", el celular se está enfriando: espera o baja los cuadros por segundo.

### No se guardan clips

1. Comprueba que la grabación esté activada (casilla en la ventana de MeCam, botón rojo en el centro de control o interruptor en la página de grabaciones) y que la cámara no tenga el **REC tachado**.
2. Solo se graba cuando hay una **persona** visible en dos cuadros seguidos; autos y otros objetos no disparan la grabación.
3. Si la cámara se desconecta o detienes el servidor en pleno clip, se guarda lo que había grabado.
4. Abre **Abrir carpeta**: si ahí hay archivos pero la página no los muestra, recárgala. Si la carpeta no se abre o el disco está lleno, mira el recuadro **Detalles** de la ventana de MeCam.

### En el centro de control algunas cámaras no cargan o dice «Sin conexión con el servidor»

Cada cámara abierta en el centro de control usa una conexión de video, y los navegadores permiten unas **6 conexiones por dirección**. Con 5 o más cámaras abiertas a la vez puede quedar sin lugar la conexión que consulta el estado. **No lo probé con tantas cámaras.** Si te pasa, cierra otras pestañas de MeCam y avísame (abre un **Issue**): está en la lista de mejoras.

### La ventana de MeCam no se abre

Abre la carpeta `servidor`: si hay un archivo `mecam_error.log`, contiene el motivo. Si la ventana se abre pero el servidor no arranca, mira el recuadro **Detalles** o el archivo `mecam.log`. Si falta algo por instalar, borra el archivo `.instalado-v2` de la carpeta y vuelve a abrir **Iniciar MeCam.bat**.

### Al hacer clic en "Iniciar servidor" dice que los puertos están en uso

Hay otro MeCam abierto: la ventana negra de antes (`python servidor.py`) u otra ventana de MeCam. Ciérralo y vuelve a probar.

---

¿Tienes una pregunta que no está aquí? Abre un **Issue** en este repositorio.
