# Estrategia QA

## Cobertura minima fase 1
- Rutas protegidas por login.
- Dashboard sin datos.
- Dashboard con sitios.
- Crear sitio con URL valida.
- Rechazar URL invalida.
- Discovery con respuesta exitosa simulada.
- Discovery con timeout o error simulado.

## Tipos de tests
- Unitarios para normalizacion de URL.
- Unitarios para servicios de discovery.
- Integracion para vistas y forms.
- Smoke test de templates principales.

## Responsive
Validar manualmente:
- 375 px mobile.
- 768 px tablet.
- 1366 px desktop.

## Regla
No depender de red externa real en tests. Usar mocks, fakes o servicios encapsulados.
