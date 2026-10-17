# Ingreso con Google

Primero se crea una cuenta de LibrIA con correo y contraseña. Una vez dentro, **Mi perfil → Mi cuenta** reúne los datos personales, tipo de perfil, solicitudes y métodos de ingreso. Para habilitar Google: escribir el correo de Google, enviar el código, ingresar los seis dígitos recibidos y pulsar **Confirmar vinculación con Google**, eligiendo exactamente el correo verificado. Después se puede ingresar con la contraseña habitual o con **Continuar con Google** en el login.

Google no crea cuentas ni vincula automáticamente por coincidencia de correo. El login solo acepta identidades previamente vinculadas por el `sub` estable de Google. La vinculación conserva el perfil, biblioteca, rol, correo de LibrIA y contraseña. El correo de Google puede ser diferente al de LibrIA; una identidad de Google solo puede vincularse a una cuenta de LibrIA. No se permite sustituir una identidad ya vinculada desde este flujo.

## Configuración local

En `apps/backend/.env`, configurar `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback` y `FRONTEND_ORIGINS=http://localhost:5173`. El primer origen es el destino fijo de regreso al frontend. Usar `localhost` al abrir la aplicación para mantener el mismo sitio en las cookies.

En Google Cloud, el cliente OAuth debe ser de tipo aplicación web y tener exactamente ese URI de redirección autorizado. Si el proyecto sigue en modo de pruebas, agregar las cuentas que probarán el ingreso como usuarios de prueba. Para admitir público general, configurar la audiencia externa y publicar la aplicación según los requisitos de Google.

Instalar `apps/backend/requirements.txt` en el entorno virtual, aplicar `python -m alembic upgrade head` desde `apps/backend` e iniciar con `run.cmd`. La migración `0041_google_login` agrega una identidad de Google única y opcional a cada cuenta existente.

La migración `0042_google_email_verification` agrega correo, estado de verificación y control de códigos. Una vinculación previa sin esta verificación debe completar la verificación y confirmar de nuevo la misma identidad de Google.

## Correo de verificación con Gmail

Completar en `apps/backend/.env`:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=cuenta-remitente@gmail.com
SMTP_PASSWORD=contraseña-de-aplicación
SMTP_FROM=cuenta-remitente@gmail.com
```

Usar una [contraseña de aplicación de Google](https://support.google.com/accounts/answer/185833?hl=es), que requiere verificación en dos pasos en la cuenta remitente. No usar la contraseña habitual ni publicar el `.env`. El remitente es la cuenta técnica que envía los códigos y puede ser distinto de los correos que verificarán los usuarios. `SMTP_FROM` vacío usa `SMTP_USERNAME`. El envío usa TLS y el puerto 465; también admite STARTTLS en 587, según la [documentación SMTP de Gmail](https://developers.google.com/workspace/gmail/imap/imap-smtp).

Reiniciar la API después de configurar las credenciales. Sin configuración o si falla Gmail, la API informa un error; no simula un envío exitoso ni entrega el código en la respuesta o los logs.

El código vence en cinco minutos, se almacena mediante HMAC vinculado al usuario y correo, admite cinco intentos y no se puede reutilizar. Se permite un envío por minuto y solicitar otro código invalida el anterior y cualquier verificación pendiente de vinculación. Verificar el correo por sí solo no habilita Google: aún se requiere confirmar esa misma identidad mediante OAuth.

El login solicita siempre `openid email profile`; `GOOGLE_OAUTH_SCOPE` ya no se usa. `GOOGLE_BOOKS_API_KEY` sigue siendo independiente del ingreso.

## Flujo y comprobación

El inicio de vinculación requiere un token de sesión de LibrIA y el correo verificado por código. El backend guarda una intención firmada, con estado OAuth, usuario, correo y expiración de diez minutos, en una cookie HttpOnly. El callback valida esa intención y la coincidencia del correo antes de vincular, además de comprobar la firma RS256, emisor, destinatario, vencimiento y nonce del ID token y el correo verificado por Google. La vinculación regresa a **Mi cuenta** con su resultado y no crea otra sesión.

En un ingreso posterior con Google, una cookie HttpOnly de 60 segundos permite completar la sesión desde el frontend sin incluir tokens en la URL. El endpoint de sesión exige un origen autorizado y borra la cookie al completarse. Los tokens de Google no se almacenan ni se entregan al navegador.

Pruebas automatizadas: `python -m unittest discover -s tests -p "test_google*.py"` y `python -m unittest discover -s tests -p test_security.py`. Cubren registro obligatorio en LibrIA, ausencia de vinculación automática, vinculación autenticada, contraseña conservada, identidad exclusiva, cancelación, validación del token y protección del intercambio de sesión.

Comprobación manual: registrarse en `http://localhost:5173/register`, abrir **Mi cuenta**, ingresar el correo de Google y solicitar el código. Comprobar su llegada real al buzón, ingresarlo y confirmar esa misma cuenta en Google. Cerrar sesión, pulsar **Continuar con Google** en el login y comprobar que se abre la misma cuenta. Cerrar sesión y repetir con correo y contraseña. También comprobar que Google sin vinculación previa no crea una cuenta y que cancelar la vinculación deja intacta la contraseña.

Referencia: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).

El formulario muestra siempre el campo de correo. Tras enviar el código, presenta un temporizador de cinco minutos basado en el vencimiento de la API; recargar conserva el tiempo pendiente. Al validar el código se abre Google automáticamente para confirmar esa identidad y, al volver, se muestra la cuenta vinculada.
