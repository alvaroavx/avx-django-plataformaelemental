import unicodedata

from django.db.models import CharField, Func, Q, Value


CARACTERES_CON_TILDE = "ÁÉÍÓÚÜÑáéíóúüñ"
CARACTERES_SIN_TILDE = "AEIOUUNaeiouun"


def fragmentos_busqueda(termino):
    """Divide una consulta y normaliza tildes para comparar cada fragmento."""
    normalizado = unicodedata.normalize("NFKD", termino or "")
    sin_tildes = "".join(
        caracter for caracter in normalizado if not unicodedata.combining(caracter)
    )
    return [fragmento.lower() for fragmento in sin_tildes.split() if fragmento]


def _texto_sin_tildes(campo):
    return Func(
        campo,
        Value(CARACTERES_CON_TILDE),
        Value(CARACTERES_SIN_TILDE),
        function="TRANSLATE",
        output_field=CharField(),
    )


def filtrar_por_fragmentos(queryset, termino, *, campos, prefijo="persona_busqueda"):
    """Filtra con AND entre palabras y OR entre campos, ignorando tildes y mayúsculas.

    Los campos deben ser rutas ORM constantes y autorizadas por quien llama. El
    helper no altera el alcance inicial del queryset (organización, rol o clase).
    """
    fragmentos = fragmentos_busqueda(termino)
    if not fragmentos:
        return queryset

    aliases = []
    anotaciones = {}
    for indice, campo in enumerate(campos):
        alias = f"_{prefijo}_{indice}"
        aliases.append(alias)
        anotaciones[alias] = _texto_sin_tildes(campo)
    if not aliases:
        return queryset

    queryset = queryset.annotate(**anotaciones)
    for fragmento in fragmentos:
        coincidencia = Q()
        for alias in aliases:
            coincidencia |= Q(**{f"{alias}__icontains": fragmento})
        queryset = queryset.filter(coincidencia)
    return queryset
