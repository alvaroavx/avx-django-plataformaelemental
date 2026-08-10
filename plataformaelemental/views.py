from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from personas.models import PersonaRol
from personas.permissions import normalizar_codigo_rol


@login_required
def elemental_apps(request):
    persona = getattr(request.user, "persona", None)
    if persona:
        roles = {
            normalizar_codigo_rol(codigo)
            for codigo in PersonaRol.objects.filter(persona=persona, activo=True).values_list("rol__codigo", flat=True)
        }
        if "profesor" in roles and not roles.intersection({"admin", "staff_asistencia", "finanzas"}):
            return redirect("profesor:inicio")
    return render(request, "plataformaelemental/elemental_apps.html")
