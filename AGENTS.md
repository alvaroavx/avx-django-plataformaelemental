## Usar este archivo para:
- objetivos del repo
- convenciones (arquitectura, naming, estilo)

## Documentacion viva
- Antes de hacer cambios transversales, revisar `docs/INDICE.md` y `docs/arquitectura/PLATAFORMA.md`.
- Antes de trabajar una app puntual, revisar su archivo local:
  - `docs/apps/ASISTENCIAS.md`
  - `docs/apps/PERSONAS.md`
  - `docs/apps/FINANZAS.md`
  - `docs/apps/API.md`
- Cada decision concreta debe actualizar su `.md` correspondiente en el mismo cambio de codigo.

## Estructura del proyecto
api/ contiene las apis hacia el exterior de esta plataforma
data/ cargas masivas de informacion
database/ namespace legado de migraciones y compatibilidad historica
finanzas/ nueva app de finanzas
plataformaelemental/ config de django
asistencias/ aplicacion de asistencias
## Reglas de Desarrollo
1.Cada modelo de datos debe vivir en su app duena:
  - `personas` para personas, roles y organizaciones
  - `asistencias` para disciplinas, sesiones y asistencias
  - `finanzas` para pagos, documentos tributarios y transacciones
  - `database` no recibe modelos nuevos; solo mantiene compatibilidad historica de migraciones mientras exista ese legado
2.Que el codigo este en lo posible en espanol, excepto para casos donde en ingles hace mas sentido.
3.El monto de dinero siempre sera visto en CPL, sin decimales, y con los cientos separados por punto.
4.Los filtros del menu superior: mes, ano y organizacion. Seran arrastrados en toda la aplicacion y seran siempre mantenidos activos.
5.No duplicar codigo, no reinventar lo que ya hay.
6.Cada cambio visual o funcional en desktop debe considerar su equivalente responsive. No se trata de replicar exactamente la misma interfaz, sino de resolver bien la misma necesidad en mobile.
