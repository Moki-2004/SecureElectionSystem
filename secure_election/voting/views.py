from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from secure_election.utils.encryption import encrypt_vote, decrypt_vote

from users.models import Voter
from elections.models import Election, Candidate
from voting.models import Vote

from collections import Counter


# =========================
# ENTRY BEFORE FACE AUTH
# =========================
@login_required(login_url='/voter-login/')
def vote_entry(request):
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    if not voter.face_image:
        return render(request, 'message.html', {'msg': 'Face not registered.'})

    if voter.has_voted:
        return render(request, 'message.html', {'msg': 'Already voted.'})

    return redirect('/face-auth/')


# =========================
# ACTUAL VOTING PAGE
# =========================
@login_required(login_url='/voter-login/')
def vote_page(request):
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    if not request.session.get('face_verified'):
        return redirect('/face-auth/')

    election = Election.objects.filter(is_active=True).first()

    if not election:
        return render(request, 'message.html', {'msg': 'No active election.'})

    candidates = Candidate.objects.filter(election=election)

    if request.method == "POST":
        candidate_id = request.POST.get('candidate')

        if not candidate_id:
            return render(request, 'vote.html', {
                'candidates': candidates,
                'error': 'Select a candidate'
            })

        try:
            candidate = Candidate.objects.get(id=candidate_id)
        except Candidate.DoesNotExist:
            return render(request, 'message.html', {'msg': 'Invalid candidate'})

        # 🔐 Encrypt vote before storing
        encrypted_id = encrypt_vote(str(candidate.id))

        Vote.objects.create(
            voter=voter,
            encrypted_candidate=encrypted_id
        )

        # Mark voter as voted
        voter.has_voted = True
        voter.save()

        # Clear session (security)
        request.session.flush()

        return render(request, 'message.html', {
            'msg': 'Vote cast successfully!'
        })

    return render(request, 'vote.html', {'candidates': candidates})


# =========================
# PUBLIC RESULTS PAGE (OPTIONAL)
# =========================
def public_results(request):
    votes = Vote.objects.all()
    decrypted_ids = []

    # 🔓 Decrypt all votes
    for vote in votes:
        try:
            cid = decrypt_vote(vote.encrypted_candidate)
            decrypted_ids.append(int(cid))
        except:
            pass

    counts = Counter(decrypted_ids)

    results = []
    winner = None

    # Find winner
    if counts:
        top_id = max(counts, key=counts.get)
        winner = Candidate.objects.get(id=top_id).name

    # Build result list
    for cid, total in counts.items():
        try:
            name = Candidate.objects.get(id=cid).name
            results.append((name, total))
        except:
            pass

    return render(request, "results.html", {
        "results": results,
        "winner": winner
    })