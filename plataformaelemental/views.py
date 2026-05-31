from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def elemental_apps(request):
    return render(request, "plataformaelemental/elemental_apps.html")
