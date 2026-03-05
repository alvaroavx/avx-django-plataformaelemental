## Usar este archivo para:
- objetivos del repo
- convenciones (arquitectura, naming, estilo)
## Estructura del proyecto
api/ contiene las apis hacia el exterior de esta plataforma
data/ cargas masivas de informacion
database/ modelo de datos del proyecto
finanzas/ nueva app de finanzas
plataformaelemental/ config de django
asistencias/ aplicacion de asistencias
## Reglas de Desarrollo
1.Todo modelo de datos sera trabajado dentro de la aplicacion 'database'. 
2.Que el codigo este en lo posible en espanol, excepto para casos donde en ingles hace mas sentido.
3.El monto de dinero siempre sera visto en CPL, sin decimales, y con los cientos separados por punto.
4.Los filtros del menu superior: mes, ano y organizacion. Seran arrastrados en toda la aplicacion y seran siempre mantenidos activos.
5.No duplicar codigo, no reinventar lo que ya hay.