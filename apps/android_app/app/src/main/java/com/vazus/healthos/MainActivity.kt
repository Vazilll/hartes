package com.vazus.healthos

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        setContentView(webView)

        setupWebView()
        requestPermissionsIfNeeded()
    }

    private fun setupWebView() {
        val settings: WebSettings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.allowFileAccess = true

        webView.webViewClient = WebViewClient()
        webView.addJavascriptInterface(WebAppInterface(this), "AndroidNative")

        // Load local interactive dashboard HTML asset
        webView.loadUrl("file:///android_asset/index.html")
    }

    private fun requestPermissionsIfNeeded() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }

        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 101)
        }
    }

    inner class WebAppInterface(private val activity: AppCompatActivity) {
        
        @JavascriptInterface
        fun startMiScaleBleScan(): String {
            // Simulated BLE Scan Result for Mi Body Scale 2
            val mockPayload = JSONObject().apply {
                put("status", "SUCCESS")
                put("device", "Mi Scale 2 (BLE 5.0)")
                put("weight_kg", 74.5)
                put("impedance_ohms", 480)
                put("body_fat_pct", 15.2)
                put("muscle_mass_kg", 59.8)
                put("water_pct", 61.4)
                put("bmr_kcal", 1740)
            }
            return mockPayload.toString()
        }

        @JavascriptInterface
        fun syncHealthConnectData(): String {
            // Simulated Google Health Connect Sync Result
            val mockSync = JSONObject().apply {
                put("status", "CONNECTED")
                put("provider", "Google Health Connect API")
                put("device_source", "Xiaomi Mi Band 8 / Zepp OS")
                put("trimp_today", 95.0)
                put("ctl_fitness", 54.2)
                put("atl_fatigue", 42.8)
                put("tsb_form", 11.4)
            }
            return mockSync.toString()
        }
        
        @JavascriptInterface
        fun showToast(msg: String) {
            Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
        }
    }
}
