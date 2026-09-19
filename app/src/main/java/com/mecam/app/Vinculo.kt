package com.mecam.app

import android.content.Context
import android.net.Uri
import android.os.Build
import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLException
import javax.net.ssl.X509TrustManager

/**
 * Vinculación con la computadora mediante el QR.
 * La conexión es cifrada y solo confía en el certificado cuya huella viene dentro del QR.
 */
object Vinculo {
    class Datos(val host: String, val puerto: Int, val token: String, val huella: String)

    class Resultado(val ok: Boolean, val mensaje: String)

    fun huellaDe(cert: X509Certificate): String {
        val h = MessageDigest.getInstance("SHA-256").digest(cert.encoded)
        return Base64.encodeToString(h, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    }

    private class ConfianzaFija(private val huella: String) : X509TrustManager {
        override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}

        override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
            if (chain.isEmpty() || huellaDe(chain[0]) != huella) {
                throw CertificateException("El certificado no es el de tu computadora MeCam")
            }
        }

        override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
    }

    /** Cliente que solo habla con la computadora cuyo certificado tiene esta huella. */
    fun clienteFijado(huella: String): OkHttpClient.Builder {
        val confianza = ConfianzaFija(huella)
        val ssl = SSLContext.getInstance("TLS")
        ssl.init(null, arrayOf(confianza), SecureRandom())
        return OkHttpClient.Builder()
            .sslSocketFactory(ssl.socketFactory, confianza)
            .hostnameVerifier { _, _ -> true }   // la huella del QR ya identifica a tu computadora
            .connectTimeout(10, TimeUnit.SECONDS)
    }

    /** Interpreta el QR: https://IP:8443/v/CODIGO#fp=HUELLA */
    fun parsear(texto: String): Datos? {
        return try {
            val uri = Uri.parse(texto.trim())
            val partes = uri.pathSegments
            val huella = uri.fragment?.removePrefix("fp=") ?: return null
            val host = uri.host
            if (uri.scheme != "https" || host.isNullOrEmpty() || partes.size != 2 ||
                partes[0] != "v" || huella.length < 20
            ) {
                return null
            }
            Datos(host, if (uri.port > 0) uri.port else 443, partes[1], huella)
        } catch (e: Exception) {
            null
        }
    }

    /** Canjea el código del QR y guarda la credencial propia de este celular. */
    fun vincular(ctx: Context, d: Datos): Resultado {
        return try {
            val cliente = clienteFijado(d.huella).callTimeout(15, TimeUnit.SECONDS).build()
            val cuerpo = JSONObject()
                .put("token", d.token)
                .put("modelo", Build.MODEL ?: "")
                .toString()
                .toRequestBody("application/json".toMediaType())
            val pedido = Request.Builder()
                .url("https://${d.host}:${d.puerto}/api/vincular")
                .post(cuerpo)
                .build()
            cliente.newCall(pedido).execute().use { r ->
                if (r.code == 403) {
                    return Resultado(false, "Ese QR ya se usó o venció. Toca «Vincular dispositivo» en la computadora para generar uno nuevo.")
                }
                if (!r.isSuccessful) return Resultado(false, "El servidor respondió con el código ${r.code}.")
                val cuerpoRespuesta = r.body?.string() ?: return Resultado(false, "Respuesta vacía del servidor.")
                val j = JSONObject(cuerpoRespuesta)
                ctx.getSharedPreferences("mecam", Context.MODE_PRIVATE).edit()
                    .putString("v_host", d.host)
                    .putInt("v_puerto", d.puerto)
                    .putString("v_huella", d.huella)
                    .putString("v_id", j.getString("id"))
                    .putString("v_secreto", j.getString("secreto"))
                    .putString("v_nombre", j.getString("nombre"))
                    .putBoolean("activo", false)
                    .apply()
                Resultado(true, j.getString("nombre"))
            }
        } catch (e: SSLException) {
            Resultado(false, "No se pudo verificar la computadora. ¿Escaneaste el QR más reciente?")
        } catch (e: IOException) {
            Resultado(false, "No se pudo conectar. Revisa que estés en el mismo Wi-Fi y que MeCam esté en marcha en la computadora.")
        } catch (e: Exception) {
            Resultado(false, "Error: ${e.message}")
        }
    }

    fun vinculada(ctx: Context): Boolean {
        val p = ctx.getSharedPreferences("mecam", Context.MODE_PRIVATE)
        return !p.getString("v_secreto", "").isNullOrEmpty() && !p.getString("v_host", "").isNullOrEmpty()
    }

    fun olvidar(ctx: Context) {
        ctx.getSharedPreferences("mecam", Context.MODE_PRIVATE).edit()
            .remove("v_host").remove("v_puerto").remove("v_huella")
            .remove("v_id").remove("v_secreto").remove("v_nombre")
            .putBoolean("activo", false)
            .apply()
    }
}
