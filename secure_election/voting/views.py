from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from elections.models import Candidate, Election
from users.models import Voter
from .models import Vote
from django.utils import timezone

@login_required
def vote_page(request):
    voter = Voter.objects.get(user=request.user)

    # Check if voter already voted
    if voter.has_voted:
        return render(request, 'vote.html', {
            'error': 'You have already voted.'
        })

    # Get active election
    election = Election.objects.filter(is_active=True).first()
    if not election:
        return render(request, 'vote.html', {
            'error': 'No active election.'
        })

    candidates = Candidate.objects.filter(election=election)

    if request.method == "POST":
        candidate_id = request.POST.get('candidate')
        try:
            candidate = Candidate.objects.get(id=candidate_id)
            # Save vote
            Vote.objects.create(voter=voter, candidate=candidate)
            voter.has_voted = True
            voter.save()
            return render(request, 'vote.html', {
                'success': 'Vote submitted successfully!'
            })
        except Candidate.DoesNotExist:
            return render(request, 'vote.html', {
                'error': 'Invalid candidate selected.'
            })

    return render(request, 'vote.html', {'candidates': candidates})
