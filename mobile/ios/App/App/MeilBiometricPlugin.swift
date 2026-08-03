import Foundation
import Capacitor
import LocalAuthentication

/// Meil'in arka plandan dönüşte uyguladığı Face ID / Touch ID kilidi.
/// static/app.js içindeki initNativeLock() bunu Cap.Plugins.MeilBiometric
/// üzerinden çağırır — üçüncü taraf bir JS paketine bağımlı değildir.
@objc(MeilBiometricPlugin)
public class MeilBiometricPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "MeilBiometricPlugin"
    public let jsName = "MeilBiometric"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "checkAvailable", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "authenticate", returnType: CAPPluginReturnPromise),
    ]

    @objc func checkAvailable(_ call: CAPPluginCall) {
        var error: NSError?
        let context = LAContext()
        let available = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
        call.resolve(["isAvailable": available])
    }

    @objc func authenticate(_ call: CAPPluginCall) {
        let context = LAContext()
        let reason = call.getString("reason") ?? "Kimliğinizi doğrulayın"
        var error: NSError?

        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            call.reject(error?.localizedDescription ?? "Biyometrik doğrulama kullanılamıyor")
            return
        }

        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { success, evalError in
            if success {
                call.resolve(["success": true])
            } else {
                call.reject(evalError?.localizedDescription ?? "Doğrulama başarısız", nil, evalError)
            }
        }
    }
}
