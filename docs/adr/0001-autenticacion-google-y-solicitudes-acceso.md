# ADR 0001: Autenticacion Google y solicitudes de acceso

Fecha: 2026-07-20

## Contexto

Plataforma Elemental usa `django.contrib.auth.User` y relacion opcional `Persona.user`.
La identidad de una cuenta Google no equivale a autorizacion: el acceso sigue dependiendo de `PersonaRol` y de los permisos Django existentes.

La plataforma tiene una brecha historica de aislamiento multi-organizacion. La autenticacion nueva no puede ampliarla ni habilitar aprobaciones de usuarios nuevos hasta que exista evidencia negativa de aislamiento.

## Decision

- Se usara `django-allauth` con Google; no se implementara OAuth manualmente.
- Se preservan `User`, sus IDs, `Persona.user`, `PersonaRol`, sesiones Django, `login_required` y la auditoria atribuida a `User`.
- Google autentica identidad; nunca asigna organizaciones, roles ni permisos por correo, dominio o existencia de cuenta.
- La identidad estable se resuelve primero por `SocialAccount(provider=google, uid=sub)`. El fallback por correo solo sirve para enlazar un `User` activo, unico y con correo Google verificado; cualquier duplicado, inactividad o conflicto falla cerrado.
- No se insertara `SocialAccount` manualmente ni se guardaran tokens, codes, secretos o respuestas OAuth completas.
- Una identidad desconocida puede crear una `SolicitudAcceso`, pero esta no crea `User`, `Persona`, `PersonaRol` ni `SocialAccount`.
- La aprobacion administrativa requiere permiso global explicito `personas.gestionar_solicitudes_acceso`, no se concede por `staff` ni por `PersonaRol`.
- La aprobacion se implementara como servicio atomico y auditado; el enlace social se completara solamente durante un `SocialLogin` validado posterior, usando API publica soportada por allauth.
- Todos los flags son opt-in y seguros por defecto: `GOOGLE_AUTH_ENABLED`, `ACCESS_REQUESTS_ENABLED`, `ACCESS_REQUEST_APPROVAL_ENABLED` y `GOOGLE_AUTH_ENFORCED` parten en `false`.
- `ACCESS_REQUEST_APPROVAL_ENABLED` y `GOOGLE_AUTH_ENFORCED` son security gates: no se habilitaran hasta corregir y probar el aislamiento multi-organizacion en listados, detalles, mutaciones, filtros, exports, JSON y navegacion directa.

## Consecuencias

- Se agregara una auditoria read-only de identidad antes de cualquier cambio de unicidad sobre `auth_user.email`.
- No se agrega ahora una constraint unica a `auth_user.email`; cualquier propuesta futura requiere datos auditados y revision separada.
- Se mantiene una ruta local de emergencia no visible, limitada a superusuarios cuando Google se fuerce.
- La bandeja de solicitudes y el badge son una proyeccion de `SolicitudAcceso`, no una app generica de notificaciones.
- La configuracion Google vive exclusivamente en variables de entorno y el callback productivo sera `https://apps.espacioelementos.cl/accounts/google/login/callback/`.

## Protocolo OAuth y sesion

- Google se configura solo por settings/variables de entorno; no se crea un `SocialApp` paralelo en Django Admin.
- Los scopes son `openid`, `email` y `profile`; el parametro es `access_type=online` y PKCE queda habilitado.
- `SOCIALACCOUNT_STORE_TOKENS=False`. El adaptador OAuth propio elimina `extra_data` antes de que allauth ejecute cualquier lookup, por lo que no persiste respuestas OAuth ni tokens.
- Solo se exponen la ruta POST `/accounts/google/iniciar/` y el callback `/accounts/google/login/callback/`; no se incluye el conjunto general de rutas de allauth.
- El inicio Google usa POST con CSRF. allauth conserva y valida el estado OAuth; el `next` se valida en servidor con host local y se fuerzan `process=login`, los scopes minimos y `access_type=online` antes de iniciar el flujo.
- El callback se delega al callback OAuth2 de allauth para que siempre valide y consuma `state`, incluso ante cancelacion o error. El adaptador redirige esos errores al login sin crear sesion.
- Las identidades pendientes de solicitud viven solo en sesion Django de servidor con TTL de 10 minutos; no aceptan subject, email o verificacion desde el navegador. Para evitar abuso, cada identidad validada puede crear hasta cinco solicitudes nuevas por ventana de 24 horas; recuperar una pendiente no consume ese limite.

## Rollout y rollback

El despliegue futuro se hara con flags apagados. La activacion sera gradual y reversible apagando flags; no se revertiran migraciones ni se eliminaran solicitudes/asociaciones durante un incidente. La autenticacion local de emergencia se conserva para superusuarios.
