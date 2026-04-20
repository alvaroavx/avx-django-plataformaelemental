# Seguridad En Produccion

Fecha de actualizacion: 2026-04-20

## Contexto
La plataforma esta publicada en produccion y se detecto que una sesion iniciada el dia anterior seguia activa al dia siguiente.

## Decision
La configuracion de seguridad de produccion debe ser mas estricta que desarrollo y debe vivir en `plataformaelemental/config/prod.py`.

## Sesiones
- Las sesiones de produccion usan timeout por inactividad de 2 horas por defecto.
- `SESSION_COOKIE_AGE` se puede ajustar con la variable de entorno `SESSION_COOKIE_AGE`.
- `SESSION_EXPIRE_AT_BROWSER_CLOSE=True` para pedir al navegador que elimine la cookie al cerrar.
- `SESSION_SAVE_EVERY_REQUEST=True` para renovar expiracion mientras exista actividad real.
- `SESSION_COOKIE_NAME=elemental_sessionid` por defecto para invalidar las cookies antiguas llamadas `sessionid` luego del deploy.
- El cambio de nombre de cookie fuerza cierre de sesion a usuarios autenticados con la cookie anterior.

## Cookies
- `SESSION_COOKIE_HTTPONLY=True`.
- `SESSION_COOKIE_SAMESITE=Lax`.
- `CSRF_COOKIE_SAMESITE=Lax`.
- En produccion:
  - `SESSION_COOKIE_SECURE=True`.
  - `CSRF_COOKIE_SECURE=True`.

## HTTPS
- `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")` se mantiene para operar detras de proxy o balanceador.
- `SECURE_SSL_REDIRECT=True` por defecto en produccion.
- Puede desactivarse temporalmente con `DJANGO_SECURE_SSL_REDIRECT=False` solo si el proxy ya maneja redireccion HTTPS o hay riesgo de loop.
- HSTS queda activo con `DJANGO_SECURE_HSTS_SECONDS=3600` por defecto.
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False` por defecto.
- `DJANGO_SECURE_HSTS_PRELOAD=False` por defecto.
- `check --deploy` puede advertir que `SECURE_HSTS_INCLUDE_SUBDOMAINS` y `SECURE_HSTS_PRELOAD` no estan activos; es una decision conservadora hasta confirmar que todo el dominio y subdominios operan solo por HTTPS.

## Headers
- `SECURE_CONTENT_TYPE_NOSNIFF=True`.
- `SECURE_REFERRER_POLICY=same-origin`.
- `X_FRAME_OPTIONS=DENY`.

## Variables De Entorno Relevantes
```env
SESSION_COOKIE_NAME=elemental_sessionid
SESSION_COOKIE_AGE=7200
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=3600
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
DJANGO_SECURE_HSTS_PRELOAD=False
```

## Deploy
- `scripts/deploy.sh` ejecuta `python manage.py clearsessions` despues de `migrate`.
- `clearsessions` solo borra sesiones expiradas.
- La invalidacion inmediata de sesiones antiguas se produce por el cambio de `SESSION_COOKIE_NAME`.

## Reglas Operativas
- No versionar secretos reales en `.env.dev`, `.env.prod` ni otros archivos de entorno.
- `.env.example` debe contener solo placeholders.
- Si se cambia `SESSION_COOKIE_NAME`, todos los usuarios deberan volver a iniciar sesion.
- Si se aumenta `SESSION_COOKIE_AGE`, debe quedar documentado como decision explicita.
