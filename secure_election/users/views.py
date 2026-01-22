from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login

def voter_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user and not user.is_staff:
            login(request, user)

            # Redirect based on intent
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else '/')

        return render(request, 'voter_login.html', {
            'error': 'Invalid credentials'
        })

    return render(request, 'voter_login.html')
