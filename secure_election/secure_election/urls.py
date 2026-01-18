"""
URL configuration for secure_election project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.conf.urls.static import static


def home(request):
    return render(request, 'home.html')

def admin_login(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user and user.is_staff:
            login(request, user)
            return redirect('/admin/')
        else:
            return render(request, 'admin_login.html', {
                'error': 'Invalid credentials'
            })
    return render(request, 'admin_login.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home),
    path('admin-login/', admin_login),
    path('', include('users.urls')),
    path('', include('proctoring.urls')),
    path('', include('voting.urls')),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)