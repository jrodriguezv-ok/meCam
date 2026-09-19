package com.mecam.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.util.Size
import android.view.OrientationEventListener
import android.view.Surface
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleService
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Servicio en primer plano: mantiene la cámara y la transmisión
 * funcionando aunque la pantalla esté apagada.
 * Transmite de forma constante; si el celular se calienta, baja la
 * velocidad y, si sigue subiendo, pausa hasta que se enfríe.
 */
class CamaraService : LifecycleService() {

    companion object {
        const val CANAL = "mecam"
        const val PUERTO = 8080        // puerto sin certificado del servidor
        const val TEMP_BAJAR = 40f     // a esta temperatura baja a pocos cuadros por segundo
        const val TEMP_MAX = 42f       // a esta temperatura pausa la cámara
        const val TEMP_OK = 38f        // por debajo de esta vuelve a la velocidad normal
        const val FPS_CALIENTE = 4     // velocidad reducida cuando hace calor
    }

    private val principal = Handler(Looper.getMainLooper())
    private val ejecutor = Executors.newSingleThreadExecutor()
    private var proveedor: ProcessCameraProvider? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var cliente: OkHttpClient? = null
    private var ws: WebSocket? = null

    private var ip = ""
    private var nombre = "celular1"
    private var fps = 10
    private var orientacion = 0   // 0 automática, 1 vertical, 2 horizontal (izquierda), 3 horizontal (derecha)
    @Volatile private var rotacionAuto = Surface.ROTATION_0
    private var analisisActual: ImageAnalysis? = null
    private var sensorGiro: OrientationEventListener? = null
    private var detenido = false

    @Volatile private var conectado = false
    @Volatile private var esperando = false
    @Volatile private var enfriando = false   // cámara en pausa por calor
    @Volatile private var calor = false       // velocidad reducida por calor
    @Volatile private var ultimoEnvio = 0L

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val prefs = getSharedPreferences("mecam", Context.MODE_PRIVATE)
        ip = intent?.getStringExtra("ip") ?: prefs.getString("ip", "") ?: ""
        nombre = intent?.getStringExtra("nombre") ?: prefs.getString("nombre", "celular1") ?: "celular1"
        val fpsPedido = intent?.getIntExtra("fps", -1) ?: -1
        fps = (if (fpsPedido > 0) fpsPedido else prefs.getInt("fps", 10)).coerceIn(1, 25)
        val orientPedida = intent?.getIntExtra("orientacion", -1) ?: -1
        orientacion = if (orientPedida >= 0) orientPedida else prefs.getInt("orientacion", 0)
        analisisActual?.targetRotation = rotacionActual()

        crearCanal()
        val notif = crearNotificacion("Iniciando...")
        if (Build.VERSION.SDK_INT >= 30) {
            startForeground(1, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
        } else {
            startForeground(1, notif)
        }

        if (wakeLock == null) {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MeCam::camara")
            wakeLock?.acquire()
        }

        if (cliente == null) {
            cliente = OkHttpClient.Builder().pingInterval(20, TimeUnit.SECONDS).build()
            conectar()
            iniciarSensorGiro()
            iniciarCamara()
            vigilarTemperatura()
        }
        return START_NOT_STICKY
    }

    // ------------------------------------------------------------ Conexión
    private fun conectar() {
        if (detenido) return
        val pedido = Request.Builder().url("ws://$ip:$PUERTO/ws/$nombre").build()
        ws = cliente!!.newWebSocket(pedido, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                conectado = true
                esperando = false
                actualizarNotificacion("Transmitiendo como $nombre")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                esperando = false
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                perdida()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                perdida()
            }
        })
    }

    private fun perdida() {
        conectado = false
        esperando = false
        if (detenido) return
        actualizarNotificacion("Reconectando...")
        principal.postDelayed({ conectar() }, 3000)
    }

    // ------------------------------------------------------------ Cámara
    private fun iniciarCamara() {
        val futuro = ProcessCameraProvider.getInstance(this)
        futuro.addListener({
            proveedor = futuro.get()
            enlazar()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun enlazar() {
        val p = proveedor ?: return
        if (enfriando || detenido) return
        val analisis = ImageAnalysis.Builder()
            .setTargetResolution(Size(640, 480))
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
        analisis.targetRotation = rotacionActual()
        analisisActual = analisis
        analisis.setAnalyzer(ejecutor) { imagen -> procesar(imagen) }
        try {
            p.unbindAll()
            p.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, analisis)
        } catch (e: Exception) {
            actualizarNotificacion("Error de cámara: ${e.message}")
        }
    }

    private fun rotacionActual(): Int = when (orientacion) {
        1 -> Surface.ROTATION_0
        2 -> Surface.ROTATION_90
        3 -> Surface.ROTATION_270
        else -> rotacionAuto
    }

    // Detecta cómo está puesto el celular (vertical u horizontal) con el sensor de movimiento
    private fun iniciarSensorGiro() {
        val sensor = object : OrientationEventListener(this) {
            override fun onOrientationChanged(grados: Int) {
                if (grados == OrientationEventListener.ORIENTATION_UNKNOWN) return
                rotacionAuto = when (grados) {
                    in 45..134 -> Surface.ROTATION_270
                    in 135..224 -> Surface.ROTATION_180
                    in 225..314 -> Surface.ROTATION_90
                    else -> Surface.ROTATION_0
                }
                if (orientacion == 0) analisisActual?.targetRotation = rotacionAuto
            }
        }
        if (sensor.canDetectOrientation()) sensor.enable()
        sensorGiro = sensor
    }

    private fun procesar(imagen: ImageProxy) {
        try {
            val ahora = System.currentTimeMillis()
            if (!conectado || enfriando) return
            if (esperando && ahora - ultimoEnvio < 5000) return
            val fpsActual = if (calor) minOf(fps, FPS_CALIENTE) else fps
            if (ahora - ultimoEnvio < 1000L / fpsActual) return

            val bmp = imagen.toBitmap()
            val giro = imagen.imageInfo.rotationDegrees
            val final = if (giro != 0) {
                val m = Matrix().apply { postRotate(giro.toFloat()) }
                Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, m, true)
            } else bmp
            val salida = ByteArrayOutputStream()
            final.compress(Bitmap.CompressFormat.JPEG, 60, salida)
            esperando = true
            ultimoEnvio = ahora
            ws?.send(salida.toByteArray().toByteString())
        } finally {
            imagen.close()
        }
    }

    // ------------------------------------------------------------ Temperatura
    private fun vigilarTemperatura() {
        val tarea = object : Runnable {
            override fun run() {
                if (detenido) return
                val estadoBateria = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
                val temp = (estadoBateria?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10f

                if (!enfriando && temp >= TEMP_MAX) {
                    enfriando = true
                    proveedor?.unbindAll()
                    actualizarNotificacion("En pausa por calor ($temp °C)")
                } else if (enfriando) {
                    if (temp > 0f && temp <= TEMP_OK) {
                        enfriando = false
                        calor = false
                        enlazar()
                        actualizarNotificacion("Transmitiendo como $nombre")
                    }
                } else {
                    val nuevo = if (calor) temp >= TEMP_OK else temp >= TEMP_BAJAR
                    if (nuevo != calor) {
                        calor = nuevo
                        actualizarNotificacion(
                            if (calor) "Velocidad reducida por calor ($temp °C)"
                            else "Transmitiendo como $nombre"
                        )
                    }
                }
                principal.postDelayed(this, 30_000)
            }
        }
        principal.post(tarea)
    }

    // ------------------------------------------------------------ Notificación
    private fun crearCanal() {
        if (Build.VERSION.SDK_INT >= 26) {
            val m = getSystemService(NotificationManager::class.java)
            m.createNotificationChannel(
                NotificationChannel(CANAL, "MeCam", NotificationManager.IMPORTANCE_LOW)
            )
        }
    }

    private fun crearNotificacion(texto: String): Notification =
        NotificationCompat.Builder(this, CANAL)
            .setContentTitle("MeCam")
            .setContentText(texto)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()

    private fun actualizarNotificacion(texto: String) {
        getSystemService(NotificationManager::class.java).notify(1, crearNotificacion(texto))
    }

    override fun onDestroy() {
        detenido = true
        principal.removeCallbacksAndMessages(null)
        sensorGiro?.disable()
        proveedor?.unbindAll()
        ws?.close(1000, null)
        cliente?.dispatcher?.executorService?.shutdown()
        ejecutor.shutdown()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }
}
