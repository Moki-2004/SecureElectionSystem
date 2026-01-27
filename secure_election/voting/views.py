from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from users.models import Voter
from elections.models import Election, Candidate
from .models import Vote


# =========================================================
# ENTRY POINT FOR VOTING (LOGIN + FACE CHECK)
# =========================================================
@login_required(login_url='/voter-login/')
def vote_entry(request):
    """
    Entry gate for voting.
    Ensures face is registered and redirects to face authentication.
    """

    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    # ❌ Face must be registered before voting
    if not voter.face_image:
        return render(request, 'message.html', {
            'msg': 'Face not registered. Please complete face registration first.'
        })

    # ❌ Block repeat voting
    if voter.has_voted:
        return render(request, 'message.html', {
            'msg': 'You have already voted.'
        })

    # 🔐 Redirect to face authentication
    return redirect('/face-auth/')


# =========================================================
# ACTUAL VOTING PAGE (FACE VERIFIED)
# =========================================================
@login_required(login_url='/voter-login/')
def vote_page(request):
    """
    Displays candidates and records vote.
    Requires successful face authentication.
    """

    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    # 🔒 Face authentication required
    if not request.session.get('face_verified'):
        return redirect('/face-auth/')

    # ❌ Block repeat voting
    if voter.has_voted:
        return render(request, 'message.html', {
            'msg': 'You have already voted.'
        })

    # 🔍 Get active election
    election = Election.objects.filter(is_active=True).first()
    if not election:
        return render(request, 'message.html', {
            'msg': 'No active election at the moment.'
        })

    candidates = Candidate.objects.filter(election=election)

    if request.method == "POST":
        candidate_id = request.POST.get('candidate')

        if not candidate_id:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'error': 'Please select a candidate.'
            })

        try:
            candidate = Candidate.objects.get(id=candidate_id, election=election)
        except Candidate.DoesNotExist:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'vote_time_limit': election.vote_time_limit,
                'error': 'Invalid candidate selected.'
            })

        # ✅ Save vote
        Vote.objects.create(voter=voter, candidate=candidate)
        voter.has_voted = True
        voter.save()

        # 🔐 Clear face verification after voting
        request.session.flush()

        return render(request, 'message.html', {
            'msg': 'Vote cast successfully. Thank you for voting!'
        })

    return render(request, 'vote.html', {
        'candidates': candidates
    })
