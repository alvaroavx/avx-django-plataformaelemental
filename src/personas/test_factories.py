from django.contrib.auth import get_user_model

from .models import Persona, PersonaRol


def crear_usuario_con_rol(
    *,
    username,
    password,
    rol,
    organizacion,
    nombres=None,
    apellidos="Pruebas",
):
    user = get_user_model().objects.create_user(username, password=password)
    persona = Persona.objects.create(
        nombres=nombres or username,
        apellidos=apellidos,
        user=user,
    )
    PersonaRol.objects.create(
        persona=persona,
        rol=rol,
        organizacion=organizacion,
        activo=True,
    )
    return user


def asignar_profesora_a_sesion(*, user, sesion):
    from asistencias.models import AsignacionProfesorDisciplina

    sesion.profesores.add(user.persona)
    AsignacionProfesorDisciplina.objects.get_or_create(
        disciplina=sesion.disciplina,
        profesor=user.persona,
    )
    return user


__all__ = ["asignar_profesora_a_sesion", "crear_usuario_con_rol"]
