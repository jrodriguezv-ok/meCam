package com.mecam.app

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import androidx.core.content.pm.PackageInfoCompat
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/** Busca versiones nuevas de MeCam en GitHub Releases y las instala. */
object Actualizador {
    private const val REPO = "jrodriguezv-ok/meCam"
    private const val APK_URL = "https://github.com/$REPO/releases/download/ultima-version/MeCam.apk"
    private const val API_URL = "https://api.github.com/repos/$REPO/releases/tags/ultima-version"

    private val cliente = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    fun versionInstalada(ctx: Context): Long {
        val info = ctx.packageManager.getPackageInfo(ctx.packageName, 0)
        return PackageInfoCompat.getLongVersionCode(info)
    }

    /** Número de la última versión publicada, o null si no se pudo consultar. */
    fun ultimaVersion(): Long? {
        return try {
            val pedido = Request.Builder()
                .url(API_URL)
                .header("Accept", "application/vnd.github+json")
                .build()
            cliente.newCall(pedido).execute().use { r ->
                if (!r.isSuccessful) return null
                val texto = r.body?.string() ?: return null
                val cuerpo = JSONObject(texto).optString("body")
                Regex("versionCode=(\\d+)").find(cuerpo)?.groupValues?.get(1)?.toLong()
            }
        } catch (e: Exception) {
            null
        }
    }

    /** Descarga el APK nuevo y lo entrega al instalador de Android. Devuelve un mensaje si algo falló. */
    fun descargarEInstalar(ctx: Context): String? {
        return try {
            val destino = File(ctx.cacheDir, "MeCam-nueva.apk")
            cliente.newCall(Request.Builder().url(APK_URL).build()).execute().use { r ->
                if (!r.isSuccessful) return "No se pudo descargar (código ${r.code})"
                val cuerpo = r.body ?: return "Descarga vacía"
                cuerpo.byteStream().use { entrada ->
                    destino.outputStream().use { salida -> entrada.copyTo(salida) }
                }
            }
            instalar(ctx, destino)
            null
        } catch (e: Exception) {
            "Error: ${e.message}"
        }
    }

    private fun instalar(ctx: Context, apk: File) {
        val instalador = ctx.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        if (Build.VERSION.SDK_INT >= 31) {
            // En Android 12+ puede instalarse sin pedir confirmación, si el sistema lo permite
            params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        }
        val id = instalador.createSession(params)
        instalador.openSession(id).use { sesion ->
            apk.inputStream().use { entrada ->
                sesion.openWrite("MeCam", 0, apk.length()).use { salida ->
                    entrada.copyTo(salida)
                    sesion.fsync(salida)
                }
            }
            val intent = Intent(ctx, InstalacionReceiver::class.java)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val pendiente = PendingIntent.getBroadcast(ctx, id, intent, flags)
            sesion.commit(pendiente.intentSender)
        }
    }
}
