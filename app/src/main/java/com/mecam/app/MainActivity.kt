package com.mecam.app

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private lateinit var campoIp: EditText
    private lateinit var campoNombre: EditText
    private lateinit var campoFps: EditText
    private lateinit var estado: TextView

    private val pedirPermisos = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        val camaraOk = ContextCompat.checkSelfPermission(
            this, Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED
        if (camaraOk) {
            iniciarServicio()
        } else {
            estado.text = "Falta el permiso de cámara. Toca Iniciar y elige Permitir."
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("mecam", Context.MODE_PRIVATE)
        val pad = (20 * resources.displayMetrics.density).toInt()

        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }
        val titulo = TextView(this).apply {
            text = "MeCam"
            textSize = 28f
        }
        campoIp = EditText(this).apply {
            hint = "IP de la computadora (ej: 192.168.1.128)"
            setText(prefs.getString("ip", ""))
        }
        campoNombre = EditText(this).apply {
            hint = "Nombre de esta cámara (ej: celular1)"
            setText(prefs.getString("nombre", "celular1"))
        }
        campoFps = EditText(this).apply {
            hint = "Cuadros por segundo (1 a 25, ej: 10)"
            inputType = InputType.TYPE_CLASS_NUMBER
            setText(prefs.getInt("fps", 10).toString())
        }
        val botonIniciar = Button(this).apply {
            text = "Iniciar cámara"
            setOnClickListener { pedir() }
        }
        val botonDetener = Button(this).apply {
            text = "Detener"
            setOnClickListener {
                stopService(Intent(this@MainActivity, CamaraService::class.java))
                estado.text = "Detenida."
            }
        }
        val botonBateria = Button(this).apply {
            text = "Ajustes de batería (para que no se cierre)"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
        }
        estado = TextView(this).apply {
            textSize = 16f
            setPadding(0, pad, 0, 0)
        }

        listOf(titulo, campoIp, campoNombre, campoFps, botonIniciar, botonDetener, botonBateria, estado)
            .forEach { raiz.addView(it) }
        setContentView(raiz)
    }

    private fun pedir() {
        if (campoIp.text.toString().trim().isEmpty()) {
            estado.text = "Escribe la IP de la computadora."
            return
        }
        val lista = mutableListOf(Manifest.permission.CAMERA)
        if (Build.VERSION.SDK_INT >= 33) lista.add(Manifest.permission.POST_NOTIFICATIONS)
        pedirPermisos.launch(lista.toTypedArray())
    }

    private fun iniciarServicio() {
        val ip = campoIp.text.toString().trim()
        val nombre = campoNombre.text.toString().trim().ifEmpty { "celular1" }
        val fps = (campoFps.text.toString().toIntOrNull() ?: 10).coerceIn(1, 25)
        getSharedPreferences("mecam", Context.MODE_PRIVATE).edit()
            .putString("ip", ip)
            .putString("nombre", nombre)
            .putInt("fps", fps)
            .apply()
        val intent = Intent(this, CamaraService::class.java)
            .putExtra("ip", ip)
            .putExtra("nombre", nombre)
            .putExtra("fps", fps)
        ContextCompat.startForegroundService(this, intent)
        estado.text = "Cámara iniciada. Ya puedes apagar la pantalla."
    }
}
