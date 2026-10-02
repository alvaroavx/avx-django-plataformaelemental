# D-003: El desarrollo local con Google usa `127.0.0.1:8000`

**Fecha:** 2026-10-02 | **Decidió:** Álvaro | **Estado:** vigente

## Contexto

Google bloqueó un inicio de sesión porque el intento había sido creado desde el
puerto anterior `8002`, mientras Elemental ya operaba en `8000`. OAuth compara
el `redirect_uri` completo y trata como distintos el esquema, host, puerto y
ruta; una pestaña de error antigua conserva el callback con que comenzó.

## Alternativas descartadas

- Autorizar cualquier puerto local — Google OAuth no admite comodines de puerto para este callback y multiplicaría configuraciones propensas a desalinearse.
- Usar indistintamente `localhost` y `127.0.0.1` — son hosts diferentes para OAuth y obligan a mantener dos callbacks exactos.
- Continuar con `8002` — contradice el puerto local elegido para la aplicación y la configuración de orígenes confiables.

## Decisión

El origen canónico para ejecutar y probar Elemental localmente, incluido Google
OAuth, es `http://127.0.0.1:8000`; el callback autorizado correspondiente es
`http://127.0.0.1:8000/accounts/google/login/callback/`.

## Consecuencias asumidas

- El servidor local debe iniciarse con `python manage.py runserver 127.0.0.1:8000`.
- Tras cambiar host o puerto se debe iniciar el login Google desde Elemental en una pestaña nueva; no se reutiliza la página de error anterior.
- Si Google informa `redirect_uri_mismatch`, se inspecciona primero el `redirect_uri` mostrado por Google y se compara literalmente con el callback autorizado.
- Credenciales, client secret y configuración privada de Google Cloud no se documentan ni versionan.

## Condiciones de revisión

Revisar esta decisión si el entorno local adopta HTTPS, un proxy de desarrollo
con URL estable o un puerto canónico diferente que también se registre de forma
explícita en Google Cloud y en la configuración local.
