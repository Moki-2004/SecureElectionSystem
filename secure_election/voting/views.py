from collections import Counter
import hashlib
import secrets

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from elections.models import Candidate, Election
from secure_election.utils.encryption import decrypt_vote, encrypt_vote
from users.models import Voter

from .models import Vote


def normalize_receipt_token(value):
    cleaned = ''.join(ch for ch in str(value).upper() if ch.isalnum())
    return cleaned


def hash_receipt_token(value):
    normalized = normalize_receipt_token(value)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def generate_receipt_token():
    raw = secrets.token_hex(12).upper()
    return '-'.join(raw[index:index + 4] for index in range(0, len(raw), 4))


def build_results_summary():
    votes = Vote.objects.select_related('candidate').all()
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
    sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    results = []
    winner = None
    is_tie = False
    tied_candidates = []

    if sorted_counts:
        top_vote_total = sorted_counts[0][1]
        top_ids = [cid for cid, total in sorted_counts if total == top_vote_total]
        top_candidates = list(Candidate.objects.filter(id__in=top_ids).order_by('id'))

        if len(top_candidates) == 1:
            winner = top_candidates[0].name
        elif len(top_candidates) > 1:
            is_tie = True
            tied_candidates = [candidate.name for candidate in top_candidates]
            winner = 'Tie'

    for cid, total in sorted_counts:
        candidate = Candidate.objects.filter(id=cid).first()
        if candidate:
            results.append({
                'candidate_id': candidate.id,
                'name': candidate.name,
                'votes': total,
            })

    total_votes = sum(item['votes'] for item in results)
    return {
        'results': results,
        'winner': winner,
        'is_tie': is_tie,
        'tied_candidates': tied_candidates,
        'total_votes': total_votes,
    }


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

            receipt_token = generate_receipt_token()
            Vote.objects.create(
                voter=voter,
                candidate=candidate,
                encrypted_candidate=encrypt_vote(str(candidate.id)),
                receipt_hash=hash_receipt_token(receipt_token),
            )
            voter.has_voted = True
            voter.save(update_fields=['has_voted'])

        request.session.pop('face_verified', None)

        return render(request, 'vote_receipt.html', {
            'receipt_token': receipt_token,
            'election_name': election.name,
        })

    return render(request, 'vote.html', {
        'candidates': candidates,
        'vote_time_limit': election.vote_time_limit,
    })


def public_results(request):
    summary = build_results_summary()
    return render(request, 'results.html', summary)


def public_results_data(request):
    return JsonResponse(build_results_summary())


def verify_receipt(request):
    context = {'checked': False}

    if request.method == 'POST':
        receipt_token = request.POST.get('receipt_token', '')
        normalized = normalize_receipt_token(receipt_token)

        context['checked'] = True
        context['receipt_token'] = receipt_token.strip()

        if not normalized:
            context['error'] = 'Enter your receipt token to verify a recorded vote.'
        else:
            receipt_hash = hash_receipt_token(normalized)
            vote = Vote.objects.filter(receipt_hash=receipt_hash).first()

            if vote:
                context['verified'] = True
                context['recorded_at'] = timezone.localtime(vote.timestamp)
            else:
                context['verified'] = False

    return render(request, 'verify_receipt.html', context)
