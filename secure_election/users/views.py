from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .models import Voter
from voting.views import VOTING_ELECTION_SESSION_KEY

def voter_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user and not user.is_staff:
            login(request, user)
            request.session.pop('face_verified', None)
            request.session.pop(VOTING_ELECTION_SESSION_KEY, None)

            # Ensure Voter record exists for this user
            voter, created = Voter.objects.get_or_create(
                user=user,
                defaults={'voter_id': f'voter_{user.id}'}
            )

            # Redirect based on intent
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else '/vote-entry/')

        return render(request, 'voter_login.html', {
            'error': 'Invalid credentials'
        })

    return render(request, 'voter_login.html')

def voter_logout(request):
    logout(request)
    return redirect('/')
