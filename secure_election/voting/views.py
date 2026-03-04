from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from elections.models import Candidate, Election
from secure_election.utils.encryption import decrypt_vote, encrypt_vote
from users.models import Voter

from .models import Vote


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

    if not voter.face_image:
        return render(request, 'message.html', {
            'msg': 'Face not registered. Please complete face registration first.'
        })

    if voter.has_voted or Vote.objects.filter(voter=voter).exists():
        return render(request, 'message.html', {
            'msg': 'You have already voted.'
        })

    return redirect('/face-auth/')


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

    if not request.session.get('face_verified'):
        return redirect('/face-auth/')

    if voter.has_voted or Vote.objects.filter(voter=voter).exists():
        return render(request, 'message.html', {
            'msg': 'You have already voted.'
        })

    now = timezone.now()
    election = Election.objects.filter(
        is_active=True,
        start_time__lte=now,
        end_time__gte=now,
    ).first()

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
                'vote_time_limit': election.vote_time_limit,
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

        with transaction.atomic():
            voter = Voter.objects.select_for_update().get(pk=voter.pk)
            if voter.has_voted or Vote.objects.filter(voter=voter).exists():
                return render(request, 'message.html', {
                    'msg': 'You have already voted.'
                })

            Vote.objects.create(
                voter=voter,
                candidate=candidate,
                encrypted_candidate=encrypt_vote(str(candidate.id)),
            )
            voter.has_voted = True
            voter.save(update_fields=['has_voted'])

        request.session.pop('face_verified', None)

        return render(request, 'message.html', {
            'msg': 'Vote cast successfully. Thank you for voting!'
        })

    return render(request, 'vote.html', {
        'candidates': candidates,
        'vote_time_limit': election.vote_time_limit,
    })


def public_results(request):
    votes = Vote.objects.all()
    decrypted_ids = []

    for vote in votes:
        try:
            if vote.encrypted_candidate:
                cid = decrypt_vote(vote.encrypted_candidate)
                decrypted_ids.append(int(cid))
            elif vote.candidate_id:
                decrypted_ids.append(vote.candidate_id)
        except Exception:
            continue

    counts = Counter(decrypted_ids)

    results = []
    winner = None

    if counts:
        top_id = max(counts, key=counts.get)
        top_candidate = Candidate.objects.filter(id=top_id).first()
        winner = top_candidate.name if top_candidate else None

    for cid, total in counts.items():
        candidate = Candidate.objects.filter(id=cid).first()
        if candidate:
            results.append((candidate.name, total))

    return render(request, 'results.html', {
        'results': results,
        'winner': winner
    })
