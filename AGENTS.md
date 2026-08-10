## Usar este archivo para:
- objetivos del repo
- convenciones (arquitectura, naming, estilo)

## Documentacion viva
- Antes de hacer cambios transversales, revisar `docs/INDICE.md` y `docs/arquitectura/PLATAFORMA.md`.
- Antes de crear scripts, fixtures, cargas, recorridos de navegador o utilidades
  temporales, revisar `docs/proceso/ARTEFACTOS.md` y el inventario existente. Si
  un artefacto puede generalizarse, extenderlo en vez de crear otro desde cero.
- Antes de trabajar una app puntual, revisar su archivo local:
  - `docs/apps/ASISTENCIAS.md`
  - `docs/apps/PERSONAS.md`
  - `docs/apps/FINANZAS.md`
  - `docs/apps/API.md`
- Cada decision concreta debe actualizar su `.md` correspondiente en el mismo cambio de codigo.

## Artefactos de trabajo
- Los scripts, fixtures, trazas, capturas y resultados que se creen y usen para
  completar una tarea deben conservarse, sanitizarse y documentarse según
  `docs/proceso/ARTEFACTOS.md`.
- No borrar un artefacto útil porque terminó la tarea. Si queda obsoleto, marcarlo
  como reemplazado y enlazar su sucesor.
- Nunca persistir secretos, datos personales reales, dumps, perfiles de navegador
  ni dependencias descargadas. Conservar en su lugar la herramienta parametrizada,
  una evidencia sanitizada o la receta reproducible.
- Antes de delegar a un subagente, el agente principal debe revisar el inventario
  y entregarle las rutas reutilizables pertinentes. El subagente debe preferir
  extender esos artefactos y reportar cualquier artefacto nuevo para incorporarlo
  al inventario.

## Estructura del proyecto
api/ contiene las apis hacia el exterior de esta plataforma
data/ cargas masivas de informacion
finanzas/ nueva app de finanzas
plataformaelemental/ config de django
asistencias/ aplicacion de asistencias

## Entorno local
- Usar Python 3.12 para el entorno virtual local: `python3.12 -m venv .venv`.
- No usar `python3 -m venv` en este proyecto si el alias `python3` apunta a Python 3.14.
- Instalar dependencias con `python -m pip install -r requirements.txt` dentro del entorno activado.

## Reglas de Desarrollo
1.Cada modelo de datos debe vivir en su app duena:
  - `personas` para personas, roles y organizaciones
  - `asistencias` para disciplinas, sesiones y asistencias
  - `finanzas` para pagos, documentos tributarios y transacciones
2.Que el codigo este en lo posible en espanol, excepto para casos donde en ingles hace mas sentido.
3.El monto de dinero siempre sera visto en CLP, sin decimales, y con los cientos separados por punto.
4.Los filtros del menu superior: mes, ano y organizacion. Seran arrastrados en toda la aplicacion y seran siempre mantenidos activos.
5.No duplicar codigo, no reinventar lo que ya hay.
6.Cada cambio visual o funcional en desktop debe considerar su equivalente responsive. No se trata de replicar exactamente la misma interfaz, sino de resolver bien la misma necesidad en mobile.
7.Cada cambio de modelo o migracion debe asumir que produccion ya tiene datos reales. La primera opcion siempre es preservar esos datos. Si una solicitud implica borrar, sobrescribir, recalcular destructivamente o volver inaccesible data productiva, se debe alertar antes de implementar y proponer caminos alternativos seguros.

## Definición de hecho
Un cambio se considera terminado solo si:
- `python manage.py check` pasa.
- Los tests relevantes pasan.
- Si toca modelos, incluye migración revisada y compatible con datos existentes de produccion.
- Si toca lógica financiera, incluye test de regla.
- Si toca UI desktop, revisa mobile.
- Si mueve una responsabilidad, actualiza docs.

## Fronteras de dominio
- `personas` define identidad: Persona, Organizacion, Rol, PersonaRol.
- `asistencias` define operación de clases: Disciplina, BloqueHorario, SesionClase, Asistencia.
- `cobranzas` es un dominio conceptual, por ahora implementado dentro de `finanzas/services/`, y maneja planes, pagos operacionales, deuda e imputación de clases.
- `finanzas` maneja contabilidad: documentos tributarios, transacciones, categorías, reportes para contadora.
- `monitor` es herramienta interna y no debe depender del core operacional.

## Reglas de dependencia
- Ninguna app debe importar helpers desde `views.py` de otra app.
- La lógica compartida de filtros globales vive en un módulo neutral.
- Las views coordinan request/response; no contienen reglas de negocio complejas.
- Templates no calculan deuda, pagos ni estados financieros.
- Los servicios pueden coordinar modelos de varias apps cuando representen un caso de uso claro.
- Los documentos tributarios son snapshots legales; pueden duplicar nombre/RUT/montos.
- Los pagos operacionales pueden guardar montos históricos; deben tener invariantes claras.
