## Usar este archivo para:
- objetivos del repo
- convenciones (arquitectura, naming, estilo)
- â€œno inventarâ€, â€œno duplicarâ€
- cÃ³mo correr tests / lint
## Estructura del proyecto
api/ contiene las apis hacia el exterior de esta plataforma
data/ cargas masivas de informacion
database/ modelo de datos del proyecto
finanzas/ nueva app de finanzas
plataformaelemental/ config de django
asistencias/ aplicaciÃ³n de asistencias
## Reglas de Desarrollo
1.Todo modelo de datos serÃ¡ trabajado dentro de la aplicaciÃ³n 'database'. 
2.Que el cÃ³digo estÃ© en lo posible en espaÃ±ol, excepto para casos donde en inglÃ©s hace mÃ¡s sentido.
3.El monto de dinero siempre serÃ¡ visto en CPL, sin decimales, y con los cientos separados por punto.
4.Los filtros del menÃº superior: mes, aÃ±o y organizacion. SerÃ¡n arrastrados en toda la aplicaciÃ³n y serÃ¡n siempre mantenidos activos.
