import base64
import os

import face_recognition
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect

from users.models import Voter


# =========================================================
# FACE REGISTRATION (ONE-TIME ONLY)
# =========================================================
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

    # ❌ Block re-registration
    if voter.face_image:
        return render(request, 'message.html', {
            'msg': 'Face already registered. You can proceed to voting.'
        })

    if request.method == "POST":
        image_data = request.POST.get('image')

        if not image_data:
            return render(request, 'face_register.html', {
                'error': 'No image captured. Please try again.'
            })

        try:
            header, encoded = image_data.split(';base64,')
            image_file = ContentFile(
                base64.b64decode(encoded),
                name=f"{voter.voter_id}.png"
            )

            voter.face_image.save(f"{voter.voter_id}.png", image_file)
            voter.save()

            return render(request, 'message.html', {
                'msg': 'Face registration successful. You can now vote.'
            })

        except Exception:
            return render(request, 'face_register.html', {
                'error': 'Face registration failed. Please retry.'
            })

    return render(request, 'face_register.html')


# =========================================================
# FACE AUTHENTICATION (BEFORE VOTING)
# =========================================================
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

    # ❌ Cannot authenticate without face registration
    if not voter.face_image:
        return render(request, 'message.html', {
            'msg': 'Face not registered. Please register your face first.'
        })

    if request.method == "POST":
        image_data = request.POST.get('image')

        if not image_data:
            return render(request, 'face_auth.html', {
                'error': 'No image captured. Try again.'
            })

        temp_path = "temp_live_face.png"

        try:
            # Decode live image
            header, encoded = image_data.split(';base64,')
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(encoded))

            # Load images
            registered_img = face_recognition.load_image_file(voter.face_image.path)
            live_img = face_recognition.load_image_file(temp_path)

            registered_enc = face_recognition.face_encodings(registered_img)
            live_enc = face_recognition.face_encodings(live_img)

            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)

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
            else:
                return render(request, 'face_auth.html', {
                    'error': 'Face authentication failed.'
                })

        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return render(request, 'face_auth.html', {
                'error': 'Authentication error. Please retry.'
            })

    return render(request, 'face_auth.html')
