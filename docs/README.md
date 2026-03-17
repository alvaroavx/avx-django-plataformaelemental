# Documentacion interna del repo

Esta carpeta existe para persistir decisiones, reglas operativas y acuerdos de producto/arquitectura que se vayan tomando durante el trabajo sobre la plataforma.

## Regla de mantenimiento
- Cada decision concreta que cambie comportamiento, modelo de datos, navegacion o criterio de uso debe quedar documentada.
- La documentacion general y humana vive en `README.md`.
- La documentacion tecnica y de decisiones vive en archivos Markdown cercanos al dominio afectado.
- Cuando una decision afecta una app puntual, su archivo local debe actualizarse en el mismo cambio de codigo.

## Archivos vigentes
- [README.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/README.md): vision general para uso humano.
- [PLATAFORMA.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/PLATAFORMA.md): estado tecnico consolidado del proyecto.
- [DECISIONES.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/DECISIONES.md): indice corto y puente hacia la documentacion viva.
- [finanzas/FINANZAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/finanzas/FINANZAS.md): decisiones y modelo operativo de finanzas.
- [asistencias/ASISTENCIAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/asistencias/ASISTENCIAS.md): criterios funcionales de asistencia y operacion academica.
- [personas/PERSONAS.md](/home/alvax/Code/platforms/avx-django-plataformaelemental/personas/PERSONAS.md): criterios del CRM, perfiles y organizaciones.
