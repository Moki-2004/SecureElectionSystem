from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login

def voter_login(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST['username'],
            password=request.POST['password']
        )
        if user and not user.is_staff:
            login(request, user)
            return redirect('/face-register/')
        else:
            return render(request, 'voter_login.html', {
                'error': 'Invalid voter credentials'
            })
    return render(request, 'voter_login.html')
