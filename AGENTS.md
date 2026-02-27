## Usar este archivo para:
- objetivos del repo
- convenciones (arquitectura, naming, estilo)
- “no inventar”, “no duplicar”
- cómo correr tests / lint
## Estructura del proyecto
api/ contiene las apis hacia el exterior de esta plataforma
data/ cargas masivas de informacion
database/ modelo de datos del proyecto
finanzas/ nueva app de finanzas
plataformaelemental/ config de django
webapp/ aplicación de asistencias
## Reglas de Desarrollo
1.Todo modelo de datos será trabajado dentro de la aplicación 'database'. 
2.Que el código esté en lo posible en español, excepto para casos donde en inglés hace más sentido.
3.El monto de dinero siempre será visto en CPL, sin decimales, y con los cientos separados por punto.