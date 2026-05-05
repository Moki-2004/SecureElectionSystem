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

VOTING_ELECTION_SESSION_KEY = 'voting_election_id'
RESULTS_ELECTION_SESSION_KEY = 'results_election_id'
INELIGIBLE_POPUP_SESSION_KEY = 'show_ineligible_election_popup'


def normalize_receipt_token(value):
    cleaned = ''.join(ch for ch in str(value).upper() if ch.isalnum())
    return cleaned


def hash_receipt_token(value):
    normalized = normalize_receipt_token(value)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def generate_receipt_token():
    raw = secrets.token_hex(12).upper()
    return '-'.join(raw[index:index + 4] for index in range(0, len(raw), 4))


def get_selected_election(request, session_key, *, read_get=True):
    if read_get and 'election_id' in request.GET:
        election_id = request.GET.get('election_id')
        if not election_id:
            request.session.pop(session_key, None)
            return None

        election = Election.objects.filter(id=election_id).first()
        if election:
            request.session[session_key] = election.id
            return election

    election_id = request.session.get(session_key)
    if election_id:
        return Election.objects.filter(id=election_id).first()

    return None


def build_results_summary(election=None):
    if election is None:
        return {
            'results': [],
            'winner': None,
            'is_tie': False,
            'tied_candidates': [],
            'total_votes': 0,
        }

    votes = Vote.objects.select_related('candidate').filter(election=election)
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
        top_candidates = list(Candidate.objects.filter(id__in=top_ids, election=election).order_by('id'))

        if len(top_candidates) == 1:
            winner = top_candidates[0].name
        elif len(top_candidates) > 1:
            is_tie = True
            tied_candidates = [candidate.name for candidate in top_candidates]
            winner = 'Tie'

    for cid, total in sorted_counts:
        candidate = Candidate.objects.filter(id=cid, election=election).first()
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
    Ensures election selection and face authentication before ballot display.
    """
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    now = timezone.now()
    elections = Election.objects.filter(
        is_active=True,
        start_time__lte=now,
        end_time__gte=now,
    ).order_by('start_time')
    eligible_elections = [
        election for election in elections
        if election.is_voter_eligible(voter)
    ]

    error = None
    selected_election = None
    show_ineligible_popup = False

    if request.method == 'POST':
        election_id = request.POST.get('election_id')

        if not election_id:
            error = 'Please select an election.'
        else:
            selected_election = Election.objects.filter(
                id=election_id,
                is_active=True,
                start_time__lte=now,
                end_time__gte=now,
            ).first()
            if not selected_election:
                error = 'Selected election is not active.'
            elif not selected_election.is_voter_eligible(voter):
                selected_election = None
                error = 'You are not eligible for this election.'
                show_ineligible_popup = True

        if selected_election:
            request.session[VOTING_ELECTION_SESSION_KEY] = selected_election.id
            request.session.pop('face_verified', None)
            if not voter.face_image:
                return redirect('/face-register/')
            return redirect('/face-auth/')

    return render(request, 'select_election.html', {
        'elections': eligible_elections,
        'error': error,
        'show_ineligible_popup': show_ineligible_popup,
    })


@login_required(login_url='/voter-login/')
def vote_page(request):
    """
    Displays candidates and records vote for the explicitly selected election.
    """
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    if not request.session.get('face_verified'):
        return redirect('/face-auth/')

    election = get_selected_election(
        request,
        VOTING_ELECTION_SESSION_KEY,
        read_get=False,
    )

    if not election:
        return redirect('/vote-entry/')

    now = timezone.now()
    if not (election.is_active and election.start_time <= now <= election.end_time):
        return render(request, 'message.html', {
            'msg': 'Selected election is not currently accepting votes.'
        })

    already_voted = Vote.objects.filter(voter=voter, election=election).exists()
    if already_voted:
        return render(request, 'message.html', {
            'msg': 'You have already voted in this election.'
        })

    candidates = Candidate.objects.filter(election=election)
    is_eligible = election.is_voter_eligible(voter)
    show_ineligible_popup = request.session.pop(INELIGIBLE_POPUP_SESSION_KEY, False)

    if request.method == 'POST':
        if not is_eligible:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'vote_time_limit': election.vote_time_limit,
                'election_name': election.name,
                'eligible': False,
                'error': 'You are not eligible for this election.',
                'show_ineligible_popup': True,
            })

        candidate_id = request.POST.get('candidate')

        if not candidate_id:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'vote_time_limit': election.vote_time_limit,
                'election_name': election.name,
                'eligible': is_eligible,
                'error': 'Please select a candidate.',
            })

        try:
            candidate = Candidate.objects.get(id=candidate_id, election=election)
        except Candidate.DoesNotExist:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'vote_time_limit': election.vote_time_limit,
                'election_name': election.name,
                'eligible': is_eligible,
                'error': 'Invalid candidate selected.',
            })

        with transaction.atomic():
            voter = Voter.objects.select_for_update().get(pk=voter.pk)
            if Vote.objects.filter(voter=voter, election=election).exists():
                return render(request, 'message.html', {
                    'msg': 'You have already voted in this election.'
                })

            receipt_token = generate_receipt_token()
            Vote.objects.create(
                voter=voter,
                election=election,
                candidate=candidate,
                encrypted_candidate=encrypt_vote(str(candidate.id)),
                receipt_hash=hash_receipt_token(receipt_token),
            )

        request.session.pop('face_verified', None)

        return render(request, 'vote_receipt.html', {
            'receipt_token': receipt_token,
            'election_name': election.name,
        })

    if not is_eligible:
        show_ineligible_popup = True

    return render(request, 'vote.html', {
        'candidates': candidates,
        'vote_time_limit': election.vote_time_limit,
        'election_name': election.name,
        'eligible': is_eligible,
        'show_ineligible_popup': show_ineligible_popup,
    })


def public_results(request):
    selected_election = get_selected_election(request, RESULTS_ELECTION_SESSION_KEY)
    elections = Election.objects.order_by('-start_time')
    summary = build_results_summary(selected_election)

    context = {
        'elections': elections,
        'selected_election': selected_election,
        **summary,
    }
    return render(request, 'results.html', context)


def public_results_data(request):
    selected_election = get_selected_election(request, RESULTS_ELECTION_SESSION_KEY)
    return JsonResponse(build_results_summary(selected_election))


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
