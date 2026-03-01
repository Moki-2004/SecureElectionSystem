from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout


def voter_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('/vote-entry/')
        else:
            return render(request, "voter_login.html", {
                "error": "Invalid username or password"
            })

    return render(request, "voter_login.html")


def voter_logout(request):
    logout(request)
    return redirect('/')