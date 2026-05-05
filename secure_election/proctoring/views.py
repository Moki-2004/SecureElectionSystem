import base64
import os
import tempfile
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from users.models import Voter
from voting.views import VOTING_ELECTION_SESSION_KEY

from .models import ProctoringLog, ProctoringRule


@login_required(login_url='/voter-login/')
def face_register(request):
    """
    Allows a voter to register face exactly once.
    Requires voter login.
    """
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    if voter.face_image:
        if request.session.get(VOTING_ELECTION_SESSION_KEY):
            return redirect('/face-auth/')
        return redirect('/vote-entry/')

    if request.method == "POST":
        image_data = request.POST.get('image')

        if not image_data:
            return render(request, 'face_register.html', {
                'error': 'No image captured. Please try again.'
            })

        try:
            _, encoded = image_data.split(';base64,')
            image_file = ContentFile(
                base64.b64decode(encoded),
                name=f"{voter.voter_id}.png"
            )

            voter.face_image.save(f"{voter.voter_id}.png", image_file)
            voter.save(update_fields=['face_image'])

            if request.session.get(VOTING_ELECTION_SESSION_KEY):
                return redirect('/face-auth/')

            return redirect('/vote-entry/')
        except Exception:
            return render(request, 'face_register.html', {
                'error': 'Face registration failed. Please retry.'
            })

    return render(request, 'face_register.html')


@login_required(login_url='/voter-login/')
def face_authenticate(request):
    """
    Authenticates voter using live face capture.
    Redirects to voting on success.
    """
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return redirect('/voter-login/')

    if not request.session.get(VOTING_ELECTION_SESSION_KEY):
        return redirect('/vote-entry/')

    if not voter.face_image:
        return redirect('/face-register/')

    if request.method == "POST":
        image_data = request.POST.get('image')

        if not image_data:
            return render(request, 'face_auth.html', {
                'error': 'No image captured. Try again.'
            })

        temp_path = None

        try:
            _, encoded = image_data.split(';base64,')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file.write(base64.b64decode(encoded))
                temp_path = temp_file.name

            import face_recognition

            registered_img = face_recognition.load_image_file(voter.face_image.path)
            live_img = face_recognition.load_image_file(temp_path)

            registered_enc = face_recognition.face_encodings(registered_img)
            live_enc = face_recognition.face_encodings(live_img)

            if not registered_enc or not live_enc:
                return render(request, 'face_auth.html', {
                    'error': 'Face not detected properly. Try again.'
                })

            match = face_recognition.compare_faces(
                [registered_enc[0]],
                live_enc[0],
                tolerance=0.5
            )

            if match[0]:
                request.session['face_verified'] = True
                return redirect('/vote/')

            return render(request, 'face_auth.html', {
                'error': 'Face authentication failed.'
            })

        except Exception:
            return render(request, 'face_auth.html', {
                'error': 'Authentication error. Please retry.'
            })
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    return render(request, 'face_auth.html')


@login_required(login_url='/voter-login/')
@require_POST
def log_violation(request):
    try:
        voter = Voter.objects.get(user=request.user)
    except Voter.DoesNotExist:
        return JsonResponse({'status': 'unauthorized'}, status=401)

    violation = (request.POST.get('type') or '').strip().upper()
    valid_types = {choice[0] for choice in ProctoringLog.VIOLATION_TYPES}

    if violation not in valid_types:
        return JsonResponse({'status': 'invalid violation type'}, status=400)

    rule = ProctoringRule.objects.first()
    max_warnings = rule.max_warnings if rule else 2

    warning_count = ProctoringLog.objects.filter(
        voter=voter,
        blocked=False
    ).count()

    log = ProctoringLog.objects.create(
        voter=voter,
        violation_type=violation
    )

    if violation in {'FACE_CHANGED', 'MULTIPLE_FACES'}:
        log.blocked = True
        log.save(update_fields=['blocked'])
        return JsonResponse({'action': 'BLOCK'})

    if warning_count < max_warnings:
        return JsonResponse({
            'action': 'WARN',
            'remaining': max_warnings - warning_count
        })

    log.blocked = True
    log.save(update_fields=['blocked'])
    return JsonResponse({'action': 'BLOCK'})
